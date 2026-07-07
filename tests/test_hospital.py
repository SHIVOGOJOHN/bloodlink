import unittest

from app import create_app
from app.extensions import db
from app.models import BloodBank, BloodRequest, Hospital, User


class HospitalFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = self.app.test_client()

    def test_hospital_dashboard_renders(self):
        response = self.client.get("/hospital/", follow_redirects=False)
        self.assertIn(response.status_code, {200, 302})

    def test_haversine_distance_matching(self):
        from app.models import User, Donor, Hospital
        from app.utils.matching import score_donor
        from datetime import date
        from app.extensions import db

        with self.app.app_context():
            # Setup donor user and profile
            user_d = User(email="donor_gps@example.com", password_hash="x", full_name="GPS Donor", role="donor")
            db.session.add(user_d)
            db.session.flush()
            donor = Donor(
                user_id=user_d.id, name="GPS Donor", phone="0712345678",
                county="Uasin Gishu", subcounty="Ainabkoi", ward="Ainabkoi",
                latitude=0.5200, longitude=35.2800, blood_type="O-"
            )
            db.session.add(donor)

            # Setup hospital user and profile
            user_h = User(email="hosp_gps@example.com", password_hash="y", full_name="GPS Hosp", role="hospital_staff")
            db.session.add(user_h)
            db.session.flush()
            hospital = Hospital(
                user_id=user_h.id, name="GPS Hospital",
                county="Uasin Gishu", subcounty="Eldoret West", ward="Eldoret Central",
                latitude=0.5143, longitude=35.2698, contact_phone="0712345679"
            )
            db.session.add(hospital)
            db.session.commit()

            # Execute matching score
            match_res = score_donor(donor, "O-", hospital)
            self.assertIsNotNone(match_res)
            self.assertAlmostEqual(match_res["distance_km"], 1.30, places=1)
            self.assertEqual(match_res["prox_score"], 10) # 1.30 km <= 5 km
            self.assertEqual(match_res["score"], 100) # 60 (compatibility) + 30 (eligibility) + 10 (proximity)
            self.assertIn("exact GPS match", match_res["reasons"][2])

    def test_confirm_receipt_flow(self):
        with self.app.app_context():
            # Setup hospital user and profile
            user = User(email="hosp_rec@example.com", password_hash="x", full_name="Receipt Hosp", role="hospital_staff")
            db.session.add(user)
            db.session.flush()
            user_id = user.id

            hospital = Hospital(
                user_id=user_id, name="Receipt Hospital", county="Nairobi", contact_phone="0712345670"
            )
            db.session.add(hospital)
            db.session.flush()
            hosp_id = hospital.id

            # Create a request in 'dispatched' status
            req = BloodRequest(
                hospital_id=hosp_id, blood_type="O+", units_needed=3, urgency_level="urgent", status="dispatched"
            )
            db.session.add(req)
            db.session.commit()
            req_id = req.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

        response = self.client.post(
            f"/hospital/requests/{req_id}/confirm-receipt",
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            updated_req = db.session.get(BloodRequest, req_id)
            self.assertEqual(updated_req.status, "received")

    def test_hospital_dashboard_links_fulfilled_bank_profile(self):
        with self.app.app_context():
            hospital_user = User(email="hosp_profile@example.com", password_hash="x", full_name="Profile Hosp", role="hospital_staff")
            bank_user = User(email="bank_profile@example.com", password_hash="x", full_name="Profile Bank", role="bloodbank_staff")
            db.session.add_all([hospital_user, bank_user])
            db.session.flush()
            hospital_user_id = hospital_user.id

            hospital = Hospital(user_id=hospital_user.id, name="Profile Hospital", county="Nairobi", contact_phone="0712345670")
            bloodbank = BloodBank(user_id=bank_user.id, name="Profile Blood Bank", county="Nairobi")
            db.session.add_all([hospital, bloodbank])
            db.session.flush()
            bloodbank_id = bloodbank.id

            req = BloodRequest(
                hospital_id=hospital.id,
                blood_type="A-",
                units_needed=2,
                urgency_level="normal",
                status="dispatched",
                fulfilled_by_bloodbank_id=bloodbank.id,
            )
            db.session.add(req)
            db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(hospital_user_id)
            session["_fresh"] = True

        response = self.client.get("/hospital/", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn(f"/profile/bloodbank/{bloodbank_id}", html)

    def test_create_request_page_submits_request(self):
        with self.app.app_context():
            hospital_user = User(email="hosp_create_request@example.com", password_hash="x", full_name="Create Request Hosp", role="hospital_staff")
            db.session.add(hospital_user)
            db.session.flush()
            hospital_user_id = hospital_user.id

            hospital = Hospital(user_id=hospital_user.id, name="Create Request Hospital", county="Nairobi", contact_phone="0712345670")
            db.session.add(hospital)
            db.session.commit()
            hospital_id = hospital.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(hospital_user_id)
            session["_fresh"] = True

        response = self.client.post(
            "/hospital/create-request",
            data={"blood_type": "O+", "units_needed": "3", "urgency_level": "urgent"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            requests = BloodRequest.query.filter_by(hospital_id=hospital_id).all()
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0].blood_type, "O+")
            self.assertEqual(requests[0].units_needed, 3)


if __name__ == "__main__":
    unittest.main()


