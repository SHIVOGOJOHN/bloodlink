from __future__ import annotations

from flask import current_app, url_for
from flask_mail import Message

from app.extensions import db, mail
from app.models import BloodBank, BloodRequest, DonationRecord, Notification
from app.utils.matching import rank_donors_for_request


def _log_notification(recipient: str, channel: str, message: str, status: str) -> None:
    try:
        note = Notification(
            recipient=recipient,
            channel=channel,
            message=message,
            status=status,
        )
        db.session.add(note)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _send_email(subject: str, recipient: str, body: str, reply_to: str | None = None) -> None:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not sender:
        raise RuntimeError("Email sender is not configured.")

    message = Message(
        subject=subject,
        sender=sender,
        recipients=[recipient],
        body=body,
    )
    if reply_to:
        message.reply_to = reply_to

    mail.send(message)
    _log_notification(recipient, "email", subject, "sent")


def _send_email_safe(subject: str, recipient: str, body: str, reply_to: str | None = None) -> bool:
    try:
        _send_email(subject, recipient, body, reply_to=reply_to)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send notification email to %s", recipient)
        _log_notification(recipient, "email", subject, "failed")
        return False


def notify_new_blood_request(blood_request: BloodRequest) -> tuple[int, int]:
    hospital = blood_request.hospital
    if not hospital:
        return 0, 0

    hospital_url = url_for("public_hospital_profile", hospital_id=hospital.id, _external=True)
    subject = f"Urgent blood request: {blood_request.units_needed} × {blood_request.blood_type} for {hospital.name}"
    body = (
        f"A hospital needs blood nearby:\n\n"
        f"Hospital: {hospital.name}\n"
        f"Location: {hospital.county or 'Unknown county'}\n"
        f"Blood type: {blood_request.blood_type}\n"
        f"Units needed: {blood_request.units_needed}\n"
        f"Urgency: {blood_request.urgency_level}\n"
        f"Hospital profile: {hospital_url}\n\n"
        "If you are eligible and can donate, please visit the hospital profile and respond as soon as possible."
    )

    donors = rank_donors_for_request(blood_request.blood_type, hospital)
    donors_sent = 0
    for match in donors:
        donor = match.get("donor")
        if not donor or not getattr(donor, "user", None):
            continue
        email = getattr(donor.user, "email", None)
        if not email:
            continue
        if not getattr(donor, "consent_given", False):
            continue
        if _send_email_safe(subject, email, body):
            donors_sent += 1

    bank_subject = f"Blood bank alert: new request from {hospital.name}"
    bank_body = (
        f"A hospital has posted a new blood request: \n\n"
        f"Hospital: {hospital.name}\n"
        f"Location: {hospital.county or 'Unknown county'}\n"
        f"Blood type: {blood_request.blood_type}\n"
        f"Units needed: {blood_request.units_needed}\n"
        f"Urgency: {blood_request.urgency_level}\n"
        f"Hospital profile: {hospital_url}\n\n"
        "Please review the request and fulfill it if your bank can supply the requested blood."
    )

    banks_sent = 0
    for bank in BloodBank.query.all():
        if not getattr(bank, "user", None):
            continue
        email = getattr(bank.user, "email", None)
        if not email:
            continue
        if _send_email_safe(bank_subject, email, bank_body):
            banks_sent += 1

    return donors_sent, banks_sent


def notify_donor_donation_confirmed(
    donation: DonationRecord,
    points_awarded: int = 0,
    unlocked_badges: list[str] | None = None,
) -> bool:
    donor = donation.donor
    if not donor or not getattr(donor, "user", None):
        return False
    email = getattr(donor.user, "email", None)
    if not email:
        return False

    hospital = donation.hospital
    hospital_url = url_for("public_hospital_profile", hospital_id=hospital.id, _external=True) if hospital else ""
    subject = "Donation confirmed — thank you from BloodLink"
    badge_message = ""
    if unlocked_badges:
        badge_message = f"\n\nYou unlocked: {', '.join(unlocked_badges)}!"
    body = (
        f"Thank you {donor.name},\n\n"
        f"Your donation of {donation.blood_type} has been confirmed by {hospital.name if hospital else 'the hospital'}.\n"
        f"Hospital profile: {hospital_url}\n\n"
        f"You earned {points_awarded} loyalty point{'s' if points_awarded != 1 else ''}.\n"
        f"Your total loyalty balance is now {donor.loyalty_points or 0} points.\n"
        f"Your current loyalty rank is {donor.loyalty_rank}."
        f"{badge_message}\n\n"
        "You are now prioritized for future donation opportunities."
    )
    return _send_email_safe(subject, email, body)


def notify_request_receipt_confirmed(blood_request: BloodRequest) -> bool:
    bank = blood_request.fulfilled_by_bank
    if not bank or not getattr(bank, "user", None):
        return False
    email = getattr(bank.user, "email", None)
    if not email:
        return False

    hospital = blood_request.hospital
    hospital_url = url_for("public_hospital_profile", hospital_id=hospital.id, _external=True) if hospital else ""
    subject = "Blood delivery confirmed by hospital"
    body = (
        f"The hospital request for {blood_request.blood_type} was marked as received.\n\n"
        f"Hospital: {hospital.name if hospital else 'Unknown'}\n"
        f"Request ID: {blood_request.id}\n"
        f"Hospital profile: {hospital_url}\n\n"
        "Thank you for fulfilling this request. Your delivery is complete."
    )
    return _send_email_safe(subject, email, body)
