import unittest
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


class AuthFlowTests(unittest.TestCase):
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

    def test_demo_admin_login_redirects_to_admin_dashboard(self):
        if not self._db_is_available():
            self.skipTest("MySQL database is not reachable yet")

        response = self.client.post(
            "/auth/login",
            data={"email": "admin@bloodlink.local", "password": "admin123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin", response.headers["Location"])

    def test_register_page_contains_csrf_hidden_field(self):
        response = self.client.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="csrf_token"', response.get_data(as_text=True))

    def test_forgot_password_page_renders(self):
        response = self.client.get("/auth/forgot-password")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Forgot your password", response.get_data(as_text=True))

    def test_register_page_contains_three_role_choices(self):
        response = self.client.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-role="donor"', html)
        self.assertIn('data-role="hospital_staff"', html)
        self.assertIn('data-role="bloodbank_staff"', html)
        self.assertIn("Blood bank staff", html)

    def test_google_auth_redirects_to_provider(self):
        self.app.config["GOOGLE_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/google/callback"
        response = self.client.get("/auth/google?role=donor")
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.headers["Location"])
        params = parse_qs(urlparse(response.headers["Location"]).query)
        self.assertEqual(params["redirect_uri"][0], "http://127.0.0.1:5000/auth/google/callback")

    def test_google_only_account_email_login_prompts_for_google_or_reset(self):
        with self.app.app_context():
            user = User(
                email="google-only@example.com",
                full_name="Google Only",
                google_id="google-subject",
                role="donor",
            )
            db.session.add(user)
            db.session.commit()

        response = self.client.post(
            "/auth/login",
            data={"email": "google-only@example.com", "password": "google-password"},
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Continue with Google or use password reset", html)

    def test_email_password_account_can_link_google_later(self):
        with self.app.app_context():
            user = User(
                email="email-first@example.com",
                full_name="Email First",
                password_hash=generate_password_hash("password123"),
                role="donor",
            )
            db.session.add(user)
            db.session.commit()

        response = self.client.post(
            "/auth/login",
            data={"email": "email-first@example.com", "password": "password123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

    def test_google_only_account_register_prompt_points_to_google_or_reset(self):
        with self.app.app_context():
            user = User(
                email="register-google-only@example.com",
                full_name="Register Google Only",
                google_id="register-google-subject",
                role="donor",
            )
            db.session.add(user)
            db.session.commit()

        response = self.client.post(
            "/auth/register",
            data={
                "full_name": "Register Google Only",
                "email": "register-google-only@example.com",
                "phone": "",
                "password": "password123",
                "role": "donor",
                "terms_accepted": "yes",
            },
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Continue with Google or use password reset", html)

    def test_switch_role_does_not_change_fixed_user_role(self):
        with self.app.app_context():
            user = User(email="fixed-role@example.com", full_name="Fixed Role", role="donor")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        response = self.client.post("/auth/switch-role/hospital_staff", follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            user = db.session.get(User, user_id)
            self.assertEqual(user.role, "donor")


if __name__ == "__main__":
    unittest.main()
