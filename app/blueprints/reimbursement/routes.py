from flask import Blueprint, render_template
from flask_login import login_required

reimbursement_bp = Blueprint("reimbursement", __name__, url_prefix="/reimbursement")


@reimbursement_bp.route("/")
@login_required
def dashboard():
    return render_template("reimbursement/dashboard.html")
