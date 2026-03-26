"""API Blueprint — toutes les routes /api/* sont enregistrées ici."""
from flask import Blueprint

api_bp = Blueprint("api", __name__)

# Importer les modules de routes pour les enregistrer sur le blueprint
from app.routes.api import dossiers     # noqa: F401, E402
from app.routes.api import factures     # noqa: F401, E402
from app.routes.api import freight      # noqa: F401, E402
from app.routes.api import admin        # noqa: F401, E402
from app.routes.api import permissions  # noqa: F401, E402
