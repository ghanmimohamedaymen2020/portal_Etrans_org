"""API routes — Gestion des rôles et permissions (admin uniquement)."""
from flask import jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models.user import Role, User
from app.models.permission import Permission, UserPermission, RolePermission
from app.routes.api import api_bp
from app.services.permission_service import (
    set_role_permissions,
    set_user_permission_override,
    remove_user_permission_override,
    get_user_permissions,
    get_permissions_by_category,
    ALL_PERMISSIONS,
)
from app.utils.audit import log_user_event


def _admin_required():
    if not current_user.is_authenticated:
        return jsonify({"message": "Non authentifié"}), 401
    if current_user.role.name != "Admin":
        return jsonify({"message": "Accès réservé aux administrateurs"}), 403
    return None


def _log_admin_event(event_type: str, status: str = "SUCCESS", details: dict | None = None) -> None:
    log_user_event(
        event_type=event_type,
        actor_username=current_user.username if current_user.is_authenticated else "anonymous",
        actor_role=(current_user.role.name if current_user.is_authenticated and current_user.role else "guest"),
        status=status,
        details=details or {},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Catalogue des permissions
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/permissions/catalog", methods=["GET"])
@login_required
def get_permissions_catalog():
    """Retourne toutes les permissions groupées par catégorie."""
    err = _admin_required()
    if err:
        return err
    return jsonify(get_permissions_by_category())


# ─────────────────────────────────────────────────────────────────────────────
#  Rôles — CRUD
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/roles", methods=["GET"])
@login_required
def list_roles():
    """Liste tous les rôles avec leurs permissions."""
    err = _admin_required()
    if err:
        return err

    roles = Role.query.order_by(Role.name).all()
    result = []
    for role in roles:
        perm_codes = [
            rp.permission.code
            for rp in role.role_permissions
            if rp.permission
        ]
        result.append({
            "id":          role.id,
            "name":        role.name,
            "description": role.description,
            "is_system":   role.is_system,
            "user_count":  len(role.users),
            "permissions": perm_codes,
        })
    return jsonify(result)


@api_bp.route("/roles", methods=["POST"])
@login_required
def create_role():
    """Crée un nouveau rôle avec ses permissions."""
    err = _admin_required()
    if err:
        return err

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        _log_admin_event("create_role", "FAILED", {"reason": "missing_name"})
        return jsonify({"message": "Le nom du rôle est requis"}), 400
    if Role.query.filter_by(name=name).first():
        _log_admin_event("create_role", "FAILED", {"reason": "duplicate_role", "role": name})
        return jsonify({"message": f"Le rôle '{name}' existe déjà"}), 409

    role = Role(
        name=name,
        nom=name,
        description=data.get("description", "").strip(),
    )
    db.session.add(role)
    db.session.flush()  # obtenir l'id

    permission_codes = data.get("permissions", [])
    set_role_permissions(role.id, permission_codes)

    db.session.commit()
    _log_admin_event("create_role", "SUCCESS", {"role": role.name, "permissions_count": len(permission_codes)})
    return jsonify({"message": "Rôle créé", "id": role.id, "name": role.name}), 201


@api_bp.route("/roles/<int:role_id>", methods=["PUT"])
@login_required
def update_role(role_id: int):
    """Met à jour un rôle (nom, description, permissions)."""
    err = _admin_required()
    if err:
        return err

    role = Role.query.get_or_404(role_id)
    if role.is_system:
        _log_admin_event("update_role", "FAILED", {"reason": "system_role", "role_id": role_id})
        return jsonify({"message": "Ce rôle système ne peut pas être modifié"}), 403

    data = request.get_json() or {}
    if "name" in data:
        new_name = data["name"].strip()
        existing = Role.query.filter(Role.name == new_name, Role.id != role_id).first()
        if existing:
            _log_admin_event("update_role", "FAILED", {"reason": "duplicate_role", "role_id": role_id, "name": new_name})
            return jsonify({"message": f"Le rôle '{new_name}' existe déjà"}), 409
        role.name = new_name
        role.nom  = new_name
    if "description" in data:
        role.description = data["description"].strip()

    if "permissions" in data:
        set_role_permissions(role.id, data["permissions"])

    db.session.commit()
    _log_admin_event("update_role", "SUCCESS", {"role_id": role_id, "role": role.name})
    return jsonify({"message": "Rôle mis à jour"})


@api_bp.route("/roles/<int:role_id>", methods=["DELETE"])
@login_required
def delete_role(role_id: int):
    """Supprime un rôle (uniquement si aucun utilisateur ne l'utilise)."""
    err = _admin_required()
    if err:
        return err

    role = Role.query.get_or_404(role_id)
    if role.is_system:
        _log_admin_event("delete_role", "FAILED", {"reason": "system_role", "role_id": role_id})
        return jsonify({"message": "Ce rôle système ne peut pas être supprimé"}), 403
    if role.users:
        _log_admin_event("delete_role", "FAILED", {"reason": "role_in_use", "role_id": role_id, "users": len(role.users)})
        return jsonify({
            "message": f"Ce rôle est assigné à {len(role.users)} utilisateur(s). Réassignez-les d'abord."
        }), 409

    role_name = role.name
    db.session.delete(role)
    db.session.commit()
    _log_admin_event("delete_role", "SUCCESS", {"role_id": role_id, "role": role_name})
    return jsonify({"message": "Rôle supprimé"})


@api_bp.route("/roles/<int:role_id>/permissions", methods=["PUT"])
@login_required
def set_role_perms(role_id: int):
    """Remplace les permissions d'un rôle."""
    err = _admin_required()
    if err:
        return err

    role = Role.query.get_or_404(role_id)
    if role.is_system:
        _log_admin_event("set_role_permissions", "FAILED", {"reason": "system_role", "role_id": role_id})
        return jsonify({"message": "Rôle Admin : toutes les permissions sont accordées automatiquement"}), 403

    data = request.get_json() or {}
    codes = data.get("permissions", [])
    set_role_permissions(role_id, codes)
    _log_admin_event("set_role_permissions", "SUCCESS", {"role_id": role_id, "permissions_count": len(codes)})
    return jsonify({"message": "Permissions du rôle mises à jour", "permissions": codes})


# ─────────────────────────────────────────────────────────────────────────────
#  Utilisateurs — overrides de permissions
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/users/<int:user_id>/permissions", methods=["GET"])
@login_required
def get_user_perms(user_id: int):
    """Retourne les permissions effectives d'un utilisateur + ses overrides."""
    err = _admin_required()
    if err:
        return err

    user = User.query.get_or_404(user_id)

    # Permissions effectives (rôle + overrides)
    effective = list(get_user_permissions(user))

    # Overrides individuels
    overrides = [
        {"code": up.permission.code, "granted": up.granted}
        for up in user.user_permissions
        if up.permission
    ]

    # Permissions du rôle de base
    from app.models.permission import PERMISSION_CODES
    if user.role.name == "Admin":
        role_perms = list(PERMISSION_CODES)
    else:
        role_perms = [
            rp.permission.code
            for rp in user.role.role_permissions
            if rp.permission
        ]

    return jsonify({
        "user_id":    user.id,
        "username":   user.username,
        "role":       user.role.name,
        "effective":  effective,
        "overrides":  overrides,
        "role_perms": role_perms,
    })


@api_bp.route("/users/<int:user_id>/permissions", methods=["PUT"])
@login_required
def update_user_perms(user_id: int):
    """Met à jour les overrides de permissions d'un utilisateur.

    Body: { "overrides": [{"code": "card.timbrage", "granted": true}, ...] }
    Pour supprimer un override, ne pas l'inclure dans la liste
    (ou envoyer "reset": true pour tout supprimer).
    """
    err = _admin_required()
    if err:
        return err

    user = User.query.get_or_404(user_id)
    if user.role.name == "Admin":
        _log_admin_event("set_user_permissions", "FAILED", {"reason": "target_is_admin", "target_user_id": user_id})
        return jsonify({"message": "L'Admin a toutes les permissions automatiquement"}), 403

    data = request.get_json() or {}

    if data.get("reset"):
        # Supprimer tous les overrides
        UserPermission.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        _log_admin_event("set_user_permissions", "SUCCESS", {"target_user_id": user_id, "action": "reset"})
        return jsonify({"message": "Overrides réinitialisés"})

    overrides = data.get("overrides", [])
    # Supprimer les anciens overrides
    UserPermission.query.filter_by(user_id=user_id).delete()

    # Insérer les nouveaux
    perm_map = {p.code: p.id for p in Permission.query.all()}
    for ov in overrides:
        code    = ov.get("code", "")
        granted = bool(ov.get("granted", True))
        if code in perm_map:
            db.session.add(UserPermission(
                user_id=user_id,
                permission_id=perm_map[code],
                granted=granted,
            ))

    db.session.commit()
    _log_admin_event(
        "set_user_permissions",
        "SUCCESS",
        {
            "target_user_id": user_id,
            "target_username": user.username,
            "overrides_count": len(overrides),
        },
    )
    return jsonify({"message": "Overrides mis à jour", "count": len(overrides)})

@api_bp.route("/users", methods=["GET"])
@login_required
def list_users_api():
    """Liste tous les utilisateurs (pour le panneau de gestion des permissions)."""
    err = _admin_required()
    if err:
        return err
    users = User.query.order_by(User.username).all()
    return jsonify([{
        "id":       u.id,
        "username": u.username,
        "email":    u.email,
        "role":     u.role.name if u.role else None,
        "role_id":  u.role_id,
        "is_active": u.is_active,
    } for u in users])
