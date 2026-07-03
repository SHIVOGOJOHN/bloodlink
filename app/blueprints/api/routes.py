from flask import Blueprint, abort, jsonify

from app.extensions import db
from app.models import Hospital
from app.utils.forecast import get_hospital_forecast, get_national_forecast_summary

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/forecast/national")
def national_forecast():
    return jsonify(get_national_forecast_summary())


@api_bp.route("/forecast/hospital/<int:hospital_id>")
def hospital_forecast(hospital_id):
    hospital = db.session.get(Hospital, hospital_id)
    if not hospital:
        abort(404)
    return jsonify(get_hospital_forecast(hospital))
