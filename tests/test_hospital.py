import unittest

from app import create_app


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


if __name__ == "__main__":
    unittest.main()

