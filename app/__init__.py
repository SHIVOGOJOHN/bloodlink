import os
from flask import Flask, render_template
from sqlalchemy.exc import SQLAlchemyError

from .config import config as config_map
from .extensions import csrf, db, login_manager, mail
from .models import (
    BloodBank,
    BloodBankStock,
    BloodRequest,
    DonationRecord,
    Donor,
    Notification,
    PasswordResetToken,
    ReimbursementRequest,
    User,
)
from .blueprints.auth.routes import auth_bp
from .blueprints.donor.routes import donor_bp
from .blueprints.hospital.routes import hospital_bp
from .blueprints.bloodbank.routes import bloodbank_bp
from .blueprints.admin.routes import admin_bp
from .blueprints.ussd.routes import ussd_bp
from .blueprints.api.routes import api_bp
from .blueprints.reimbursement.routes import reimbursement_bp
from .utils.forecast import start_forecast_retraining_scheduler


def init_database(app):
    with app.app_context():
        try:
            db.create_all()
            
            # Auto-migrate: add columns if they don't exist in existing tables (e.g. on MySQL)
            from sqlalchemy import text
            from .models import Donor, Hospital, BloodBank, BloodRequest

            
            tables_to_update = [
                (Donor.__tablename__, [
                    ("subcounty", "VARCHAR(100)"),
                    ("ward", "VARCHAR(100)"),
                    ("latitude", "DOUBLE"),
                    ("longitude", "DOUBLE")
                ]),
                (Hospital.__tablename__, [
                    ("subcounty", "VARCHAR(100)"),
                    ("ward", "VARCHAR(100)"),
                    ("latitude", "DOUBLE"),
                    ("longitude", "DOUBLE")
                ]),
                (BloodBank.__tablename__, [
                    ("subcounty", "VARCHAR(100)"),
                    ("ward", "VARCHAR(100)"),
                    ("latitude", "DOUBLE"),
                    ("longitude", "DOUBLE")
                ]),
                (BloodRequest.__tablename__, [
                    ("fulfilled_by_bloodbank_id", "INT")
                ])
            ]
            
            for table_name, columns in tables_to_update:
                for col_name, col_type in columns:
                    try:
                        db.session.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type} NULL"))
                        db.session.commit()
                        app.logger.info("Migrated: Added column %s to %s", col_name, table_name)
                    except Exception:
                        db.session.rollback()

            if app.config.get("SEED_DATABASE_ON_INIT", True):
                from .seed import seed_database

                seed_database(app)
        except Exception as exc:
            app.logger.warning("Database initialization skipped: %s", exc)



def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_map[config_name])
    config_map[config_name].init_app(app)

    # Use ProxyFix in production to generate correct https external URLs behind Render's reverse proxy
    if config_name == "production":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(donor_bp)
    app.register_blueprint(hospital_bp)
    app.register_blueprint(bloodbank_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ussd_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(reimbursement_bp)

    init_database(app)
    start_forecast_retraining_scheduler(app)

    @app.context_processor
    def inject_counties():
        from app.utils.matching import COUNTY_DISTANCE
        return {"kenya_counties": sorted(COUNTY_DISTANCE.keys())}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/data-policy")
    def data_policy():
        return render_template("policy/data_policy.html")

    @app.route("/terms")
    def terms():
        return render_template("policy/terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("policy/privacy.html")

    @app.route("/cdn/profile_pics/<path:filename>")
    def cdn_profile_pics(filename):
        """Proxy profile pictures from private GitHub repository."""
        token = app.config.get("GITHUB_TOKEN", "").strip()
        repo = app.config.get("GITHUB_REPO", "").strip()
        branch = app.config.get("GITHUB_BRANCH", "main").strip()
        
        if not token or not repo:
            from flask import abort
            abort(404)
            
        import requests
        from flask import make_response, abort
        
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/profile_pics/{filename}"
        headers = {"Authorization": f"token {token}"}
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                resp = make_response(r.content)
                resp.headers['Content-Type'] = r.headers.get('Content-Type', 'image/jpeg')
                resp.headers['Cache-Control'] = 'public, max-age=86400'
                return resp
            else:
                abort(404)
        except Exception:
            abort(404)

    from flask import abort
    from flask_login import login_required

    @app.route("/profile/donor/<int:donor_id>")
    @login_required
    def public_donor_profile(donor_id):
        from app.models import Donor
        from app.utils.matching import is_eligible
        
        donor = db.session.get(Donor, donor_id)
        if not donor:
            abort(404)
        eligible, days_since = is_eligible(donor)
        days_left = max(0, 90 - days_since) if days_since is not None else 0
        
        # Unlocked badges count
        from app.models import DonationRecord
        donation_count = DonationRecord.query.filter_by(donor_id=donor.id, status="confirmed").count()
        badges = []
        if donation_count >= 1:
            badges.append("First Drop")
        if donation_count >= 5:
            badges.append("Life Saver")
        if donation_count >= 10:
            badges.append("Blood Hero")
            
        return render_template(
            "donor/profile.html",
            donor=donor,
            eligible=eligible,
            days_left=days_left,
            donation_count=donation_count,
            badges=badges,
        )

    @app.route("/profile/hospital/<int:hospital_id>")
    @login_required
    def public_hospital_profile(hospital_id):
        from app.models import Hospital
        hospital = db.session.get(Hospital, hospital_id)
        if not hospital:
            abort(404)
        return render_template("hospital/profile.html", hospital=hospital)

    @app.route("/profile/bloodbank/<int:bloodbank_id>")
    @login_required
    def public_bloodbank_profile(bloodbank_id):
        from app.models import BloodBank
        bloodbank = db.session.get(BloodBank, bloodbank_id)
        if not bloodbank:
            abort(404)
        return render_template("bloodbank/profile.html", bloodbank=bloodbank)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"Internal Server Error: {e}")
        return render_template("errors/500.html"), 500

    return app


application = None
