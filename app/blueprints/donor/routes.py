from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.models import BloodRequest, DonationRecord, Donor, Hospital, ReimbursementRequest
from app.utils.auth import role_required
from app.utils.loyalty import (
    get_badges_for_donation_count,
    get_next_badge,
    get_badge_progress,
    get_certificates_for_donation_count,
)
from app.utils.matching import calculate_haversine_distance, get_distance, is_compatible, is_eligible
from app.extensions import db


donor_bp = Blueprint("donor", __name__, url_prefix="/donor")


def _normalize_location(value: str | None) -> str:
    return str(value or "").strip().lower()


def _compute_distance(donor: Donor, hospital: Hospital) -> float | None:
    if (
        donor.latitude is not None and donor.longitude is not None and
        hospital.latitude is not None and hospital.longitude is not None
    ):
        return calculate_haversine_distance(
            donor.latitude,
            donor.longitude,
            hospital.latitude,
            hospital.longitude,
        )

    donor_ward = _normalize_location(donor.ward)
    hospital_ward = _normalize_location(hospital.ward)
    if donor_ward and hospital_ward and donor_ward == hospital_ward:
        return 2.0

    donor_subcounty = _normalize_location(donor.subcounty)
    hospital_subcounty = _normalize_location(hospital.subcounty)
    if donor_subcounty and hospital_subcounty and donor_subcounty == hospital_subcounty:
        return 4.0

    donor_county = _normalize_location(donor.county)
    hospital_county = _normalize_location(hospital.county)
    if donor_county and hospital_county and donor_county == hospital_county:
        return 10.0

    if donor_county and hospital_county:
        return float(get_distance(donor_county.title(), hospital_county.title()))

    return None


def _travel_time_label(distance_km: float | None) -> str:
    if distance_km is None:
        return "Unknown"
    if distance_km <= 5:
        return "≈ 10 min"
    if distance_km <= 15:
        return "≈ 20 min"
    if distance_km <= 30:
        return "≈ 35 min"
    if distance_km <= 60:
        return "≈ 1 hr"
    return "1+ hr"


def _prepare_nearby_requests(donor: Donor, requests: list[BloodRequest]) -> list[dict]:
    enriched: list[dict] = []
    for req in requests:
        hospital = req.hospital
        if not hospital:
            continue
        distance_km = _compute_distance(donor, hospital)
        enriched.append({
            "id": req.id,
            "hospital": hospital,
            "blood_type": req.blood_type,
            "units_needed": req.units_needed,
            "urgency_level": req.urgency_level or "normal",
            "match": is_compatible(donor.blood_type, req.blood_type),
            "distance": distance_km,
            "distance_display": f"{distance_km:.1f} km" if distance_km is not None else "Unknown distance",
            "travel_time": _travel_time_label(distance_km),
            "created_at": req.created_at,
            "contact_phone": hospital.contact_phone,
        })

    enriched.sort(
        key=lambda item: (
            0 if item["urgency_level"] == "urgent" else 1,
            item["distance"] if item["distance"] is not None else float("inf"),
            item["created_at"] or datetime.min,
        )
    )
    return enriched


@donor_bp.route("/")
@role_required("donor")
def dashboard():
    donor = current_user.donor
    if not donor:
        return redirect(url_for("donor.profile_setup"))

    donation_history = DonationRecord.query.filter_by(donor_id=donor.id).order_by(DonationRecord.confirmed_at.desc()).all()
    active_requests = BloodRequest.query.filter_by(status="open").all()

    days_since_last = None
    eligible = True
    next_eligible_date = None
    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        eligible = days_since_last >= 90
        if not eligible:
            next_eligible_date = donor.last_donation_date + timedelta(days=90)
    else:
        next_eligible_date = date.today()

    confirmed_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
    badges = get_badges_for_donation_count(confirmed_count)
    next_badge = get_next_badge(confirmed_count)
    badge_progress = get_badge_progress(confirmed_count)
    certificates = get_certificates_for_donation_count(confirmed_count, donor.blood_type)
    reimbursements = ReimbursementRequest.query.filter_by(donor_id=donor.id).order_by(ReimbursementRequest.requested_at.desc()).limit(5).all()

    nearby_requests = _prepare_nearby_requests(donor, active_requests)
    featured_requests = [req for req in nearby_requests if req["match"]][:3] or nearby_requests[:3]

    return render_template(
        "donor/dashboard.html",
        donor=donor,
        donation_history=donation_history,
        featured_requests=featured_requests,
        nearby_requests_count=len(nearby_requests),
        days_since_last=days_since_last,
        eligible=eligible,
        next_eligible_date=next_eligible_date,
        badges=badges,
        next_badge=next_badge,
        badge_progress=badge_progress,
        certificates=certificates,
        reimbursements=reimbursements,
        confirmed_count=confirmed_count,
    )


@donor_bp.route("/nearby-requests")
@role_required("donor")
def nearby_requests():
    donor = current_user.donor
    if not donor:
        return redirect(url_for("donor.profile_setup"))

    active_requests = BloodRequest.query.filter_by(status="open").all()

    days_since_last = None
    eligible = True
    next_eligible_date = None
    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        eligible = days_since_last >= 90
        if not eligible:
            next_eligible_date = donor.last_donation_date + timedelta(days=90)
    else:
        next_eligible_date = date.today()

    confirmed_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
    badges = get_badges_for_donation_count(confirmed_count)
    next_badge = get_next_badge(confirmed_count)

    nearby_requests = _prepare_nearby_requests(donor, active_requests)

    return render_template(
        "donor/nearby_requests.html",
        donor=donor,
        requests=nearby_requests,
        days_since_last=days_since_last,
        eligible=eligible,
        next_eligible_date=next_eligible_date,
        badges=badges,
        next_badge=next_badge,
        confirmed_count=confirmed_count,
    )


@donor_bp.route("/profile-setup", methods=["GET", "POST"])
@role_required("donor")
def profile_setup():
    donor = current_user.donor

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        county = request.form.get("county", "").strip()
        blood_type = request.form.get("blood_type", "").strip()
        last_donation_date_str = request.form.get("last_donation_date", "").strip()
        consent_given = request.form.get("consent_given") == "yes"
        bio = request.form.get("bio", "").strip()

        subcounty = request.form.get("subcounty", "").strip()
        ward = request.form.get("ward", "").strip()
        lat_str = request.form.get("latitude", "").strip()
        lon_str = request.form.get("longitude", "").strip()
        latitude = float(lat_str) if lat_str else None
        longitude = float(lon_str) if lon_str else None

        profile_pic_file = request.files.get("profile_pic")
        profile_pic_url = donor.profile_pic_url if donor else None
        if profile_pic_file and profile_pic_file.filename:
            import uuid
            ext = profile_pic_file.filename.split(".")[-1]
            fname = f"{uuid.uuid4().hex}.{ext}"
            file_bytes = profile_pic_file.read()
            from app.utils.github_cdn import upload_profile_pic
            uploaded_url = upload_profile_pic(file_bytes, fname)
            if uploaded_url:
                profile_pic_url = uploaded_url

        if not name or not phone or not county or not blood_type:
            flash("Please fill in all required fields.", "warning")
            return render_template("donor/profile_setup.html", donor=donor)
            
        if not donor and not consent_given:
            flash("You must agree to the data privacy policy to continue.", "danger")
            return render_template("donor/profile_setup.html", donor=donor)

        last_donation_date = None
        if last_donation_date_str:
            try:
                last_donation_date = datetime.strptime(last_donation_date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format. Use YYYY-MM-DD.", "warning")
                return render_template("donor/profile_setup.html", donor=donor)

        if donor:
            donor.name = name
            donor.phone = phone
            donor.county = county
            donor.subcounty = subcounty
            donor.ward = ward
            donor.latitude = latitude
            donor.longitude = longitude
            donor.blood_type = blood_type
            donor.last_donation_date = last_donation_date
            donor.profile_pic_url = profile_pic_url
            donor.bio = bio
        else:
            donor = Donor(
                user_id=current_user.id,
                name=name,
                phone=phone,
                county=county,
                subcounty=subcounty,
                ward=ward,
                latitude=latitude,
                longitude=longitude,
                blood_type=blood_type,
                last_donation_date=last_donation_date,
                consent_given=True,
                consent_timestamp=datetime.utcnow(),
                profile_pic_url=profile_pic_url,
                bio=bio
            )
            db.session.add(donor)
            
        db.session.commit()
        
        flash("Profile updated successfully!", "success")
        return redirect(url_for("donor.profile"))

    # If the user already provided full name and phone during registration, use them as defaults
    default_name = donor.name if donor else (current_user.full_name or "")
    default_phone = donor.phone if donor else (current_user.phone or "")

    return render_template("donor/profile_setup.html", donor=donor, default_name=default_name, default_phone=default_phone)


@donor_bp.route("/profile")
@role_required("donor")
def profile():
    donor = current_user.donor
    if not donor:
        return redirect(url_for("donor.profile_setup"))

    eligible, days_since = is_eligible(donor)
    days_left = max(0, 90 - days_since) if days_since is not None else 0

    donation_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
    badges = get_badges_for_donation_count(donation_count)
    next_badge = get_next_badge(donation_count)
    badge_progress = get_badge_progress(donation_count)
    certificates = get_certificates_for_donation_count(donation_count, donor.blood_type)
    reimbursements = ReimbursementRequest.query.filter_by(donor_id=donor.id).order_by(ReimbursementRequest.requested_at.desc()).limit(5).all()

    return render_template(
        "donor/profile.html",
        donor=donor,
        eligible=eligible,
        days_left=days_left,
        donation_count=donation_count,
        badges=badges,
        next_badge=next_badge,
        badge_progress=badge_progress,
        certificates=certificates,
        reimbursements=reimbursements,
    )

