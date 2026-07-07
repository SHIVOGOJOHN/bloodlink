from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.models import BloodRequest, DonationRecord, Donor
from app.utils.auth import role_required
from app.utils.loyalty import get_badges_for_donation_count, get_next_badge
from app.extensions import db


donor_bp = Blueprint("donor", __name__, url_prefix="/donor")


@donor_bp.route("/")
@role_required("donor")
def dashboard():
    donor = current_user.donor
    if not donor:
        return redirect(url_for("donor.profile_setup"))

    donation_history = DonationRecord.query.filter_by(donor_id=donor.id).order_by(DonationRecord.confirmed_at.desc()).all()
    active_requests = BloodRequest.query.filter_by(status="open").all()

    # Calculate eligibility
    days_since_last = None
    eligible = True
    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        eligible = days_since_last >= 90

    confirmed_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
    badges = get_badges_for_donation_count(confirmed_count)
    next_badge = get_next_badge(confirmed_count)

    return render_template(
        "donor/dashboard.html",
        donor=donor,
        donation_history=donation_history,
        active_requests=active_requests,
        days_since_last=days_since_last,
        eligible=eligible,
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

    # Eligibility check
    from app.utils.matching import is_eligible
    from datetime import date
    eligible, days_since = is_eligible(donor)
    days_left = max(0, 90 - days_since) if days_since is not None else 0

    # Badges check
    donation_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
    badges = get_badges_for_donation_count(donation_count)
    next_badge = get_next_badge(donation_count)

    return render_template(
        "donor/profile.html",
        donor=donor,
        eligible=eligible,
        days_left=days_left,
        donation_count=donation_count,
        badges=badges,
        next_badge=next_badge,
    )

