"""Factory Flask — crée et configure l'application."""
import os

from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config.settings import config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name: str | None = None) -> Flask:
    """Factory function — instancie l'application Flask."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # ------------------------------------------------------------------ #
    #  Extensions                                                         #
    # ------------------------------------------------------------------ #
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."

    # ------------------------------------------------------------------ #
    #  Jinja2 helpers globaux
    # ------------------------------------------------------------------ #
    @app.context_processor
    def inject_permissions():
        """Injecte has_perm() dans tous les templates Jinja2."""
        from flask_login import current_user as cu
        def has_perm(code: str) -> bool:
            if not cu or not cu.is_authenticated:
                return False
            from app.services.permission_service import has_permission
            return has_permission(cu, code)
        return dict(has_perm=has_perm)

    # ------------------------------------------------------------------ #
    #  Blueprints                                                         #
    # ------------------------------------------------------------------ #
    from app.routes import auth_bp, dashboard_bp, api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # ------------------------------------------------------------------ #
    #  Gestion des erreurs                                                #
    # ------------------------------------------------------------------ #
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # ------------------------------------------------------------------ #
    #  Initialisation des rôles par défaut                                #
    # ------------------------------------------------------------------ #
    _seed_roles(app)
    _seed_permissions(app)

    return app


def _seed_permissions(app: Flask) -> None:
    """Insère les permissions manquantes au démarrage."""
    try:
        from app.services.permission_service import seed_permissions
        with app.app_context():
            seed_permissions()
    except Exception:
        pass


def _seed_roles(app: Flask) -> None:
    """Crée les rôles par défaut s'ils n'existent pas encore."""
    default_roles = [
        {"name": "Admin",         "description": "Administration système"},
        {"name": "Timbrage",      "description": "Gestion du timbrage"},
        {"name": "Transit",       "description": "Gestion du transit"},
        {"name": "Documentation", "description": "Gestion de la documentation"},
        {"name": "Commercial",    "description": "Gestion commerciale"},
        {"name": "Management",    "description": "Dashboard management"},
    ]
    try:
        from app.models.user import Role

        with app.app_context():
            existing = {r.name for r in Role.query.all()}
            to_add = [
                Role(name=r["name"], nom=r["name"], description=r["description"])
                for r in default_roles
                if r["name"] not in existing
            ]
            if to_add:
                db.session.add_all(to_add)
                db.session.commit()
    except Exception:
        pass  # La DB n'est peut-être pas encore disponible (ex: tests)
