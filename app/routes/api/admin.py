"""API Admin — statistiques et KPIs pour le dashboard administrateur."""
from datetime import datetime, timedelta

from flask import jsonify
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models.user import Role, User
from app.routes.api import api_bp
from app.utils.system_logs import collect_system_logs_details


@api_bp.route("/admin/summary", methods=["GET"])
@login_required
def admin_summary():
    """Retourne les KPIs du dashboard admin."""
    if current_user.role.name != "Admin":
        return jsonify({"error": "Accès refusé"}), 403

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)

    # ── KPIs principaux ──────────────────────────────────────────────
    total_users = db.session.query(func.count(User.id)).scalar() or 0
    active_users = db.session.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    connexions_today = db.session.query(func.count(User.id)).filter(
        User.last_login >= today_start
    ).scalar() or 0
    active_users_30d = db.session.query(func.count(User.id)).filter(
        User.last_login >= last_30_days
    ).scalar() or 0

    # Utilisateurs connectés dans les 15 dernières minutes
    connected_now = db.session.query(func.count(User.id)).filter(
        User.last_login >= now - timedelta(minutes=15)
    ).scalar() or 0

    # ── Activité des 7 derniers jours ────────────────────────────────
    activity_labels = []
    activity_data = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.session.query(func.count(User.id)).filter(
            User.last_login >= day_start,
            User.last_login < day_end
        ).scalar() or 0
        activity_labels.append(day.strftime("%d/%m"))
        activity_data.append(count)

    # ── Répartition par rôle ─────────────────────────────────────────
    roles_query = (
        db.session.query(Role.name, func.count(User.id))
        .join(User, User.role_id == Role.id)
        .group_by(Role.name)
        .all()
    )
    roles_labels = [r[0] for r in roles_query]
    roles_data = [r[1] for r in roles_query]
    logs_details = collect_system_logs_details()

    return jsonify({
        "total_users":      total_users,
        "active_users":     active_users,
        "active_users_30d": active_users_30d,
        "connected_now":    connected_now,
        "connexions_today": connexions_today,
        "total_dossiers":   0,   # Requiert accès Dashboard DB externe
        "activity": {
            "labels": activity_labels,
            "data":   activity_data,
        },
        "roles": {
            "labels": roles_labels,
            "data":   roles_data,
        },
        "system_logs": logs_details,
    })
