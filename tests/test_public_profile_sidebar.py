import pytest

from app import create_app
from app.extensions import db
from app.models import Donor, Hospital, BloodBank, User


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


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_donor_sees_donor_sidebar_when_viewing_hospital_profile(app, client):
    with app.app_context():
        donor_user = User(email="donor@example.com", password_hash="x", full_name="Donor User", role="donor")
        hospital_user = User(email="hospital@example.com", password_hash="x", full_name="Hospital User", role="hospital_staff")
        db.session.add_all([donor_user, hospital_user])
        db.session.flush()

        donor = Donor(user_id=donor_user.id, name="Test Donor", phone="0712345678", county="Nairobi", blood_type="O+")
        hospital = Hospital(user_id=hospital_user.id, name="Test Hospital", county="Nairobi")
        db.session.add_all([donor, hospital])
        db.session.commit()

    login_as(client, donor_user.id)
    response = client.get(f"/profile/hospital/{hospital.id}")
    assert response.status_code == 200
    assert b"id=\"donor-sidebar\"" in response.data
    assert b"Profile & Rewards" in response.data
    assert b"id=\"hospital-sidebar\"" not in response.data


def test_hospital_sees_hospital_sidebar_when_viewing_bloodbank_profile(app, client):
    with app.app_context():
        hospital_user = User(email="hospital2@example.com", password_hash="x", full_name="Hospital Two", role="hospital_staff")
        bank_user = User(email="bank@example.com", password_hash="x", full_name="Bank User", role="bloodbank_staff")
        db.session.add_all([hospital_user, bank_user])
        db.session.flush()

        hospital = Hospital(user_id=hospital_user.id, name="Viewer Hospital", county="Mombasa")
        bloodbank = BloodBank(user_id=bank_user.id, name="Viewer Bank", county="Mombasa")
        db.session.add_all([hospital, bloodbank])
        db.session.commit()

    login_as(client, hospital_user.id)
    response = client.get(f"/profile/bloodbank/{bloodbank.id}")
    assert response.status_code == 200
    assert b"id=\"hospital-sidebar\"" in response.data
    assert b"National Inventory" in response.data
    assert b"id=\"bank-sidebar\"" not in response.data


def test_bloodbank_sees_bloodbank_sidebar_when_viewing_donor_profile(app, client):
    with app.app_context():
        bank_user = User(email="bank2@example.com", password_hash="x", full_name="Bank Two", role="bloodbank_staff")
        donor_user = User(email="donor2@example.com", password_hash="x", full_name="Donor Two", role="donor")
        db.session.add_all([bank_user, donor_user])
        db.session.flush()

        bloodbank = BloodBank(user_id=bank_user.id, name="Viewer Bank", county="Kisumu")
        donor = Donor(user_id=donor_user.id, name="Target Donor", phone="0722001122", county="Kisumu", blood_type="A+")
        db.session.add_all([bloodbank, donor])
        db.session.commit()

    login_as(client, bank_user.id)
    response = client.get(f"/profile/donor/{donor.id}")
    assert response.status_code == 200
    assert b"id=\"bank-sidebar\"" in response.data
    assert b"Inventory" in response.data
    assert b"id=\"donor-sidebar\"" not in response.data
