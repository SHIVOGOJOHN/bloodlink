import unittest

from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import Hospital, User
from app.utils.forecast import get_county_map_data, get_hospital_forecast, get_national_forecast_summary


class Phase6Tests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = self.app.test_client()

    def _db_is_available(self):
        try:
            with self.app.app_context():
                db.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def test_hospital_forecast_service_returns_structured_data(self):
        if not self._db_is_available():
            self.skipTest("Database is not reachable yet")

        with self.app.app_context():
            hospital_user = User.query.filter_by(email="hospital@bloodlink.local").first()
            self.assertIsNotNone(hospital_user)
            hospital = hospital_user.hospital
            self.assertIsNotNone(hospital)

            forecast = get_hospital_forecast(hospital)
            self.assertTrue(forecast["is_operational"])
            self.assertEqual(len(forecast["daily_totals"]), 14)
            self.assertGreater(len(forecast["blood_type_summary"]), 0)
            self.assertIn("refresh_policy", forecast)
            self.assertIn("selected_model", forecast["training_summary"])

    def test_county_map_service_returns_summary(self):
        if not self._db_is_available():
            self.skipTest("Database is not reachable yet")

        with self.app.app_context():
            county_map = get_county_map_data()
            self.assertEqual(county_map["type"], "FeatureCollection")
            self.assertGreater(len(county_map["features"]), 0)
            self.assertGreater(len(county_map["summary"]), 0)
            self.assertIn("legend", county_map)

    def test_hospital_dashboard_renders_forecast_panel(self):
        if not self._db_is_available():
            self.skipTest("Database is not reachable yet")

        with self.app.app_context():
            user = User.query.filter_by(email="hospital@bloodlink.local").first()
            self.assertIsNotNone(user)
            hospital = user.hospital
            self.assertIsNotNone(hospital)
            hospital_id = user.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(hospital_id)
            session["_fresh"] = True

        response = self.client.get("/hospital/", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Operational Demand Forecast", html)
        self.assertIn("forecast-chart", html)

    def test_admin_dashboard_renders_national_map(self):
        if not self._db_is_available():
            self.skipTest("Database is not reachable yet")

        with self.app.app_context():
            admin_user = User.query.filter_by(email="admin@bloodlink.local").first()
            self.assertIsNotNone(admin_user)
            admin_id = admin_user.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(admin_id)
            session["_fresh"] = True

        response = self.client.get("/admin/", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("National Monitoring Map", html)
        self.assertIn("county-map", html)
        self.assertIn("Operational National Forecast", html)


if __name__ == "__main__":
    unittest.main()
