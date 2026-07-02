from datetime import datetime, date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import BloodBankStock, BloodRequest, Donor, DonationRecord, Hospital
from app.utils.auth import role_required
from app.utils.matching import rank_donors_for_request

hospital_bp = Blueprint("hospital", __name__, url_prefix="/hospital")


@hospital_bp.route("/", methods=["GET", "POST"])
@role_required("hospital_staff")
def dashboard():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    if request.method == "POST":
        blood_type = request.form.get("blood_type", "").strip().upper()
        try:
            units_needed = int(request.form.get("units_needed", 0) or 0)
        except ValueError:
            units_needed = 0
        urgency_level = request.form.get("urgency_level", "urgent")

        if not blood_type or units_needed <= 0:
            flash("Please complete the blood request form fully.", "danger")
        else:
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
                flash("Blood request created successfully.", "success")
            except SQLAlchemyError as exc:
                db.session.rollback()
                flash(f"Unable to save the request right now: {exc}", "warning")
            return redirect(url_for("hospital.dashboard"))

    try:
        requests_list = BloodRequest.query.filter_by(hospital_id=hospital.id).order_by(BloodRequest.created_at.desc()).all()
        stock = BloodBankStock.query.all()
    except SQLAlchemyError:
        requests_list = []
        stock = []

    matching_results = []
    if requests_list:
        # Match donors for the most recent open request
        open_requests = [r for r in requests_list if r.status == "open"]
        if open_requests:
            latest_request = open_requests[0]
            matching_results = rank_donors_for_request(latest_request.blood_type, hospital.county)

    return render_template(
        "hospital/dashboard.html",
        hospital=hospital,
        requests=requests_list,
        stock=stock,
        matching_results=matching_results,
    )


@hospital_bp.route("/profile-setup", methods=["GET", "POST"])
@role_required("hospital_staff")
def profile_setup():
    hospital = current_user.hospital

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        county = request.form.get("county", "").strip()
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
            hospital.contact_phone = contact_phone
            hospital.profile_pic_url = profile_pic_url
            hospital.bio = bio
        else:
            hospital = Hospital(
                user_id=current_user.id,
                name=name,
                county=county,
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
        
    donor = Donor.query.get(donor_id)
    blood_req = BloodRequest.query.get(blood_request_id)
    
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
    
    # Update the request status
    blood_req.status = "fulfilled"
    
    db.session.add(donation)
    db.session.commit()
    
    flash(f"Donation confirmed for {donor.name}. The request has been marked as fulfilled.", "success")
    return redirect(url_for("hospital.dashboard"))


@hospital_bp.route("/profile")
@role_required("hospital_staff")
def profile():
    hospital = current_user.hospital
    if not hospital:
        return redirect(url_for("hospital.profile_setup"))

    return render_template("hospital/profile.html", hospital=hospital)

