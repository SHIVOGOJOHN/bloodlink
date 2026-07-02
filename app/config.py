import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_USER = os.getenv("MYSQL_USER", "bloodlink")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "bloodlink")
    MYSQL_DB = os.getenv("MYSQL_DB", "bloodlink")
    DB_TABLE_PREFIX = os.getenv("DB_TABLE_PREFIX", "bl_")
    DB_TABLE_SUFFIX = os.getenv("DB_TABLE_SUFFIX", "_tbl")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    else:
        if SQLALCHEMY_DATABASE_URI.startswith("mysql://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("mysql://", "mysql+pymysql://", 1)
        elif SQLALCHEMY_DATABASE_URI.startswith("mysql+pymysql://"):
            pass
        else:
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("mysql://", "mysql+pymysql://", 1)

        parsed = urlsplit(SQLALCHEMY_DATABASE_URI)
        filtered_query = urlencode(
            [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() != "ssl-mode"],
            doseq=True,
        )
        SQLALCHEMY_DATABASE_URI = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, filtered_query, parsed.fragment))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "bloodlink@example.com")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    GOOGLE_REDIRECT_BASE_URL = os.getenv("GOOGLE_REDIRECT_BASE_URL", "").strip()
    AFRICAS_TALKING_USERNAME = os.getenv("AFRICAS_TALKING_USERNAME", "")
    AFRICAS_TALKING_API_KEY = os.getenv("AFRICAS_TALKING_API_KEY", "")
    DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY", "")
    DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET", "")
    DARAJA_INITIATOR_NAME = os.getenv("DARAJA_INITIATOR_NAME", "")
    DARAJA_SECURITY_CREDENTIAL = os.getenv("DARAJA_SECURITY_CREDENTIAL", "")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
    GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
    GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
    SEED_DATABASE_ON_INIT = True

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SEED_DATABASE_ON_INIT = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite://")


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
