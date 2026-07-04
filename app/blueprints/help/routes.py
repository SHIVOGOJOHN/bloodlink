from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

from app.utils.auth import role_required

help_bp = Blueprint("help", __name__, url_prefix="/help")


@help_bp.route("/")
def index():
    # Redirect authenticated users to their role-specific help page
    if current_user.is_authenticated:
        role = current_user.role
        if role == "hospital_staff":
            return redirect(url_for("help.hospital"))
        if role == "donor":
            return redirect(url_for("help.donor"))
        if role == "bloodbank_staff":
            return redirect(url_for("help.bloodbank"))
        if role == "admin":
            return redirect(url_for("help.admin"))
    # Generic public help
    return render_template("help/index.html")


@help_bp.route("/hospital")
@role_required("hospital_staff")
def hospital():
    return render_template("help/hospital_help.html")


@help_bp.route("/donor")
@role_required("donor")
def donor():
    return render_template("help/donor_help.html")


@help_bp.route("/bloodbank")
@role_required("bloodbank_staff")
def bloodbank():
    return render_template("help/bloodbank_help.html")


@help_bp.route("/admin")
@role_required("admin")
def admin():
    return render_template("help/admin_help.html")
