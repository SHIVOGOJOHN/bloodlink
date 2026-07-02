from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.models import BloodRequest, DonationRecord, Donor
from app.utils.auth import role_required
from app.extensions import db


donor_bp = Blueprint("donor", __name__, url_prefix="/donor")


@donor_bp.route("/")
@role_required("donor")
def dashboard():
    donor = current_user.donor
    if not donor:
        return redirect(url_for("donor.profile_setup"))

    donation_history = DonationRecord.query.filter_by(donor_id=donor.id).all()
    active_requests = BloodRequest.query.filter_by(status="open").all()
    
    # Calculate eligibility
    days_since_last = None
    eligible = True
    if donor.last_donation_date:
        days_since_last = (date.today() - donor.last_donation_date).days
        eligible = days_since_last >= 90
    
    # Calculate badges
    confirmed_donations = [d for d in donation_history if d.status == "confirmed"]
    badges = []
    if len(confirmed_donations) >= 1:
        badges.append("First Drop")
    if len(confirmed_donations) >= 5:
        badges.append("Life Saver")
    if len(confirmed_donations) >= 10:
        badges.append("Blood Hero")

    return render_template(
        "donor/dashboard.html",
        donor=donor,
        donation_history=donation_history,
        active_requests=active_requests,
        days_since_last=days_since_last,
        eligible=eligible,
        badges=badges,
    )


@donor_bp.route("/profile-setup", methods=["GET", "POST"])
@role_required("donor")
def profile_setup():
    if current_user.donor:
        return redirect(url_for("donor.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        county = request.form.get("county", "").strip()
        blood_type = request.form.get("blood_type", "").strip()
        last_donation_date_str = request.form.get("last_donation_date", "").strip()
        consent_given = request.form.get("consent_given") == "yes"

        if not name or not phone or not county or not blood_type:
            flash("Please fill in all required fields.", "warning")
            return render_template("donor/profile_setup.html")
            
        if not consent_given:
            flash("You must agree to the data privacy policy to continue.", "danger")
            return render_template("donor/profile_setup.html")

        last_donation_date = None
        if last_donation_date_str:
            try:
                last_donation_date = datetime.strptime(last_donation_date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format. Use YYYY-MM-DD.", "warning")
                return render_template("donor/profile_setup.html")

        donor = Donor(
            user_id=current_user.id,
            name=name,
            phone=phone,
            county=county,
            blood_type=blood_type,
            last_donation_date=last_donation_date,
            consent_given=True,
            consent_timestamp=datetime.utcnow()
        )
        db.session.add(donor)
        db.session.commit()
        
        flash("Profile setup complete! Welcome to your dashboard.", "success")
        return redirect(url_for("donor.dashboard"))

    # If the user already provided full name and phone during registration, use them as defaults
    default_name = current_user.full_name or ""
    default_phone = current_user.phone or ""

    return render_template("donor/profile_setup.html", default_name=default_name, default_phone=default_phone)

