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


def init_database(app):
    with app.app_context():
        try:
            db.create_all()
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

    return app


application = None
