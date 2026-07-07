from __future__ import annotations

import threading

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


def _create_email_message(subject: str, recipient: str, body: str, reply_to: str | None = None) -> Message:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not sender:
        raise RuntimeError("Email sender is not configured")

    message = Message(
        subject=subject,
        sender=sender,
        recipients=[recipient],
        body=body,
    )
    if reply_to:
        message.reply_to = reply_to
    return message


def _send_message(message: Message) -> None:
    mail.send(message)
    _log_notification(message.recipients[0], "email", message.subject, "sent")


def _send_message_async(app, message: Message) -> None:
    with app.app_context():
        try:
            mail.send(message)
            _log_notification(message.recipients[0], "email", message.subject, "sent")
        except Exception:
            current_app.logger.exception("Failed to send notification email to %s", message.recipients[0])
            _log_notification(message.recipients[0], "email", message.subject, "failed")


def send_email_notification(
    subject: str,
    recipient: str,
    body: str,
    reply_to: str | None = None,
    async_send: bool | None = None,
) -> bool:
    if async_send is None:
        async_send = current_app.config.get("MAIL_ASYNC", True)

    try:
        message = _create_email_message(subject, recipient, body, reply_to=reply_to)
    except Exception:
        current_app.logger.exception("Failed to create email message for %s", recipient)
        _log_notification(recipient, "email", subject, "failed")
        return False

    timeout = current_app.config.get("MAIL_TIMEOUT", 10)
    current_app.config["MAIL_TIMEOUT"] = timeout

    if async_send:
        app = current_app._get_current_object()
        thread = threading.Thread(target=_send_message_async, args=(app, message), daemon=True)
        thread.start()
        return True

    try:
        _send_message(message)
        return True
    except Exception:
        current_app.logger.exception("Failed to send notification email to %s", recipient)
        _log_notification(recipient, "email", subject, "failed")
        return False


def _send_email_safe(subject: str, recipient: str, body: str, reply_to: str | None = None) -> bool:
    try:
        return send_email_notification(subject, recipient, body, reply_to=reply_to)
    except Exception:
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


def notify_bank_of_request(blood_request: BloodRequest, bank: BloodBank) -> bool:
    if not bank or not getattr(bank, "user", None):
        return False
    email = getattr(bank.user, "email", None)
    if not email:
        return False

    hospital = blood_request.hospital
    hospital_url = url_for("public_hospital_profile", hospital_id=hospital.id, _external=True) if hospital else ""
    subject = f"Targeted blood request: {blood_request.units_needed} × {blood_request.blood_type} for {hospital.name if hospital else 'your region'}"
    body = (
        f"A hospital has requested blood directly from your blood bank:\n\n"
        f"Hospital: {hospital.name if hospital else 'Unknown'}\n"
        f"Location: {hospital.county or 'Unknown county'}\n"
        f"Blood type: {blood_request.blood_type}\n"
        f"Units needed: {blood_request.units_needed}\n"
        f"Urgency: {blood_request.urgency_level}\n"
        f"Hospital profile: {hospital_url}\n\n"
        "Please review the request and fulfill it if you can supply the requested blood."
    )
    return _send_email_safe(subject, email, body)


def notify_hospital_request_created(blood_request: BloodRequest, bank_name: str | None = None) -> bool:
    hospital = blood_request.hospital
    if not hospital or not getattr(hospital, "user", None):
        return False
    email = getattr(hospital.user, "email", None)
    if not email:
        return False

    bank_text = f"Your request was sent to {bank_name}. " if bank_name else ""
    subject = f"Blood request submitted: {blood_request.units_needed} × {blood_request.blood_type}"
    body = (
        f"Hello {hospital.name},\n\n"
        f"Your targeted blood request has been created successfully.\n"
        f"{bank_text}The blood bank has been notified and can now review your request.\n\n"
        f"Details:\n"
        f"Blood type: {blood_request.blood_type}\n"
        f"Units needed: {blood_request.units_needed}\n"
        f"Urgency: {blood_request.urgency_level}\n"
        f"Hospital profile: {url_for('public_hospital_profile', hospital_id=hospital.id, _external=True)}\n\n"
        "Thank you for using BloodLink. We will notify you when the blood bank responds."
    )
    return _send_email_safe(subject, email, body)


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
