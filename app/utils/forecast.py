from __future__ import annotations

import hashlib
import json
import math
import pickle
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models import BloodBank, BloodBankStock, BloodRequest, DonationRecord, Hospital
from app.utils.matching import COUNTY_DISTANCE

try:  # scikit-learn is required by the plan, but the app should still degrade gracefully.
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    from sklearn.pipeline import Pipeline

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - only used when sklearn is unavailable locally.
    DummyRegressor = None  # type: ignore[assignment]
    RandomForestRegressor = None  # type: ignore[assignment]
    DictVectorizer = None  # type: ignore[assignment]
    GradientBoostingRegressor = None  # type: ignore[assignment]
    HistGradientBoostingRegressor = None  # type: ignore[assignment]
    Ridge = None  # type: ignore[assignment]
    mean_absolute_error = None  # type: ignore[assignment]
    mean_squared_error = None  # type: ignore[assignment]
    Pipeline = None  # type: ignore[assignment]
    SKLEARN_AVAILABLE = False

BLOOD_TYPES = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

HOSPITAL_FEATURE_ALIASES = {
    "hospital_id": ["hospital_id", "facility_id", "site_id", "facility"],
    "county": ["county", "county_name", "hospital_county", "location_county"],
    "blood_type": ["blood_type", "blood_group", "group", "requested_blood_type"],
    "urgency_level": ["urgency_level", "urgency", "priority"],
    "units_needed": ["units_needed", "required_units", "demand_units", "volume"],
    "day_of_week_name": ["day_of_week_name", "weekday", "day_name"],
    "month_name": ["month_name", "month_label"],
    "is_weekend": ["is_weekend"],
    "holiday_flag": ["holiday_flag"],
    "recent_hospital_requests_30d": ["recent_hospital_requests_30d", "hospital_requests_30d"],
    "recent_hospital_requests_90d": ["recent_hospital_requests_90d", "hospital_requests_90d"],
    "recent_county_requests_30d": ["recent_county_requests_30d", "county_requests_30d"],
    "recent_blood_type_requests_30d": ["recent_blood_type_requests_30d", "blood_type_requests_30d"],
    "county_stock_total": ["county_stock_total", "stock_total"],
    "county_stock_pressure": ["county_stock_pressure", "stock_pressure"],
    "bank_count_in_county": ["bank_count_in_county", "blood_bank_count"],
}

BLOOD_TYPE_FACTORS = {
    "O-": 1.35,
    "O+": 1.15,
    "A-": 1.08,
    "A+": 1.0,
    "B-": 0.95,
    "B+": 0.9,
    "AB-": 0.82,
    "AB+": 0.75,
}

HORIZON_DAYS = 14
TRAINING_LOOKBACK_DAYS = 180
FORECAST_CACHE_DIR_NAME = "forecast"
FORECAST_BUNDLE_FILENAME = "forecast_bundle.pkl"
FORECAST_META_FILENAME = "forecast_meta.json"
DEFAULT_COUNTY_COORDS = {
    "Baringo": (35.95, 0.47),
    "Bomet": (35.35, -0.78),
    "Bungoma": (34.56, 0.57),
    "Busia": (34.12, 0.46),
    "Elgeyo Marakwet": (35.57, 0.52),
    "Embu": (37.45, -0.53),
    "Garissa": (39.65, -0.46),
    "Homa Bay": (34.46, -0.53),
    "Isiolo": (37.58, 0.35),
    "Kajiado": (36.78, -1.85),
    "Kakamega": (34.75, 0.28),
    "Kericho": (35.29, -0.37),
    "Kiambu": (36.83, -1.17),
    "Kilifi": (39.85, -3.63),
    "Kirinyaga": (37.33, -0.50),
    "Kisii": (34.77, -0.68),
    "Kisumu": (34.76, -0.10),
    "Kitui": (38.01, -1.37),
    "Kwale": (39.46, -4.18),
    "Laikipia": (36.95, 0.20),
    "Lamu": (40.90, -2.27),
    "Machakos": (37.26, -1.52),
    "Makueni": (37.94, -2.28),
    "Mandera": (41.84, 3.94),
    "Marsabit": (37.99, 2.33),
    "Meru": (37.65, 0.05),
    "Migori": (34.47, -1.06),
    "Mombasa": (39.67, -4.04),
    "Muranga": (37.16, -0.72),
    "Nairobi": (36.82, -1.29),
    "Nakuru": (36.07, -0.28),
    "Nandi": (35.20, 0.11),
    "Narok": (35.87, -1.10),
    "Nyamira": (34.93, -0.56),
    "Nyandarua": (36.56, -0.35),
    "Nyeri": (36.95, -0.42),
    "Samburu": (36.72, 1.09),
    "Siaya": (34.27, 0.07),
    "Taita Taveta": (38.37, -3.40),
    "Tana River": (40.08, -1.53),
    "Tharaka Nithi": (37.80, -0.30),
    "Trans Nzoia": (34.95, 1.02),
    "Turkana": (35.61, 3.12),
    "Uasin Gishu": (35.27, 0.52),
    "Vihiga": (34.72, 0.08),
    "Wajir": (40.05, 1.75),
    "West Pokot": (35.22, 1.90),
}


def _cache_dir() -> Path:
    try:
        base_dir = Path(current_app.instance_path)
    except Exception:
        base_dir = Path(__file__).resolve().parents[2] / "instance"
    cache_dir = base_dir / FORECAST_CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _bundle_path() -> Path:
    return _cache_dir() / FORECAST_BUNDLE_FILENAME


def _meta_path() -> Path:
    return _cache_dir() / FORECAST_META_FILENAME


def _geojson_path() -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "geojson" / "kenya_counties_centroids.geojson"


def invalidate_forecast_cache() -> None:
    for path in (_bundle_path(), _meta_path()):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def _first_present(payload: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def canonicalize_hospital_upload_row(payload: dict[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for field, aliases in HOSPITAL_FEATURE_ALIASES.items():
        value = _first_present(payload, aliases)
        canonical[field] = value
        canonical[f"missing_{field}"] = 0 if value not in (None, "") else 1
    return canonical


def _holiday_flag(moment: datetime) -> int:
    if (moment.month == 1 and moment.day <= 3) or (moment.month == 4 and moment.day <= 7):
        return 1
    if moment.month == 5 and moment.day == 1:
        return 1
    if moment.month == 8 and moment.day == 1:
        return 1
    if moment.month == 10 and moment.day == 20:
        return 1
    if moment.month == 12 and moment.day >= 24:
        return 1
    return 0


def _day_name(moment: datetime) -> str:
    return WEEKDAY_NAMES[moment.weekday()]


def _month_name(moment: datetime) -> str:
    return MONTH_NAMES[moment.month - 1]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _count_rows_since(rows: list[Any], since: datetime, attr_name: str = "created_at") -> int:
    total = 0
    for row in rows:
        when = getattr(row, attr_name, None)
        if when and when >= since:
            total += 1
    return total


def _stock_by_county() -> tuple[dict[str, int], dict[str, int]]:
    stock_totals: dict[str, int] = defaultdict(int)
    bank_counts: dict[str, int] = defaultdict(int)
    stocks = BloodBankStock.query.join(BloodBank).all()
    for stock in stocks:
        bank = stock.blood_bank
        county = (bank.county if bank and bank.county else "Unknown").strip() or "Unknown"
        stock_totals[county] += _safe_int(stock.units_available)
        bank_counts[county] += 1
    return stock_totals, bank_counts


def _request_counters(reference_date: datetime | None = None) -> dict[str, Any]:
    requests = BloodRequest.query.join(Hospital).all()
    cutoff_30 = (reference_date or datetime.utcnow()) - timedelta(days=30)
    cutoff_90 = (reference_date or datetime.utcnow()) - timedelta(days=90)

    by_hospital_30: Counter[int] = Counter()
    by_hospital_90: Counter[int] = Counter()
    by_county_30: Counter[str] = Counter()
    by_type_30: defaultdict[int, Counter[str]] = defaultdict(Counter)
    by_type_90: defaultdict[int, Counter[str]] = defaultdict(Counter)
    all_requests_by_hospital: defaultdict[int, list[Any]] = defaultdict(list)

    for request in requests:
        all_requests_by_hospital[request.hospital_id].append(request)
        when = request.created_at or datetime.utcnow()
        hospital = request.hospital
        county = (hospital.county if hospital and hospital.county else "Unknown").strip() or "Unknown"
        blood_type = (request.blood_type or "Unknown").strip() or "Unknown"

        if when >= cutoff_30:
            by_hospital_30[request.hospital_id] += 1
            by_county_30[county] += 1
            by_type_30[request.hospital_id][blood_type] += 1
        if when >= cutoff_90:
            by_hospital_90[request.hospital_id] += 1
            by_type_90[request.hospital_id][blood_type] += 1

    return {
        "requests": requests,
        "by_hospital_30": by_hospital_30,
        "by_hospital_90": by_hospital_90,
        "by_county_30": by_county_30,
        "by_type_30": by_type_30,
        "by_type_90": by_type_90,
        "all_requests_by_hospital": all_requests_by_hospital,
    }


def _training_feature_row(
    request: BloodRequest,
    request_history: list[dict[str, Any]],
    stock_totals: dict[str, int],
    bank_counts: dict[str, int],
) -> dict[str, Any]:
    hospital = request.hospital
    county = (hospital.county if hospital and hospital.county else "Unknown").strip() or "Unknown"
    blood_type = (request.blood_type or "Unknown").strip() or "Unknown"
    when = request.created_at or datetime.utcnow()
    cutoff_30 = when - timedelta(days=30)
    cutoff_90 = when - timedelta(days=90)

    recent_hospital_30 = 0
    recent_hospital_90 = 0
    recent_county_30 = 0
    recent_type_30 = 0
    recent_type_90 = 0

    for past in request_history:
        past_when = past["created_at"]
        if past["hospital_id"] == request.hospital_id and past_when >= cutoff_30:
            recent_hospital_30 += 1
        if past["hospital_id"] == request.hospital_id and past_when >= cutoff_90:
            recent_hospital_90 += 1
        if past["county"] == county and past_when >= cutoff_30:
            recent_county_30 += 1
        if past["hospital_id"] == request.hospital_id and past["blood_type"] == blood_type and past_when >= cutoff_30:
            recent_type_30 += 1
        if past["hospital_id"] == request.hospital_id and past["blood_type"] == blood_type and past_when >= cutoff_90:
            recent_type_90 += 1

    county_stock_total = stock_totals.get(county, 0)
    county_pressure = round(recent_county_30 / max(county_stock_total, 1), 3)

    return {
        "hospital_id": f"hospital-{request.hospital_id}",
        "county": county,
        "blood_type": blood_type,
        "urgency_level": (request.urgency_level or "normal").strip() or "normal",
        "day_of_week_name": _day_name(when),
        "month_name": _month_name(when),
        "is_weekend": int(when.weekday() >= 5),
        "holiday_flag": _holiday_flag(when),
        "recent_hospital_requests_30d": recent_hospital_30,
        "recent_hospital_requests_90d": recent_hospital_90,
        "recent_county_requests_30d": recent_county_30,
        "recent_blood_type_requests_30d": recent_type_30,
        "recent_blood_type_requests_90d": recent_type_90,
        "county_stock_total": county_stock_total,
        "county_stock_pressure": county_pressure,
        "bank_count_in_county": bank_counts.get(county, 0),
        "source": "actual",
    }


def _build_training_rows() -> list[dict[str, Any]]:
    requests = BloodRequest.query.join(Hospital).order_by(BloodRequest.created_at.asc(), BloodRequest.id.asc()).all()
    stock_totals, bank_counts = _stock_by_county()
    request_history: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for request in requests:
        feature_row = _training_feature_row(request, request_history, stock_totals, bank_counts)
        rows.append(
            {
                "request_id": request.id,
                "created_at": request.created_at or datetime.utcnow(),
                "features": feature_row,
                "target": max(1.0, float(request.units_needed or 1)),
            }
        )
        request_history.append(
            {
                "request_id": request.id,
                "created_at": request.created_at or datetime.utcnow(),
                "hospital_id": request.hospital_id,
                "county": feature_row["county"],
                "blood_type": feature_row["blood_type"],
            }
        )

    return rows


def _split_train_validation(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return [], []
    validation_size = max(1, int(len(rows) * 0.2)) if len(rows) > 4 else 1
    if validation_size >= len(rows):
        validation_size = 1
    split_index = max(1, len(rows) - validation_size)
    return rows[:split_index], rows[split_index:]


def _model_candidates() -> list[tuple[str, Any]]:
    if not SKLEARN_AVAILABLE:
        return []
    return [
        ("dummy_mean", DummyRegressor(strategy="mean")),
        ("ridge", Ridge(alpha=1.0, random_state=42)),
        ("random_forest", RandomForestRegressor(n_estimators=300, random_state=42, min_samples_leaf=2, n_jobs=1)),
        ("gradient_boosting", GradientBoostingRegressor(random_state=42)),
        ("hist_gradient_boosting", HistGradientBoostingRegressor(random_state=42, learning_rate=0.08, max_depth=6)),
    ]


def _mape(y_true: list[float], y_pred: list[float]) -> float:
    if not y_true:
        return 0.0
    ratios = []
    for actual, predicted in zip(y_true, y_pred):
        denom = max(abs(actual), 1e-6)
        ratios.append(abs(actual - predicted) / denom)
    return sum(ratios) / len(ratios)


def _evaluate_candidate(name: str, model: Any, train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not SKLEARN_AVAILABLE or not train_rows:
        return None

    pipeline = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            ("model", model),
        ]
    )

    train_features = [row["features"] for row in train_rows]
    train_targets = [float(row["target"]) for row in train_rows]
    try:
        pipeline.fit(train_features, train_targets)
        validation_features = [row["features"] for row in validation_rows] if validation_rows else train_features
        validation_targets = [float(row["target"]) for row in validation_rows] if validation_rows else train_targets
        predictions = list(pipeline.predict(validation_features))
        mae = float(mean_absolute_error(validation_targets, predictions)) if mean_absolute_error else 0.0
        rmse = float(math.sqrt(mean_squared_error(validation_targets, predictions))) if mean_squared_error else 0.0
        mape = _mape(validation_targets, predictions)
    except Exception:
        return None

    return {
        "name": name,
        "pipeline": pipeline,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4),
        "training_rows": len(train_rows),
        "validation_rows": len(validation_rows),
    }


def _select_best_model(train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated: list[dict[str, Any]] = []
    for name, model in _model_candidates():
        result = _evaluate_candidate(name, model, train_rows, validation_rows)
        if result is not None:
            evaluated.append(result)

    if not evaluated:
        return {
            "name": "baseline",
            "pipeline": None,
            "mae": None,
            "rmse": None,
            "mape": None,
            "training_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "evaluated_models": [],
        }

    evaluated.sort(key=lambda item: (item["mae"], item["rmse"], item["name"]))
    best = evaluated[0]
    best["evaluated_models"] = [
        {"name": item["name"], "mae": item["mae"], "rmse": item["rmse"], "mape": item["mape"]}
        for item in evaluated
    ]
    return best


def _predict_pipeline(pipeline: Any | None, feature_row: dict[str, Any], stats: dict[str, Any]) -> float:
    if pipeline is not None:
        try:
            predicted = pipeline.predict([feature_row])[0]
            return max(0.0, float(predicted))
        except Exception:
            pass

    county = str(feature_row.get("county") or "Unknown")
    hospital_key = feature_row.get("hospital_id")
    blood_type = str(feature_row.get("blood_type") or "O+")
    urgency_level = str(feature_row.get("urgency_level") or "normal")
    base = stats.get("hospital_mean", {}).get(hospital_key, stats.get("county_mean", {}).get(county, stats.get("global_mean", 4.0)))
    weekend_factor = 1.12 if feature_row.get("is_weekend") else 1.0
    holiday_factor = 1.1 if feature_row.get("holiday_flag") else 1.0
    type_factor = BLOOD_TYPE_FACTORS.get(blood_type, 1.0)
    urgency_factor = 1.12 if urgency_level == "urgent" else 0.97
    pressure_factor = 1.0 + min(float(feature_row.get("county_stock_pressure", 0.0)), 2.5) * 0.10
    recent_factor = 1.0 + min(float(feature_row.get("recent_hospital_requests_30d", 0.0)) / 18.0, 1.2) * 0.20
    predicted = base * weekend_factor * holiday_factor * type_factor * urgency_factor * pressure_factor * recent_factor
    return max(0.0, float(predicted))


def _synthetic_request_rows(hospitals: list[Hospital], stats: dict[str, Any], reference_date: datetime | None = None) -> list[dict[str, Any]]:
    reference = reference_date or datetime.utcnow()
    rng = random.Random(42)
    rows: list[dict[str, Any]] = []

    if not hospitals:
        hospitals = []

    for hospital in hospitals or [None]:
        if hospital is None:
            county = "Nairobi"
            hospital_id = 0
            base_demand = 8.0
        else:
            county = (hospital.county or "Unknown").strip() or "Unknown"
            hospital_id = hospital.id
            base_demand = max(3.0, stats["hospital_mean"].get(hospital_id, 6.0))

        county_stock_total = stats["county_stock_total"].get(county, 0)
        county_pressure = stats["county_pressure"].get(county, 1.0)
        county_base = stats["county_mean"].get(county, base_demand)
        recent_hospital = stats["hospital_30"].get(hospital_id, 0)

        for offset in range(0, TRAINING_LOOKBACK_DAYS, 2):
            moment = reference - timedelta(days=offset)
            weekend_factor = 1.18 if moment.weekday() >= 5 else 1.0
            holiday_factor = 1.15 if _holiday_flag(moment) else 1.0
            month_factor = 1.0 + (0.12 if moment.month in {12, 1} else 0.04 if moment.month in {4, 8} else 0.0)
            recency_factor = 1.0 + min(recent_hospital / 20.0, 1.0) * 0.25

            for blood_type in BLOOD_TYPES:
                type_factor = BLOOD_TYPE_FACTORS[blood_type]
                urgency_level = "urgent" if blood_type in {"O-", "O+"} and moment.weekday() >= 4 else "normal"
                urgency_factor = 1.12 if urgency_level == "urgent" else 0.95
                noise = rng.uniform(-0.8, 0.8)
                target = max(
                    1.0,
                    (county_base * type_factor * weekend_factor * holiday_factor * month_factor * urgency_factor * recency_factor)
                    + (county_pressure * 0.5)
                    + noise,
                )
                rows.append(
                    {
                        "features": {
                            "hospital_id": f"hospital-{hospital_id}",
                            "county": county,
                            "blood_type": blood_type,
                            "urgency_level": urgency_level,
                            "day_of_week_name": _day_name(moment),
                            "month_name": _month_name(moment),
                            "is_weekend": int(moment.weekday() >= 5),
                            "holiday_flag": _holiday_flag(moment),
                            "recent_hospital_requests_30d": recent_hospital,
                            "recent_hospital_requests_90d": stats["hospital_90"].get(hospital_id, 0),
                            "recent_county_requests_30d": stats["county_30"].get(county, 0),
                            "recent_blood_type_requests_30d": stats["by_type_30"].get(hospital_id, Counter()).get(blood_type, 0),
                            "county_stock_total": county_stock_total,
                            "county_stock_pressure": round(county_pressure, 3),
                            "bank_count_in_county": stats["bank_count"].get(county, 0),
                            "source": "synthetic",
                        },
                        "target": target,
                    }
                )
    return rows


def _actual_request_rows(stats: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    request_rows = stats["requests"]
    stock_totals = stats["county_stock_total"]
    bank_counts = stats["bank_count"]
    by_hospital_30 = stats["by_hospital_30"]
    by_hospital_90 = stats["by_hospital_90"]
    by_county_30 = stats["by_county_30"]
    by_type_30 = stats["by_type_30"]
    by_type_90 = stats["by_type_90"]

    for request in request_rows:
        hospital = request.hospital
        county = (hospital.county if hospital and hospital.county else "Unknown").strip() or "Unknown"
        blood_type = (request.blood_type or "Unknown").strip() or "Unknown"
        when = request.created_at or datetime.utcnow()
        rows.append(
            {
                "features": {
                    "hospital_id": f"hospital-{request.hospital_id}",
                    "county": county,
                    "blood_type": blood_type,
                    "urgency_level": request.urgency_level or "normal",
                    "day_of_week_name": _day_name(when),
                    "month_name": _month_name(when),
                    "is_weekend": int(when.weekday() >= 5),
                    "holiday_flag": _holiday_flag(when),
                    "recent_hospital_requests_30d": by_hospital_30.get(request.hospital_id, 0),
                    "recent_hospital_requests_90d": by_hospital_90.get(request.hospital_id, 0),
                    "recent_county_requests_30d": by_county_30.get(county, 0),
                    "recent_blood_type_requests_30d": by_type_30.get(request.hospital_id, Counter()).get(blood_type, 0),
                    "recent_blood_type_requests_90d": by_type_90.get(request.hospital_id, Counter()).get(blood_type, 0),
                    "county_stock_total": stock_totals.get(county, 0),
                    "county_stock_pressure": round(by_county_30.get(county, 0) / max(stock_totals.get(county, 0), 1), 3),
                    "bank_count_in_county": bank_counts.get(county, 0),
                    "source": "actual",
                },
                "target": max(1.0, float(request.units_needed or 1)),
            }
        )
    return rows


def _training_stats() -> dict[str, Any]:
    hospitals = Hospital.query.all()
    request_rows = BloodRequest.query.join(Hospital).all()
    stock_totals, bank_counts = _stock_by_county()
    request_counters = _request_counters()

    hospital_mean: dict[int, float] = defaultdict(float)
    hospital_30: dict[int, int] = defaultdict(int)
    hospital_90: dict[int, int] = defaultdict(int)
    county_mean: dict[str, float] = defaultdict(float)
    county_30: dict[str, int] = defaultdict(int)
    county_stock_pressure: dict[str, float] = defaultdict(float)
    blood_type_mean: dict[str, float] = defaultdict(float)
    blood_type_30: dict[str, int] = defaultdict(int)

    hospital_targets: defaultdict[int, list[float]] = defaultdict(list)
    county_targets: defaultdict[str, list[float]] = defaultdict(list)
    blood_type_targets: defaultdict[str, list[float]] = defaultdict(list)

    for request in request_rows:
        hospital = request.hospital
        county = (hospital.county if hospital and hospital.county else "Unknown").strip() or "Unknown"
        blood_type = (request.blood_type or "Unknown").strip() or "Unknown"
        target = max(1.0, float(request.units_needed or 1))
        hospital_targets[request.hospital_id].append(target)
        county_targets[county].append(target)
        blood_type_targets[blood_type].append(target)

    for hospital_id, values in hospital_targets.items():
        hospital_mean[hospital_id] = sum(values) / len(values)
    for county, values in county_targets.items():
        county_mean[county] = sum(values) / len(values)
    for blood_type, values in blood_type_targets.items():
        blood_type_mean[blood_type] = sum(values) / len(values)

    for hospital in hospitals:
        hospital_30[hospital.id] = request_counters["by_hospital_30"].get(hospital.id, 0)
        hospital_90[hospital.id] = request_counters["by_hospital_90"].get(hospital.id, 0)
    for county, count in request_counters["by_county_30"].items():
        county_30[county] = count
    for blood_type in BLOOD_TYPES:
        blood_type_30[blood_type] = sum(counter.get(blood_type, 0) for counter in request_counters["by_type_30"].values())

    county_stock_total = defaultdict(int, stock_totals)
    county_stock_pressure = defaultdict(float)
    for county in set(list(county_stock_total.keys()) + list(county_30.keys())):
        county_stock_pressure[county] = round(county_30.get(county, 0) / max(county_stock_total.get(county, 0), 1), 3)

    return {
        "hospitals": hospitals,
        "hospital_mean": hospital_mean,
        "hospital_30": hospital_30,
        "hospital_90": hospital_90,
        "county_mean": county_mean,
        "county_30": county_30,
        "county_stock_total": county_stock_total,
        "county_pressure": county_stock_pressure,
        "bank_count": bank_counts,
        "blood_type_mean": blood_type_mean,
        "blood_type_30": blood_type_30,
        "requests": request_counters["requests"],
        "by_hospital_30": request_counters["by_hospital_30"],
        "by_hospital_90": request_counters["by_hospital_90"],
        "by_county_30": request_counters["by_county_30"],
        "by_type_30": request_counters["by_type_30"],
        "by_type_90": request_counters["by_type_90"],
    }


def _data_fingerprint() -> str:
    payload = {
        "hospital_count": Hospital.query.count(),
        "blood_request_count": BloodRequest.query.count(),
        "blood_bank_count": BloodBank.query.count(),
        "blood_bank_stock_count": BloodBankStock.query.count(),
        "donation_count": DonationRecord.query.count(),
        "latest_request": _timestamp_or_empty(db.session.query(func.max(BloodRequest.created_at)).scalar()),
        "latest_stock": _timestamp_or_empty(db.session.query(func.max(BloodBankStock.last_updated)).scalar()),
        "latest_donation": _timestamp_or_empty(db.session.query(func.max(DonationRecord.confirmed_at)).scalar()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _timestamp_or_empty(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value or "")


def _load_cached_bundle() -> dict[str, Any] | None:
    bundle_path = _bundle_path()
    meta_path = _meta_path()
    if not bundle_path.exists() or not meta_path.exists():
        return None
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            meta = json.load(handle)
        with bundle_path.open("rb") as handle:
            bundle = pickle.load(handle)
        if meta.get("fingerprint") != bundle.get("fingerprint"):
            return None
        bundle["meta"] = meta
        return bundle
    except Exception:
        return None


def _save_bundle(bundle: dict[str, Any]) -> None:
    try:
        with _bundle_path().open("wb") as handle:
            pickle.dump(bundle, handle)
        with _meta_path().open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "fingerprint": bundle["fingerprint"],
                    "trained_at": bundle["trained_at"],
                    "training_rows": bundle["stats"].get("training_rows", 0),
                    "train_rows": bundle["stats"].get("train_rows", 0),
                    "validation_rows": bundle["stats"].get("validation_rows", 0),
                    "selected_model": bundle["stats"].get("selected_model"),
                    "sklearn_available": bundle["sklearn_available"],
                },
                handle,
                indent=2,
                sort_keys=True,
            )
    except Exception:
        pass


def _build_bundle(force_retrain: bool = False) -> dict[str, Any]:
    fingerprint = _data_fingerprint()
    if not force_retrain:
        cached = _load_cached_bundle()
        if cached and cached.get("fingerprint") == fingerprint:
            return cached

    stats = _training_stats()
    training_rows = _build_training_rows()
    training_rows.sort(key=lambda item: (item["created_at"], item["request_id"]))
    train_rows, validation_rows = _split_train_validation(training_rows)
    model_selection = _select_best_model(train_rows, validation_rows)

    actual_targets = [float(row["target"]) for row in training_rows]
    global_mean = sum(actual_targets) / len(actual_targets) if actual_targets else 4.0
    stats["global_mean"] = global_mean
    stats["training_rows"] = len(training_rows)
    stats["validation_rows"] = len(validation_rows)
    stats["train_rows"] = len(train_rows)
    stats["candidate_models"] = model_selection.get("evaluated_models", [])
    stats["selected_model"] = model_selection["name"]
    stats["selected_model_mae"] = model_selection.get("mae")
    stats["selected_model_rmse"] = model_selection.get("rmse")
    stats["selected_model_mape"] = model_selection.get("mape")

    bundle = {
        "fingerprint": fingerprint,
        "trained_at": datetime.utcnow().isoformat(),
        "sklearn_available": SKLEARN_AVAILABLE,
        "model_selection": model_selection,
        "stats": stats,
    }
    _save_bundle(bundle)
    return bundle


def _forecast_rows_for_hospital(bundle: dict[str, Any], hospital: Hospital, horizon_days: int = HORIZON_DAYS) -> list[dict[str, Any]]:
    stats = bundle.get("stats", {})
    request_counters = _request_counters()
    recent_30 = request_counters["by_hospital_30"].get(hospital.id, 0)
    recent_90 = request_counters["by_hospital_90"].get(hospital.id, 0)
    county = (hospital.county or "Unknown").strip() or "Unknown"
    county_stock_total = stats.get("county_stock_total", {}).get(county, 0)
    county_pressure = stats.get("county_pressure", {}).get(county, 1.0)
    recent_type_counts = request_counters["by_type_30"].get(hospital.id, Counter())
    recent_type_90 = request_counters["by_type_90"].get(hospital.id, Counter())
    today = datetime.utcnow()

    daily_totals: list[dict[str, Any]] = []
    by_blood_type: dict[str, list[dict[str, Any]]] = {blood_type: [] for blood_type in BLOOD_TYPES}

    for offset in range(horizon_days):
        moment = today + timedelta(days=offset)
        daily_sum = 0.0
        for blood_type in BLOOD_TYPES:
            feature_row = {
                "hospital_id": f"hospital-{hospital.id}",
                "county": county,
                "blood_type": blood_type,
                "urgency_level": "urgent" if blood_type in {"O-", "O+"} and moment.weekday() >= 4 else "normal",
                "day_of_week_name": _day_name(moment),
                "month_name": _month_name(moment),
                "is_weekend": int(moment.weekday() >= 5),
                "holiday_flag": _holiday_flag(moment),
                "recent_hospital_requests_30d": recent_30,
                "recent_hospital_requests_90d": recent_90,
                "recent_county_requests_30d": stats.get("county_30", {}).get(county, 0),
                "recent_blood_type_requests_30d": recent_type_counts.get(blood_type, 0),
                "recent_blood_type_requests_90d": recent_type_90.get(blood_type, 0),
                "county_stock_total": county_stock_total,
                "county_stock_pressure": county_pressure,
                "bank_count_in_county": stats.get("bank_count", {}).get(county, 0),
                "source": "forecast",
            }
            prediction = round(_predict_pipeline(bundle.get("model_selection", {}).get("pipeline"), feature_row, stats), 2)
            daily_sum += prediction
            by_blood_type[blood_type].append({
                "date": moment.date().isoformat(),
                "predicted_units": prediction,
            })
        daily_totals.append({"date": moment.date().isoformat(), "predicted_units": round(daily_sum, 2)})

    blood_type_summary = []
    for blood_type, series in by_blood_type.items():
        values = [item["predicted_units"] for item in series]
        blood_type_summary.append(
            {
                "blood_type": blood_type,
                "average_units": round(sum(values) / len(values), 2) if values else 0.0,
                "peak_units": round(max(values), 2) if values else 0.0,
                "series": series,
            }
        )
    blood_type_summary.sort(key=lambda item: item["average_units"], reverse=True)

    return {
        "hospital": {
            "id": hospital.id,
            "name": hospital.name,
            "county": hospital.county,
        },
        "horizon_days": horizon_days,
        "daily_totals": daily_totals,
        "blood_type_summary": blood_type_summary,
        "training_summary": {
            "trained_at": bundle["trained_at"],
            "sklearn_available": bundle["sklearn_available"],
            "train_rows": bundle["stats"].get("train_rows", 0),
            "validation_rows": bundle["stats"].get("validation_rows", 0),
            "training_rows": bundle["stats"].get("training_rows", 0),
            "candidate_models": bundle["stats"].get("candidate_models", []),
            "selected_model": bundle["stats"].get("selected_model"),
            "selected_model_mae": bundle["stats"].get("selected_model_mae"),
            "selected_model_rmse": bundle["stats"].get("selected_model_rmse"),
            "selected_model_mape": bundle["stats"].get("selected_model_mape"),
        },
        "refresh_policy": "Refreshes automatically when request, stock, or donation data changes.",
        "is_operational": True,
    }


def get_hospital_forecast(hospital: Hospital | None, horizon_days: int = HORIZON_DAYS) -> dict[str, Any]:
    if not hospital:
        return {
            "hospital": None,
            "daily_totals": [],
            "blood_type_summary": [],
            "training_summary": {"trained_at": None, "sklearn_available": SKLEARN_AVAILABLE, "train_rows": 0, "validation_rows": 0, "training_rows": 0, "candidate_models": [], "selected_model": None, "selected_model_mae": None, "selected_model_rmse": None, "selected_model_mape": None},
            "refresh_policy": "Refreshes automatically when request, stock, or donation data changes.",
            "is_operational": True,
        }
    bundle = _build_bundle()
    return _forecast_rows_for_hospital(bundle, hospital, horizon_days=horizon_days)


def get_national_forecast_summary(horizon_days: int = 7) -> dict[str, Any]:
    bundle = _build_bundle()
    hospitals = Hospital.query.order_by(Hospital.id.asc()).all()
    daily_totals: defaultdict[str, float] = defaultdict(float)
    county_totals: defaultdict[str, float] = defaultdict(float)

    for hospital in hospitals:
        forecast = _forecast_rows_for_hospital(bundle, hospital, horizon_days=horizon_days)
        county = forecast["hospital"]["county"] if forecast["hospital"] else "Unknown"
        county_totals[county] += sum(item["predicted_units"] for item in forecast["daily_totals"])
        for item in forecast["daily_totals"]:
            daily_totals[item["date"]] += item["predicted_units"]

    top_counties = [
        {"county": county, "predicted_units": round(value, 2)}
        for county, value in sorted(county_totals.items(), key=lambda item: item[1], reverse=True)[:8]
    ]

    return {
        "daily_totals": [{"date": date_key, "predicted_units": round(value, 2)} for date_key, value in sorted(daily_totals.items())],
        "top_counties": top_counties,
        "training_summary": {
            "trained_at": bundle["trained_at"],
            "sklearn_available": bundle["sklearn_available"],
            "train_rows": bundle["stats"].get("train_rows", 0),
            "validation_rows": bundle["stats"].get("validation_rows", 0),
            "training_rows": bundle["stats"].get("training_rows", 0),
            "candidate_models": bundle["stats"].get("candidate_models", []),
            "selected_model": bundle["stats"].get("selected_model"),
            "selected_model_mae": bundle["stats"].get("selected_model_mae"),
            "selected_model_rmse": bundle["stats"].get("selected_model_rmse"),
            "selected_model_mape": bundle["stats"].get("selected_model_mape"),
        },
        "refresh_policy": "Refreshes automatically when request, stock, or donation data changes.",
        "is_operational": True,
    }


def _county_status(stock_units: int, request_units_30d: int, pressure: float) -> tuple[str, str]:
    if stock_units <= 0 or pressure >= 2.0:
        return "critical", "red"
    if stock_units < 15 or pressure >= 1.0:
        return "watch", "amber"
    return "healthy", "green"


def get_county_map_data() -> dict[str, Any]:
    geojson = load_county_geojson()
    if not geojson.get("features"):
        return {
            "type": "FeatureCollection",
            "features": [],
            "summary": [],
            "legend": [
                {"status": "healthy", "label": "Healthy", "color": "green"},
                {"status": "watch", "label": "Watch", "color": "amber"},
                {"status": "critical", "label": "Critical", "color": "red"},
            ],
        }

    stock_by_county, bank_counts = _stock_by_county()
    counters = _request_counters()
    request_by_county = counters["by_county_30"]
    county_features = []
    summary_rows = []

    for feature in geojson["features"]:
        properties = feature.setdefault("properties", {})
        county = (properties.get("county") or "").strip()
        stock_units = _safe_int(stock_by_county.get(county, 0))
        request_units = _safe_int(request_by_county.get(county, 0))
        pressure = round(request_units / max(stock_units, 1), 3)
        status, status_color = _county_status(stock_units, request_units, pressure)
        top_types = Counter()
        for stock in BloodBankStock.query.join(BloodBank).filter(BloodBank.county == county).all():
            top_types[stock.blood_type] += _safe_int(stock.units_available)
        properties.update(
            {
                "stock_units": stock_units,
                "request_units_30d": request_units,
                "bank_count": bank_counts.get(county, 0),
                "pressure": pressure,
                "status": status,
                "status_color": status_color,
                "top_blood_types": [name for name, _ in top_types.most_common(3)],
            }
        )
        summary_rows.append(
            {
                "county": county,
                "stock_units": stock_units,
                "request_units_30d": request_units,
                "pressure": pressure,
                "status": status,
                "bank_count": bank_counts.get(county, 0),
                "top_blood_types": [name for name, _ in top_types.most_common(3)],
            }
        )
        county_features.append(feature)

    summary_rows.sort(key=lambda item: (item["status"] == "critical", item["pressure"]), reverse=True)

    return {
        "type": "FeatureCollection",
        "features": county_features,
        "summary": summary_rows,
        "legend": [
            {"status": "healthy", "label": "Healthy", "color": "green"},
            {"status": "watch", "label": "Watch", "color": "amber"},
            {"status": "critical", "label": "Critical", "color": "red"},
        ],
    }


def load_county_geojson() -> dict[str, Any]:
    path = _geojson_path()
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {"type": "FeatureCollection", "features": []}


def get_county_geojson() -> dict[str, Any]:
    return load_county_geojson()
