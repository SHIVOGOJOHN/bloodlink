import importlib
import os


def test_database_url_is_normalized_for_pymysql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@127.0.0.1:3306/bloodlink")
    import app.config as config_module

    config_module = importlib.reload(config_module)

    assert config_module.Config.SQLALCHEMY_DATABASE_URI.startswith("mysql+pymysql://")
