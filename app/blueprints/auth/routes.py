import hashlib
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, urljoin

import requests
from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from flask_mail import Message
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, mail
from app.models import PasswordResetToken, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

GOOGLE_AUTH_URL   = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "").strip()
_GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
_GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "").strip()


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_role(role: str) -> str:
    return role if role in {"donor", "hospital_staff", "bloodbank_staff", "admin"} else "donor"


def role_dashboard(role: str):
    role_routes = {
        "admin": "admin.dashboard",
        "hospital_staff": "hospital.dashboard",
        "bloodbank_staff": "bloodbank.dashboard",
        "donor": "donor.dashboard",
    }
    return role_routes.get(role, "index")



def _send_password_reset_email(user: User, raw_token: str) -> None:
    reset_url = url_for("auth.reset_password", token=raw_token, _external=True)
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    message = Message(
        subject="Reset your BloodLink password",
        sender=sender,
        recipients=[user.email],
        body=(
            f"Hello {user.full_name or 'there'},\n\n"
            "Use this link to reset your BloodLink password. The link expires in 1 hour:\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
    )
    mail.send(message)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(role_dashboard(current_user.role)))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user:
            if user.password_hash and check_password_hash(user.password_hash, password):
                login_user(user)
                flash("Welcome back.", "success")
                return redirect(url_for(role_dashboard(user.role)))

            if user.google_id and not user.password_hash:
                flash("This email was created with Google. Continue with Google or use password reset to set an email password.", "info")
                return render_template("auth/login.html")

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(role_dashboard(current_user.role)))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        role = _normalize_role(request.form.get("role", "donor"))
        terms_accepted = request.form.get("terms_accepted") == "yes"

        if not email or not password or not full_name:
            flash("Please complete all required fields.", "danger")
            return render_template("auth/register.html")

        if not terms_accepted:
            flash("Please agree to the Terms of Service and Privacy Policy.", "warning")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "warning")
            return render_template("auth/register.html")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.google_id and not existing_user.password_hash:
                flash("That email already has a Google sign-in account. Continue with Google or use password reset to add an email password.", "info")
            else:
                flash("An account with that email already exists.", "warning")
            return render_template("auth/register.html")

        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            phone=phone,
            role=role,
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account created successfully.", "success")
        return redirect(url_for(role_dashboard(user.role)))

    return render_template("auth/register.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email is required.", "warning")
            return render_template("auth/forgot_password.html")

        user = User.query.filter_by(email=email).first()
        if user:
            raw_token = secrets.token_urlsafe(24)
            db.session.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=_hash_reset_token(raw_token),
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                )
            )
            db.session.commit()
            try:
                _send_password_reset_email(user, raw_token)
            except Exception as exc:
                current_app.logger.exception("Password reset email failed for %s", user.email)
                flash("We created a reset link but could not send email. Check Gmail SMTP settings.", "danger")
                return render_template("auth/forgot_password.html")

        flash("If an account exists for that email, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    token_hash = _hash_reset_token(token or "")
    record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not record or record.used or record.expires_at < datetime.utcnow():
        flash("That reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 8 or password != confirm_password:
            flash("Please choose a matching password with at least 8 characters.", "warning")
            return render_template("auth/reset_password.html", token=token)

        record.user.password_hash = generate_password_hash(password)
        record.used = True
        db.session.commit()
        flash("Password updated successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)


def _get_redirect_uri():
    if _GOOGLE_REDIRECT_URI:
        return _GOOGLE_REDIRECT_URI
    return url_for("auth.google_callback", _external=True)


@auth_bp.route("/google")
def google_auth():
    action = request.args.get("action", "login")
    role = _normalize_role(request.args.get("role", "donor"))
    if not _GOOGLE_CLIENT_ID:
        flash("Google sign-in is not configured yet.", "danger")
        return redirect(url_for("auth.login"))

    session["pending_action"] = action
    session["pending_role"] = role
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = urlencode({
        "client_id": _GOOGLE_CLIENT_ID,
        "redirect_uri": _get_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    })
    return redirect(f"{GOOGLE_AUTH_URL}?{params}")

@auth_bp.route("/google/callback")
def google_callback():
    if request.args.get("state") != session.pop("oauth_state", None):
        flash("Google sign-in could not be completed.", "danger")
        return redirect(url_for("auth.login"))

    action = session.pop("pending_action", "login")
    role = _normalize_role(session.pop("pending_role", "donor"))
    code = request.args.get("code", "")
    if not code:
        flash("Google sign-in was cancelled.", "info")
        return redirect(url_for("auth.login"))

    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": _GOOGLE_CLIENT_ID,
            "client_secret": _GOOGLE_CLIENT_SECRET,
            "redirect_uri": _get_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if not token_response.ok:
        current_app.logger.warning("Google token exchange failed: %s", token_response.text)
        flash("Google sign-in could not be completed.", "danger")
        return redirect(url_for("auth.login"))

    access_token = token_response.json().get("access_token")
    if not access_token:
        flash("Google sign-in could not be completed.", "danger")
        return redirect(url_for("auth.login"))

    profile_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not profile_response.ok:
        current_app.logger.warning("Google profile request failed: %s", profile_response.text)
        flash("Google sign-in could not be completed.", "danger")
        return redirect(url_for("auth.login"))

    profile = profile_response.json()
    email = (profile.get("email") or "").strip().lower()
    if not email:
        flash("Google did not return an email address.", "danger")
        return redirect(url_for("auth.login"))

    if profile.get("email_verified") is False:
        flash("Please verify your Google email address before signing in.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        if action == "login":
            flash("No account exists for this Google email. Please register first to choose your role.", "warning")
            return redirect(url_for("auth.register"))

        user = User(
            email=email,
            full_name=profile.get("name") or email.split("@")[0],
            google_id=profile.get("sub"),
            role=role,
        )
        db.session.add(user)
        db.session.commit()
    else:
        changed = False
        if not user.google_id and profile.get("sub"):
            user.google_id = profile.get("sub")
            changed = True
        if not user.full_name and profile.get("name"):
            user.full_name = profile.get("name")
            changed = True
        if changed:
            db.session.commit()

    login_user(user)
    flash("Signed in with Google.", "success")
    return redirect(url_for(role_dashboard(user.role)))


@auth_bp.route("/switch-role/<role>", methods=["POST"])
@login_required
def switch_role(role: str):
    flash("Your account has one fixed role. Create a separate account if you need a different role.", "warning")
    return redirect(url_for(role_dashboard(current_user.role)))
