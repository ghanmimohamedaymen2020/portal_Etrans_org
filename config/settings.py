"""Configuration de l'application — centralise tous les paramètres."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


# Charge .env sans écraser les variables système (utile en environnements gérés).
load_dotenv(override=False)
_DOTENV = dotenv_values(Path(__file__).resolve().parents[1] / ".env")


def _env_bool(name: str, default: bool) -> bool:
    """Parse une variable d'environnement booléenne de façon robuste."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _mail_setting(name: str, default: str | None = None) -> str | None:
    """Lit d'abord .env pour le SMTP, puis variables système en fallback."""
    raw = _DOTENV.get(name)
    if raw is not None and str(raw).strip() != "":
        return str(raw)
    return os.environ.get(name, default)


class Config:
    """Configuration de base partagée par tous les environnements."""

    # ------------------------------------------------------------------ #
    #  Sécurité                                                           #
    # ------------------------------------------------------------------ #
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or "dev-secret-key-CHANGE-IN-PRODUCTION"
    JWT_SECRET: str = os.environ.get("JWT_SECRET") or "jwt-secret-key-CHANGE-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION: timedelta = timedelta(hours=24)

    # ------------------------------------------------------------------ #
    #  Base de données                                                    #
    # ------------------------------------------------------------------ #
    _DEFAULT_DB = (
        "mssql+pyodbc://localhost/etrans"
        "?driver=ODBC+Driver+17+for+SQL+Server"
    )
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL") or _DEFAULT_DB
    SQLALCHEMY_BINDS: dict = {
        "users": os.environ.get("USERS_DATABASE_URL") or _DEFAULT_DB,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = False

    # ------------------------------------------------------------------ #
    #  Session                                                            #
    # ------------------------------------------------------------------ #
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=24)
    SESSION_REFRESH_EACH_REQUEST: bool = True

    # ------------------------------------------------------------------ #
    #  Email (SMTP)                                                       #
    # ------------------------------------------------------------------ #
    MAIL_SERVER: str = str(_mail_setting("MAIL_SERVER", "smtp.gmail.com"))
    MAIL_PORT: int = int(str(_mail_setting("MAIL_PORT", "587")))
    MAIL_USE_TLS: bool = str(_mail_setting("MAIL_USE_TLS", "True")).strip().lower() in {"1", "true", "yes", "on"}
    MAIL_USERNAME: str | None = _mail_setting("MAIL_USERNAME")
    MAIL_PASSWORD: str | None = _mail_setting("MAIL_PASSWORD")


class DevelopmentConfig(Config):
    """Environnement de développement — debug + SQL verbose."""
    DEBUG: bool = True
    SQLALCHEMY_ECHO: bool = True


class ProductionConfig(Config):
    """Environnement de production — aucun debug."""
    DEBUG: bool = False


class TestingConfig(Config):
    """Environnement de test — base de données en mémoire."""
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_BINDS: dict = {"users": "sqlite:///:memory:"}


config: dict = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
