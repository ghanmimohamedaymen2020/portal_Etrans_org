"""Blueprints de l'application."""
from flask import Blueprint

# Blueprint auth (sans préfixe URL — /, /login, /logout …)
auth_bp = Blueprint("auth", __name__, url_prefix="")

# Importer les routes pour les enregistrer sur auth_bp
from app.routes import auth  # noqa: F401, E402

# Re-exporter dashboard_bp depuis son module
from app.routes.dashboard import dashboard_bp  # noqa: F401, E402

# Re-exporter api_bp depuis le sous-paquet
from app.routes.api import api_bp  # noqa: F401, E402

__all__ = ["auth_bp", "dashboard_bp", "api_bp"]
