"""Service RBAC — vérification et gestion des permissions."""
from __future__ import annotations
from functools import wraps
from typing import Set, Dict, List

from flask import jsonify
from flask_login import current_user

from app import db
from app.models.permission import (
    ALL_PERMISSIONS, PERMISSION_CODES,
    Permission, RolePermission, UserPermission,
)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _role_permission_codes(role_id: int) -> Set[str]:
    """Retourne l'ensemble des codes accordés par le rôle."""
    rows = (
        db.session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    return {r.code for r in rows}


def _user_overrides(user_id: int) -> Dict[str, bool]:
    """Retourne les overrides individuels {code: granted}."""
    rows = (
        db.session.query(Permission.code, UserPermission.granted)
        .join(UserPermission, UserPermission.permission_id == Permission.id)
        .filter(UserPermission.user_id == user_id)
        .all()
    )
    return {r.code: r.granted for r in rows}


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_user_permissions(user) -> Set[str]:
    """Retourne l'ensemble final des codes autorisés pour un utilisateur.

    Logique :
    1. Admin → tout autorisé.
    2. Sinon : permissions du rôle + overrides utilisateur.
       - override granted=True  → ajoute la permission
       - override granted=False → retire la permission
    """
    if user.role.name == "Admin":
        return PERMISSION_CODES.copy()

    perms = _role_permission_codes(user.role_id)
    overrides = _user_overrides(user.id)

    for code, granted in overrides.items():
        if granted:
            perms.add(code)
        else:
            perms.discard(code)

    return perms


def has_permission(user, code: str) -> bool:
    """Vérifie si un utilisateur a une permission donnée."""
    if user.role.name == "Admin":
        return True
    perms = get_user_permissions(user)
    return code in perms


# ---------------------------------------------------------------------------
# Décorateur pour les routes API
# ---------------------------------------------------------------------------

def permission_required(code: str):
    """Décorateur Flask — bloque la route si l'utilisateur n'a pas la permission."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"message": "Non authentifié"}), 401
            if not has_permission(current_user, code):
                return jsonify({"message": "Accès refusé", "permission": code}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Seed du catalogue en base
# ---------------------------------------------------------------------------

def seed_permissions() -> None:
    """Insère les permissions manquantes et resynchronise les libellés existants."""
    existing_by_code = {p.code: p for p in Permission.query.all()}
    changed = False

    for code, cat, label in ALL_PERMISSIONS:
        perm = existing_by_code.get(code)
        if not perm:
            db.session.add(Permission(code=code, category=cat, label=label))
            changed = True
            continue

        # Maintient les intitulés/catégories cohérents avec le catalogue applicatif.
        if perm.category != cat:
            perm.category = cat
            changed = True
        if perm.label != label:
            perm.label = label
            changed = True

    if changed:
        db.session.commit()


# ---------------------------------------------------------------------------
# CRUD rôles (utilisé par les routes admin)
# ---------------------------------------------------------------------------

def set_role_permissions(role_id: int, permission_codes: List[str]) -> None:
    """Remplace toutes les permissions d'un rôle par la liste fournie."""
    # Supprimer les anciennes
    RolePermission.query.filter_by(role_id=role_id).delete()

    # Insérer les nouvelles
    perm_map = {p.code: p.id for p in Permission.query.filter(Permission.code.in_(permission_codes)).all()}
    for code in permission_codes:
        if code in perm_map:
            db.session.add(RolePermission(role_id=role_id, permission_id=perm_map[code]))

    db.session.commit()


def set_user_permission_override(user_id: int, permission_code: str, granted: bool) -> None:
    """Crée ou met à jour un override de permission pour un utilisateur."""
    perm = Permission.query.filter_by(code=permission_code).first()
    if not perm:
        raise ValueError(f"Permission inconnue : {permission_code}")

    override = UserPermission.query.filter_by(
        user_id=user_id, permission_id=perm.id
    ).first()

    if override:
        override.granted = granted
    else:
        db.session.add(UserPermission(user_id=user_id, permission_id=perm.id, granted=granted))

    db.session.commit()


def remove_user_permission_override(user_id: int, permission_code: str) -> None:
    """Supprime un override utilisateur (revient au comportement du rôle)."""
    perm = Permission.query.filter_by(code=permission_code).first()
    if perm:
        UserPermission.query.filter_by(user_id=user_id, permission_id=perm.id).delete()
        db.session.commit()


def get_permissions_by_category() -> Dict[str, List[dict]]:
    """Retourne toutes les permissions groupées par catégorie."""
    result: Dict[str, List[dict]] = {}
    for code, cat, label in ALL_PERMISSIONS:
        result.setdefault(cat, []).append({"code": code, "label": label})
    return result
