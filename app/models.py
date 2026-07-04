import os
from datetime import datetime

from flask_login import UserMixin

from .extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def table_name(base_name: str) -> str:
    prefix = os.getenv("DB_TABLE_PREFIX", "bl_")
    suffix = os.getenv("DB_TABLE_SUFFIX", "_tbl")
    return f"{prefix}{base_name}{suffix}"


USER_TABLE = table_name("users")
DONOR_TABLE = table_name("donors")
HOSPITAL_TABLE = table_name("hospitals")
BLOODBANK_TABLE = table_name("blood_banks")
BLOODBANK_STOCK_TABLE = table_name("blood_bank_stock")
BLOOD_REQUEST_TABLE = table_name("blood_requests")
DONATION_RECORD_TABLE = table_name("donation_records")
NOTIFICATION_TABLE = table_name("notifications")
REIMBURSEMENT_REQUEST_TABLE = table_name("reimbursement_requests")


class User(db.Model, UserMixin):
    __tablename__ = table_name("users")

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(50), default="donor", nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    donor = db.relationship("Donor", backref="user", uselist=False, cascade="all, delete-orphan")
    hospital = db.relationship("Hospital", backref="user", uselist=False, cascade="all, delete-orphan")
    bloodbank = db.relationship("BloodBank", backref="user", uselist=False, cascade="all, delete-orphan")


class Donor(db.Model):
    __tablename__ = table_name("donors")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(f"{USER_TABLE}.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    county = db.Column(db.String(100), nullable=False)
    subcounty = db.Column(db.String(100), nullable=True)
    ward = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    blood_type = db.Column(db.String(10), nullable=False)
    last_donation_date = db.Column(db.Date, nullable=True)
    consent_given = db.Column(db.Boolean, default=False)
    consent_timestamp = db.Column(db.DateTime, nullable=True)
    profile_pic_url = db.Column(db.String(512), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Hospital(db.Model):
    __tablename__ = table_name("hospitals")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(f"{USER_TABLE}.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    county = db.Column(db.String(100), nullable=False)
    subcounty = db.Column(db.String(100), nullable=True)
    ward = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    profile_pic_url = db.Column(db.String(512), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BloodBank(db.Model):
    __tablename__ = table_name("blood_banks")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(f"{USER_TABLE}.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    county = db.Column(db.String(100), nullable=False)
    subcounty = db.Column(db.String(100), nullable=True)
    ward = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    profile_pic_url = db.Column(db.String(512), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class BloodBankStock(db.Model):
    __tablename__ = table_name("blood_bank_stock")

    id = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, db.ForeignKey(f"{BLOODBANK_TABLE}.id"), nullable=False)
    blood_type = db.Column(db.String(10), nullable=False)
    units_available = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    blood_bank = db.relationship("BloodBank", backref=db.backref("stock", lazy=True))



class BloodRequest(db.Model):
    __tablename__ = table_name("blood_requests")

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey(f"{HOSPITAL_TABLE}.id"), nullable=False)
    blood_type = db.Column(db.String(10), nullable=False)
    units_needed = db.Column(db.Integer, nullable=False)
    urgency_level = db.Column(db.String(50), default="normal")
    status = db.Column(db.String(50), default="open")
    fulfilled_by_bloodbank_id = db.Column(db.Integer, db.ForeignKey(f"{BLOODBANK_TABLE}.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hospital = db.relationship("Hospital", backref=db.backref("requests", lazy=True))
    fulfilled_by_bank = db.relationship("BloodBank", foreign_keys=[fulfilled_by_bloodbank_id], backref=db.backref("fulfilled_requests", lazy=True))



class DonationRecord(db.Model):
    __tablename__ = table_name("donation_records")

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey(f"{DONOR_TABLE}.id"), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey(f"{HOSPITAL_TABLE}.id"), nullable=False)
    blood_request_id = db.Column(db.Integer, db.ForeignKey(f"{BLOOD_REQUEST_TABLE}.id"), nullable=True)
    blood_type = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(50), default="confirmed")
    confirmed_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_by_user_id = db.Column(db.Integer, db.ForeignKey(f"{USER_TABLE}.id"), nullable=True)

    donor = db.relationship("Donor", backref=db.backref("donations", lazy=True))
    hospital = db.relationship("Hospital", backref=db.backref("donations", lazy=True))
    blood_request = db.relationship("BloodRequest", backref=db.backref("records", lazy=True))


class Notification(db.Model):
    __tablename__ = table_name("notifications")

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(255), nullable=False)
    channel = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="sent")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PasswordResetToken(db.Model):
    __tablename__ = table_name("password_reset_tokens")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(f"{USER_TABLE}.id"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="password_resets")


class ReimbursementRequest(db.Model):
    __tablename__ = table_name("reimbursement_requests")

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey(f"{DONOR_TABLE}.id"), nullable=False)
    donation_id = db.Column(db.Integer, db.ForeignKey(f"{DONATION_RECORD_TABLE}.id"), nullable=False)
    amount = db.Column(db.Integer, default=300)
    status = db.Column(db.String(50), default="pending")
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey(f"{USER_TABLE}.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    mpesa_transaction_id = db.Column(db.String(255), nullable=True)
    disbursed_at = db.Column(db.DateTime, nullable=True)


class ForecastTrainingRun(db.Model):
    __tablename__ = table_name("forecast_training_runs")

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(120), unique=True, nullable=False, index=True)
    fingerprint = db.Column(db.String(128), nullable=False, index=True)
    model_name = db.Column(db.String(120), nullable=False)
    training_rows = db.Column(db.Integer, default=0, nullable=False)
    train_rows = db.Column(db.Integer, default=0, nullable=False)
    validation_rows = db.Column(db.Integer, default=0, nullable=False)
    mae = db.Column(db.Float, nullable=True)
    rmse = db.Column(db.Float, nullable=True)
    mape = db.Column(db.Float, nullable=True)
    artifact_path = db.Column(db.String(500), nullable=False)
    metrics_json = db.Column(db.Text, nullable=True)
    is_current = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
