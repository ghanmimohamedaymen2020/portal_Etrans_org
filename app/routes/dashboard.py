"""Routes du dashboard — redirige vers le bon template selon le rôle."""
from flask import Blueprint, current_app, redirect, render_template, url_for
from flask_login import current_user, login_required
from app.services.permission_service import has_permission
from app.utils.system_logs import get_system_logs_page_data

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _get_template_key_for_role(role_name: str) -> str:
    """Convertit le nom du rôle vers la clé de template correspondante."""
    return (role_name or "management").lower().strip().replace(" ", "_")


def _resolve_dashboard_template(role_name: str) -> str:
    """Résout le template dashboard d'un rôle, avec fallback sûr.

    Les rôles personnalisés peuvent ne pas avoir de template dédié; dans ce cas,
    on utilise le dashboard management pour éviter une erreur 500.
    """
    template_key = _get_template_key_for_role(role_name)
    candidate = f"dashboard/{template_key}_dashboard.html"
    fallback = "dashboard/management_dashboard.html"

    if current_app.jinja_env.loader is not None:
        try:
            current_app.jinja_env.loader.get_source(current_app.jinja_env, candidate)
            return candidate
        except Exception:
            return fallback

    return fallback


@dashboard_bp.route("/", endpoint="index")
@login_required
def index():
    role_name = current_user.role.name if getattr(current_user, "role", None) else "management"
    template_name = _resolve_dashboard_template(role_name)
    return render_template(template_name)


@dashboard_bp.route("/home")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("main/index.html")


@dashboard_bp.route("/excel-module")
@login_required
def excel_module_page():
    if not has_permission(current_user, "excel.view"):
        return redirect(url_for("dashboard.index"))
    return render_template("dashboard/excel_module.html")


@dashboard_bp.route("/system-logs")
@login_required
def system_logs_page():
    """Page détaillée des événements utilisateur/admin et erreurs système."""
    if not getattr(current_user, "role", None) or current_user.role.name != "Admin":
        return redirect(url_for("dashboard.index"))

    payload = get_system_logs_page_data(audit_limit=250, system_limit=200)
    return render_template(
        "dashboard/system_logs.html",
        summary=payload["summary"],
        audit_events=payload["audit_events"],
        system_events=payload["system_events"],
    )
