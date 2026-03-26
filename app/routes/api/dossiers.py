"""API routes — Dossiers, Avis d'arrivée, Profil utilisateur."""
from flask import jsonify, request
from flask_login import current_user, login_required

from app.routes.api import api_bp
from app.services.dossier_service import DossierService

_svc = DossierService()


# ------------------------------------------------------------------ #
#  Dossiers                                                          #
# ------------------------------------------------------------------ #

@api_bp.route("/dossiers", methods=["GET"])
@login_required
def get_dossiers():
    """Liste paginée des dossiers."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    pagination = _svc.list_dossiers(page=page, per_page=per_page)
    dossiers = [
        {
            "id": d.id,
            "numero": d.numero,
            "type_conteneur": d.type_conteneur,
            "date_arrivee": d.date_arrivee.isoformat(),
            "status": d.status,
            "avis_envoye": d.avis_envoye,
            "contient_imo": d.contient_imo,
        }
        for d in pagination.items
    ]
    return jsonify(
        {
            "dossiers": dossiers,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page,
        }
    )


@api_bp.route("/dossiers/<int:dossier_id>", methods=["GET"])
@login_required
def get_dossier(dossier_id: int):
    d = _svc.get_dossier(dossier_id)
    return jsonify(
        {
            "id": d.id,
            "numero": d.numero,
            "type_conteneur": d.type_conteneur,
            "date_arrivee": d.date_arrivee.isoformat(),
            "status": d.status,
            "avis_envoye": d.avis_envoye,
            "contient_imo": d.contient_imo,
            "validé_transit": d.validé_transit,
            "validé_documentation": d.validé_documentation,
        }
    )


@api_bp.route("/dossiers", methods=["POST"])
@login_required
def create_dossier():
    data = request.get_json() or {}
    dossier = _svc.create_dossier(data)
    return jsonify({"message": "Dossier créé", "id": dossier.id}), 201


@api_bp.route("/dossiers/<int:dossier_id>/valider-transit", methods=["PUT"])
@login_required
def valider_transit(dossier_id: int):
    _svc.valider_transit(dossier_id)
    return jsonify({"message": "Dossier validé par Transit"})


@api_bp.route("/dossiers/<int:dossier_id>/valider-doc", methods=["PUT"])
@login_required
def valider_doc(dossier_id: int):
    _svc.valider_documentation(dossier_id)
    return jsonify({"message": "Dossier validé par Documentation"})


# ------------------------------------------------------------------ #
#  Avis d'arrivée                                                    #
# ------------------------------------------------------------------ #

@api_bp.route("/avis/<int:avis_id>/envoyer", methods=["PUT"])
@login_required
def envoyer_avis(avis_id: int):
    _svc.envoyer_avis(avis_id)
    return jsonify({"message": "Avis envoyé"})


# ------------------------------------------------------------------ #
#  Profil utilisateur                                                #
# ------------------------------------------------------------------ #

@api_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    return jsonify(
        {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role.name,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat(),
            "last_login": (
                current_user.last_login.isoformat()
                if current_user.last_login
                else None
            ),
        }
    )
