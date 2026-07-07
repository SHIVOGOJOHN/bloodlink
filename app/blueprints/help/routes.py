from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.utils.auth import role_required
from app.utils.notifications import send_email_notification

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


@help_bp.route("/contact", methods=["POST"])
def contact():
    subject = request.form.get("subject", "").strip()
    message_text = request.form.get("message", "").strip()
    redirect_to = request.form.get("redirect_to") or url_for("help.index")

    if not subject or not message_text:
        flash("Please enter both a subject and a message before sending support.", "warning")
        return redirect(redirect_to)

    recipient = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not recipient:
        flash("Support email is not configured. Please contact your administrator directly.", "danger")
        return redirect(redirect_to)

    sender_email = current_user.email if current_user.is_authenticated else None
    reply_to = sender_email if sender_email else None
    user_identity = current_user.full_name or current_user.email if current_user.is_authenticated else "Guest user"
    user_role = current_user.role if current_user.is_authenticated else "guest"
    message_body = (
        f"Support request from {user_identity} ({user_role})\n"
        f"Current page: {request.referrer or request.path}\n\n"
        f"{message_text}\n"
    )

    sent = send_email_notification(
        subject=f"[BloodLink support] {subject}",
        recipient=recipient,
        body=message_body,
        reply_to=reply_to,
        async_send=current_app.config.get("MAIL_ASYNC", True),
    )
    if sent:
        flash("Support request sent. We will get back to you as soon as possible.", "success")
    else:
        flash("Unable to send the help request right now. Please try again later.", "danger")

    return redirect(redirect_to)
