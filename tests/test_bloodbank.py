import pytest

from app import create_app
from app.extensions import db
from app.models import BloodBank, BloodBankStock, BloodRequest, User


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_bloodbank_can_update_stock_and_mark_request_fulfilled(app, client):
    with app.app_context():
        user = User(
            email="bank@example.com",
            password_hash="x",
            full_name="Bank Staff",
            role="bloodbank_staff",
        )
        db.session.add(user)
        db.session.flush()
        user_id = user.id

        bank = BloodBank(user_id=user_id, name="Kisumu Blood Bank", county="Kisumu")
        db.session.add(bank)
        db.session.flush()
        bank_id = bank.id

        stock = BloodBankStock(blood_bank_id=bank_id, blood_type="O+", units_available=5)
        db.session.add(stock)

        request = BloodRequest(hospital_id=1, blood_type="O+", units_needed=2, urgency_level="urgent")
        db.session.add(request)
        db.session.commit()
        request_id = request.id

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.post(
        "/bloodbank/stock",
        data={"blood_type": "O+", "units_available": "3", "blood_bank_id": str(bank_id)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.post(
        f"/bloodbank/requests/{request_id}/fulfill",
        data={"units_fulfilled": "2"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        updated_stock = BloodBankStock.query.filter_by(blood_type="O+", blood_bank_id=bank_id).first()
        updated_request = BloodRequest.query.get(request_id)

    assert updated_stock.units_available == 1
    assert updated_request.status == "fulfilled"

