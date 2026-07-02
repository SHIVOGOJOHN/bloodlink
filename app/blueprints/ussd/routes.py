from flask import Blueprint, request, Response

ussd_bp = Blueprint("ussd", __name__, url_prefix="/ussd")


@ussd_bp.route("", methods=["POST"])
def handle_ussd():
    session_id = request.form.get("sessionId", "")
    service_code = request.form.get("serviceCode", "")
    phone_number = request.form.get("phoneNumber", "")
    text = request.form.get("text", "")

    if text == "":
        response = "CON Welcome to BloodLink.\n1. Register as donor\n2. Check eligibility\n3. View nearby requests\n4. Find nearest blood bank"
    elif text.startswith("1"):
        response = "END Thanks. Donor registration is available through the web portal."
    elif text.startswith("2"):
        response = "END Eligibility is checked using your last donation date and blood type."
    elif text.startswith("3"):
        response = "END Nearby requests will appear on the donor dashboard."
    elif text.startswith("4"):
        response = "END Nearest blood bank details are shown on the platform map."
    else:
        response = "END Invalid selection."

    return Response(response, mimetype="text/plain")
