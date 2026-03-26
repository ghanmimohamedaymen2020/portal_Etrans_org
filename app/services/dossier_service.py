"""Service métier pour les dossiers de transport."""
from datetime import datetime

from app import db
from app.models.transport import AvisArrivee, Dossier
from app.repositories.dossier_repository import AvisArriveeRepository, DossierRepository


class DossierService:
    """Logique métier liée aux dossiers et avis d'arrivée."""

    def __init__(self):
        self.dossier_repo = DossierRepository(db)
        self.avis_repo = AvisArriveeRepository(db)

    # ------------------------------------------------------------------ #
    #  Dossiers                                                            #
    # ------------------------------------------------------------------ #

    def list_dossiers(self, page: int = 1, per_page: int = 10):
        """Retourne une page de dossiers."""
        return self.dossier_repo.get_paginated(page=page, per_page=per_page)

    def get_dossier(self, dossier_id: int) -> Dossier:
        return self.dossier_repo.get_or_404(dossier_id)

    def create_dossier(self, data: dict) -> Dossier:
        dossier = Dossier(
            numero=data.get("numero"),
            type_conteneur=data.get("type_conteneur"),
            date_arrivee=data.get("date_arrivee"),
            contient_imo=data.get("contient_imo", False),
            contient_escale=data.get("contient_escale", False),
            contient_fret=data.get("contient_fret", False),
        )
        return self.dossier_repo.add(dossier)

    def valider_transit(self, dossier_id: int) -> Dossier:
        dossier = self.dossier_repo.get_or_404(dossier_id)
        return self.dossier_repo.mark_transit_validated(dossier)

    def valider_documentation(self, dossier_id: int) -> Dossier:
        dossier = self.dossier_repo.get_or_404(dossier_id)
        return self.dossier_repo.mark_doc_validated(dossier)

    # ------------------------------------------------------------------ #
    #  Avis d'arrivée                                                      #
    # ------------------------------------------------------------------ #

    def envoyer_avis(self, avis_id: int) -> AvisArrivee:
        avis = self.avis_repo.get_or_404(avis_id)
        avis.statut = "envoyé"
        avis.dossier.avis_envoye = True
        avis.date_envoi = datetime.utcnow()
        self.avis_repo.save()
        return avis
