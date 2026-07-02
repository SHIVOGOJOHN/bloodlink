from datetime import date, datetime

from werkzeug.security import generate_password_hash

from .extensions import db
from .models import BloodBank, BloodBankStock, BloodRequest, DonationRecord, Donor, Hospital, Notification, ReimbursementRequest, User


def seed_database(app):
    with app.app_context():
        if User.query.first():
            return

        admin = User(
            email="admin@bloodlink.local",
            password_hash=generate_password_hash("admin123"),
            role="admin",
            full_name="System Admin",
            phone="0712345678",
        )
        db.session.add(admin)

        donor_user = User(
            email="donor@bloodlink.local",
            password_hash=generate_password_hash("donor123"),
            role="donor",
            full_name="Jane Donor",
            phone="0723456789",
        )
        db.session.add(donor_user)

        hospital_user = User(
            email="hospital@bloodlink.local",
            password_hash=generate_password_hash("hospital123"),
            role="hospital_staff",
            full_name="Hospital Staff",
            phone="0734567890",
        )
        db.session.add(hospital_user)

        bloodbank_user = User(
            email="bloodbank@bloodlink.local",
            password_hash=generate_password_hash("bloodbank123"),
            role="bloodbank_staff",
            full_name="Blood Bank Staff",
            phone="0745678901",
        )
        db.session.add(bloodbank_user)

        db.session.flush()

        donor = Donor(
            user_id=donor_user.id,
            name="Jane Donor",
            phone="0723456789",
            county="Nairobi",
            blood_type="O-",
            last_donation_date=date(2025, 1, 1),
            consent_given=True,
            consent_timestamp=datetime(2026, 1, 1, 0, 0, 0),
        )
        db.session.add(donor)

        hospital = Hospital(
            user_id=hospital_user.id,
            name="Moi Teaching Hospital",
            county="Uasin Gishu",
            contact_phone="0541234567",
        )
        db.session.add(hospital)

        bloodbank = BloodBank(
            user_id=bloodbank_user.id,
            name="Nairobi Blood Bank",
            county="Nairobi",
        )
        db.session.add(bloodbank)

        db.session.flush()

        db.session.add_all(
            [
                BloodBankStock(blood_bank_id=bloodbank.id, blood_type="O-", units_available=20, expiry_date=date(2026, 8, 1)),
                BloodBankStock(blood_bank_id=bloodbank.id, blood_type="A+", units_available=15, expiry_date=date(2026, 8, 2)),
                BloodBankStock(blood_bank_id=bloodbank.id, blood_type="B-", units_available=8, expiry_date=date(2026, 8, 3)),
            ]
        )

        request = BloodRequest(
            hospital_id=hospital.id,
            blood_type="O-",
            units_needed=2,
            urgency_level="urgent",
            status="open",
        )
        db.session.add(request)

        donation = DonationRecord(
            donor_id=donor.id,
            hospital_id=hospital.id,
            blood_request_id=request.id,
            blood_type="O-",
            status="confirmed",
        )
        db.session.add(donation)
        db.session.flush()

        db.session.add(Notification(recipient=donor_user.email, channel="email", message="Welcome to BloodLink", status="sent"))
        db.session.add(ReimbursementRequest(donor_id=donor.id, donation_id=donation.id, amount=300, status="pending"))

        db.session.commit()
