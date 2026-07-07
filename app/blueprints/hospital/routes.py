from datetime import datetime, date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import BloodBank, BloodBankStock, BloodRequest, Donor, DonationRecord, Hospital
from app.utils.auth import role_required
from app.utils.loyalty import calculate_reward_for_donation
from app.utils.notifications import (
    notify_new_blood_request,
    notify_bank_of_request,
    notify_donor_donation_confirmed,
    notify_request_receipt_confirmed,
)
from io import StringIO

from app.utils.forecast import (
    get_hospital_forecast,
    invalidate_forecast_cache,
    retrain_forecast_models,
    upload_training_csv_stream,
)
from app.utils.github_cdn import upload_training_csv
from app.utils.matching import calculate_haversine_distance, get_distance, rank_donors_for_request

hospital_bp = Blueprint("hospital", __name__, url_prefix="/hospital")


def _estimate_blood_bank_distance(hospital: Hospital, bank: BloodBank) -> float | None:
    """Estimate proximity in kilometers from a hospital to a blood bank."""
    if (
        hospital.latitude is not None and hospital.longitude is not None and
        bank.latitude is not None and bank.longitude is not None
    ):
        return calculate_haversine_distance(
            hospital.latitude,
            hospital.longitude,
            bank.latitude,
            bank.longitude,
        )

    if hospital.ward and bank.ward and hospital.ward.strip().lower() == bank.ward.strip().lower():
        return 2.0

    if (
        hospital.subcounty and bank.subcounty and
        hospital.subcounty.strip().lower() == bank.subcounty.strip().lower()
    ):
        return 4.0

    if hospital.county and bank.county and hospital.county.strip().lower() == bank.county.strip().lower():
        return 10.0

    if hospital.county and bank.county:
        return float(get_distance(hospital.county, bank.county))

    return None


@hospital_bp.route("/", methods=["GET"])
@role_required("hospital_staff")
def dashboard():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    try:
        requests_list = BloodRequest.query.filter_by(hospital_id=hospital.id).order_by(BloodRequest.created_at.desc()).all()
    except SQLAlchemyError:
        requests_list = []

    matching_results = []
    latest_open_request = None
    if requests_list:
        open_requests = [r for r in requests_list if r.status == "open"]
        if open_requests:
            latest_open_request = open_requests[0]
            matching_results = rank_donors_for_request(latest_open_request.blood_type, hospital)

    return render_template(
        "hospital/dashboard.html",
        hospital=hospital,
        requests=requests_list,
        matching_results=matching_results,
        latest_request=latest_open_request,
    )


def _build_hospital_stock_summary(hospital):
    """Return (stock_summary, local_stock, all_stock) for a hospital."""
    all_stock = BloodBankStock.query.all()
    stock_summary: dict = {}
    for s in all_stock:
        bt = s.blood_type
        bank = s.blood_bank
        if bt not in stock_summary:
            stock_summary[bt] = {
                "total": 0,
                "banks": [],
                "local_banks": [],
                "remote_banks": [],
                "local_units": 0,
                "remote_units": 0,
            }
        distance_km = _estimate_blood_bank_distance(hospital, bank) if bank else None
        bank_info = {
            "id": bank.id if bank else None,
            "name": bank.name if bank else "Unknown",
            "county": bank.county if bank else "",
            "units": s.units_available,
            "expiry": s.expiry_date,
            "distance": distance_km,
            "contact_phone": bank.user.phone if bank and bank.user else None,
        }
        stock_summary[bt]["total"] += s.units_available
        stock_summary[bt]["banks"].append(bank_info)

    for blood_type_info in stock_summary.values():
        blood_type_info["banks"].sort(
            key=lambda bank_info: (
                bank_info["distance"] if bank_info["distance"] is not None else float("inf"),
                -bank_info["units"],
                bank_info["name"],
            )
        )
        blood_type_info["local_banks"] = [b for b in blood_type_info["banks"] if b["county"] == hospital.county]
        blood_type_info["remote_banks"] = [b for b in blood_type_info["banks"] if b["county"] != hospital.county]
        blood_type_info["local_units"] = sum(b["units"] for b in blood_type_info["local_banks"])
        blood_type_info["remote_units"] = sum(b["units"] for b in blood_type_info["remote_banks"])

    local_stock = BloodBankStock.query.join(BloodBank).filter(
        BloodBank.county == hospital.county
    ).all()
    return stock_summary, local_stock, all_stock


@hospital_bp.route("/inventory")
@role_required("hospital_staff")
def inventory():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))
    stock_summary, local_stock, all_stock = _build_hospital_stock_summary(hospital)
    forecast_panel = get_hospital_forecast(hospital)
    return render_template("hospital/inventory.html", hospital=hospital, stock_summary=stock_summary, local_stock=local_stock, forecast_panel=forecast_panel)


@hospital_bp.route("/forecast")
@role_required("hospital_staff")
def forecast():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))
    forecast_panel = get_hospital_forecast(hospital)
    return render_template("hospital/forecast.html", hospital=hospital, forecast_panel=forecast_panel)


@hospital_bp.route("/create-request", methods=["GET", "POST"])
@role_required("hospital_staff")
def create_request_page():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))
    # delegate to existing POST handling by reusing bank_request flow when a bank is selected
    blood_type = request.args.get("blood_type", "").strip().upper()
    return render_template("hospital/create_request.html", hospital=hospital, blood_type=blood_type)


@hospital_bp.route("/bank-request/<int:bank_id>", methods=["GET", "POST"])
@role_required("hospital_staff")
def bank_request(bank_id):
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    bank = db.session.get(BloodBank, bank_id)
    if not bank:
        flash("Blood bank not found.", "danger")
        return redirect(url_for("hospital.dashboard"))

    if request.method == "POST":
        blood_type = request.form.get("blood_type", "").strip().upper()
        try:
            units_needed = int(request.form.get("units_needed", 0) or 0)
        except ValueError:
            units_needed = 0
        urgency_level = request.form.get("urgency_level", "urgent")

        if not blood_type or units_needed <= 0:
            flash("Please choose a valid blood type and units needed.", "warning")
            return render_template("hospital/bank_request.html", hospital=hospital, bank=bank, blood_type=blood_type)

        try:
            request_record = BloodRequest(
                hospital_id=hospital.id,
                blood_type=blood_type,
                units_needed=units_needed,
                urgency_level=urgency_level,
                status="open",
            )
            db.session.add(request_record)
            db.session.commit()
            invalidate_forecast_cache()
            bank_notified = notify_bank_of_request(request_record, bank)
            hospital_notified = notify_hospital_request_created(request_record, bank.name)
            status_message = []
            if bank_notified:
                status_message.append("The blood bank has been notified.")
            else:
                status_message.append("The blood bank could not be notified by email; please contact them directly.")
            if hospital_notified:
                status_message.append("A confirmation email was sent to your hospital account.")
            else:
                status_message.append("Hospital confirmation email could not be sent.")
            flash(
                f"Request created for {bank.name}. {' '.join(status_message)}",
                "success" if bank_notified and hospital_notified else "warning",
            )
        except SQLAlchemyError as exc:
            db.session.rollback()
            flash(f"Unable to create a targeted request right now: {exc}", "warning")
        return redirect(url_for("hospital.dashboard"))

    blood_type = request.args.get("blood_type", "").strip().upper()
    return render_template("hospital/bank_request.html", hospital=hospital, bank=bank, blood_type=blood_type)


@hospital_bp.route("/forecast/run", methods=["POST"])
@role_required("hospital_staff")
def run_forecast():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    try:
        retrain_forecast_models(force_retrain=True)
        flash("Forecast rerun completed successfully.", "success")
    except Exception as exc:
        flash("Unable to rerun the forecast now. Please try again later.", "danger")
    return redirect(url_for("hospital.dashboard"))


@hospital_bp.route("/forecast/upload", methods=["POST"])
@role_required("hospital_staff")
def upload_training_data():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    file_storage = request.files.get("training_csv")
    if not file_storage or not file_storage.filename:
        flash("Please choose a training CSV file to upload.", "warning")
        return redirect(url_for("hospital.dashboard"))

    if not file_storage.filename.lower().endswith(".csv"):
        flash("Only CSV files are accepted for training data uploads.", "warning")
        return redirect(url_for("hospital.dashboard"))

    try:
        file_bytes = file_storage.read()
        payload = file_bytes.decode("utf-8-sig")
        uploaded_url = upload_training_csv(file_bytes, file_storage.filename)
        imported_count, existing_count = upload_training_csv_stream(StringIO(payload), hospital)
        if imported_count > 0:
            invalidate_forecast_cache()
            retrain_forecast_models(force_retrain=True)
            flash_msg = f"Uploaded {imported_count} new training rows and refreshed the model."
            if uploaded_url:
                flash_msg += " Training CSV was also mirrored to GitHub."
            else:
                flash_msg += " GitHub mirror was not available."
            flash(flash_msg, "success")
        else:
            flash("The uploaded CSV contained no new training rows; duplicates were ignored.", "info")
    except Exception:
        flash("Failed to process the uploaded CSV file. Ensure it is valid and UTF-8 encoded.", "danger")

    return redirect(url_for("hospital.dashboard"))


@hospital_bp.route("/profile-setup", methods=["GET", "POST"])
@role_required("hospital_staff")
def profile_setup():
    hospital = current_user.hospital

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        county = request.form.get("county", "").strip()
        subcounty = request.form.get("subcounty", "").strip()
        ward = request.form.get("ward", "").strip()
        lat_str = request.form.get("latitude", "").strip()
        lon_str = request.form.get("longitude", "").strip()
        latitude = float(lat_str) if lat_str else None
        longitude = float(lon_str) if lon_str else None
        contact_phone = request.form.get("contact_phone", "").strip()
        bio = request.form.get("bio", "").strip()

        profile_pic_file = request.files.get("profile_pic")
        profile_pic_url = hospital.profile_pic_url if hospital else None
        if profile_pic_file and profile_pic_file.filename:
            import uuid
            ext = profile_pic_file.filename.split(".")[-1]
            fname = f"{uuid.uuid4().hex}.{ext}"
            file_bytes = profile_pic_file.read()
            from app.utils.github_cdn import upload_profile_pic
            uploaded_url = upload_profile_pic(file_bytes, fname)
            if uploaded_url:
                profile_pic_url = uploaded_url

        if not name or not county:
            flash("Please fill in all required fields.", "warning")
            return render_template("hospital/profile_setup.html", hospital=hospital)

        if hospital:
            hospital.name = name
            hospital.county = county
            hospital.subcounty = subcounty
            hospital.ward = ward
            hospital.latitude = latitude
            hospital.longitude = longitude
            hospital.contact_phone = contact_phone
            hospital.profile_pic_url = profile_pic_url
            hospital.bio = bio
        else:
            hospital = Hospital(
                user_id=current_user.id,
                name=name,
                county=county,
                subcounty=subcounty,
                ward=ward,
                latitude=latitude,
                longitude=longitude,
                contact_phone=contact_phone,
                profile_pic_url=profile_pic_url,
                bio=bio,
                created_at=datetime.utcnow()
            )
            db.session.add(hospital)
            
        db.session.commit()
        
        flash("Hospital profile updated successfully!", "success")
        return redirect(url_for("hospital.profile"))

    default_phone = hospital.contact_phone if hospital else (current_user.phone or "")
    default_name = hospital.name if hospital else (current_user.full_name or "")
    return render_template("hospital/profile_setup.html", hospital=hospital, default_phone=default_phone, default_name=default_name)


@hospital_bp.route("/confirm-donation", methods=["POST"])
@role_required("hospital_staff")
def confirm_donation():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    donor_id = request.form.get("donor_id")
    blood_request_id = request.form.get("blood_request_id")
    
    if not donor_id or not blood_request_id:
        flash("Missing donor or request ID.", "danger")
        return redirect(url_for("hospital.dashboard"))
        
    donor = db.session.get(Donor, int(donor_id)) if donor_id else None
    blood_req = db.session.get(BloodRequest, int(blood_request_id)) if blood_request_id else None
    
    if not donor or not blood_req:
        flash("Invalid donor or request.", "danger")
        return redirect(url_for("hospital.dashboard"))
        
    if blood_req.hospital_id != hospital.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hospital.dashboard"))

    # Create the confirmed donation
    donation = DonationRecord(
        donor_id=donor.id,
        hospital_id=hospital.id,
        blood_request_id=blood_req.id,
        blood_type=donor.blood_type,
        status="confirmed",
        confirmed_at=datetime.utcnow(),
        confirmed_by_user_id=current_user.id
    )

    # Update donor's last donation date
    donor.last_donation_date = date.today()

    # Mark the request fulfilled
    blood_req.status = "fulfilled"

    # --- Increment blood bank stock: blood collected goes into inventory ---
    # Find a blood bank in the same county as this hospital; if none, use any.
    bank = BloodBank.query.filter_by(county=hospital.county).first() or BloodBank.query.first()
    if bank:
        stock_item = BloodBankStock.query.filter_by(
            blood_bank_id=bank.id,
            blood_type=donor.blood_type
        ).first()
        if stock_item:
            stock_item.units_available += 1          # 1 donation unit
            stock_item.last_updated = datetime.utcnow()
        else:
            # No stock entry yet for this blood type — create one
            new_stock = BloodBankStock(
                blood_bank_id=bank.id,
                blood_type=donor.blood_type,
                units_available=1,
                last_updated=datetime.utcnow()
            )
            db.session.add(new_stock)

    db.session.add(donation)

    # Reward donor for confirmed donation
    confirmed_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
    points_awarded, unlocked_badges = calculate_reward_for_donation(confirmed_count)
    donor.loyalty_points = (donor.loyalty_points or 0) + points_awarded
    db.session.commit()
    invalidate_forecast_cache()

    badge_text = f" and unlocked {', '.join(unlocked_badges)}" if unlocked_badges else ""
    mail_sent = notify_donor_donation_confirmed(donation, points_awarded=points_awarded, unlocked_badges=unlocked_badges)
    if mail_sent:
        flash(
            f"Donation by {donor.name} confirmed. Blood Bank inventory updated (+1 unit of {donor.blood_type}), {points_awarded} loyalty points awarded{badge_text}, and donor notified by email.",
            "success",
        )
    else:
        flash(
            f"Donation by {donor.name} confirmed. Blood Bank inventory updated (+1 unit of {donor.blood_type}). Donor notification email could not be sent.",
            "warning",
        )
    return redirect(url_for("hospital.dashboard"))


@hospital_bp.route("/requests/<int:request_id>/confirm-receipt", methods=["POST"])
@role_required("hospital_staff")
def confirm_receipt(request_id):
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    request_record = db.session.get(BloodRequest, request_id)
    if not request_record:
        abort(404)
    if request_record.hospital_id != hospital.id:
        flash("Unauthorized request action.", "danger")
        return redirect(url_for("hospital.dashboard"))

    if request_record.status != "dispatched":
        flash("Request is not in dispatched status.", "warning")
        return redirect(url_for("hospital.dashboard"))

    request_record.status = "received"
    db.session.commit()

    mail_sent = notify_request_receipt_confirmed(request_record)
    if mail_sent:
        flash("Blood package receipt confirmed and blood bank notified by email.", "success")
    else:
        flash("Blood package receipt confirmed. Could not send notification email to the blood bank.", "warning")
    return redirect(url_for("hospital.dashboard"))


@hospital_bp.route("/profile")

@role_required("hospital_staff")
def profile():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    return render_template("hospital/profile.html", hospital=hospital)

