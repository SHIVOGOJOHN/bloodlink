import unittest

from app import create_app


class HospitalFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("development")
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = self.app.test_client()

    def test_hospital_dashboard_renders(self):
        response = self.client.get("/hospital/", follow_redirects=False)
        self.assertIn(response.status_code, {200, 302})


if __name__ == "__main__":
    unittest.main()
