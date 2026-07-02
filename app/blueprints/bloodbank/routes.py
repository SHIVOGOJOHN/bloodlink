from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import BloodBank, BloodBankStock, BloodRequest
from app.utils.auth import role_required

bloodbank_bp = Blueprint("bloodbank", __name__, url_prefix="/bloodbank")


@bloodbank_bp.route("/")
@role_required("bloodbank_staff")
def dashboard():
    bloodbank = current_user.bloodbank
    if not bloodbank:
        return redirect(url_for("bloodbank.profile_setup"))

    stock = BloodBankStock.query.filter_by(blood_bank_id=bloodbank.id).order_by(BloodBankStock.last_updated.desc()).all()
    requests_list = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    return render_template("bloodbank/dashboard.html", bloodbank=bloodbank, stock=stock, requests=requests_list)


@bloodbank_bp.route("/profile-setup", methods=["GET", "POST"])
@role_required("bloodbank_staff")
def profile_setup():
    bloodbank = current_user.bloodbank

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        county = request.form.get("county", "").strip()
        bio = request.form.get("bio", "").strip()

        profile_pic_file = request.files.get("profile_pic")
        profile_pic_url = bloodbank.profile_pic_url if bloodbank else None
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
            return render_template("bloodbank/profile_setup.html", bloodbank=bloodbank)

        if bloodbank:
            bloodbank.name = name
            bloodbank.county = county
            bloodbank.profile_pic_url = profile_pic_url
            bloodbank.bio = bio
        else:
            bloodbank = BloodBank(
                user_id=current_user.id,
                name=name,
                county=county,
                profile_pic_url=profile_pic_url,
                bio=bio,
                created_at=datetime.utcnow()
            )
            db.session.add(bloodbank)
            
        db.session.commit()
        
        flash("Blood bank profile updated successfully!", "success")
        return redirect(url_for("bloodbank.profile"))

    default_name = bloodbank.name if bloodbank else (current_user.full_name or "")
    return render_template("bloodbank/profile_setup.html", bloodbank=bloodbank, default_name=default_name)


@bloodbank_bp.route("/stock", methods=["POST"])
@role_required("bloodbank_staff")
def update_stock():
    bloodbank = current_user.bloodbank
    if not bloodbank:
        return redirect(url_for("bloodbank.profile_setup"))

    blood_type = request.form.get("blood_type", "").strip().upper()
    units_available = request.form.get("units_available", "0").strip()

    if not blood_type:
        flash("Blood type is required.", "danger")
        return redirect(url_for("bloodbank.dashboard"))

    stock_item = BloodBankStock.query.filter_by(blood_type=blood_type, blood_bank_id=bloodbank.id).first()
    if stock_item is None:
        stock_item = BloodBankStock(blood_bank_id=bloodbank.id, blood_type=blood_type)
        db.session.add(stock_item)

    stock_item.units_available = int(units_available)
    stock_item.last_updated = datetime.utcnow()
    
    expiry_date_str = request.form.get("expiry_date", "").strip()
    if expiry_date_str:
        try:
            stock_item.expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
            
    db.session.commit()
    flash("Stock updated successfully.", "success")
    return redirect(url_for("bloodbank.dashboard"))


@bloodbank_bp.route("/requests/<int:request_id>/fulfill", methods=["POST"])
@role_required("bloodbank_staff")
def fulfill_request(request_id):
    if not current_user.bloodbank:
        return redirect(url_for("bloodbank.profile_setup"))
        
    request_record = BloodRequest.query.get_or_404(request_id)
    units_fulfilled = request.form.get("units_fulfilled", request_record.units_needed)
    request_record.status = "fulfilled"
    request_record.units_needed = max(0, int(units_fulfilled))
    db.session.commit()
    flash("Request marked as fulfilled.", "success")
    return redirect(url_for("bloodbank.dashboard"))


@bloodbank_bp.route("/profile")
@role_required("bloodbank_staff")
def profile():
    bloodbank = current_user.bloodbank
    if not bloodbank:
        return redirect(url_for("bloodbank.profile_setup"))

    return render_template("bloodbank/profile.html", bloodbank=bloodbank)
