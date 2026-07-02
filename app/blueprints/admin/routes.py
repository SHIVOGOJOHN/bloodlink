from flask import Blueprint, render_template

from app.models import BloodRequest, DonationRecord, Notification, ReimbursementRequest, User
from app.utils.auth import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@role_required("admin")
def dashboard():
    users = User.query.all()
    requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    donations = DonationRecord.query.order_by(DonationRecord.confirmed_at.desc()).all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    reimbursements = ReimbursementRequest.query.order_by(ReimbursementRequest.requested_at.desc()).all()
    return render_template(
        "admin/dashboard.html",
        users=users,
        requests=requests,
        donations=donations,
        notifications=notifications,
        reimbursements=reimbursements,
    )
