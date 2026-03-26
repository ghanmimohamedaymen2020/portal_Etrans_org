"""Repository pour les Dossiers et AvisArrivee."""
from typing import Optional

from app.models.transport import AvisArrivee, Dossier
from app.repositories.base import BaseRepository


class DossierRepository(BaseRepository):
    """Accès base de données pour les dossiers de transport."""

    def find_by_numero(self, numero: str) -> Optional[Dossier]:
        return Dossier.query.filter_by(numero=numero).first()

    def get_paginated(self, page: int = 1, per_page: int = 10):
        return Dossier.query.paginate(page=page, per_page=per_page)

    def get_or_404(self, dossier_id: int) -> Dossier:
        return Dossier.query.get_or_404(dossier_id)

    def mark_transit_validated(self, dossier: Dossier) -> Dossier:
        dossier.validé_transit = True
        if (
            dossier.validé_transit
            and dossier.validé_documentation
            and dossier.contient_escale
        ):
            dossier.avis_a_envoyer = True
        self.save()
        return dossier

    def mark_doc_validated(self, dossier: Dossier) -> Dossier:
        dossier.validé_documentation = True
        if (
            dossier.validé_transit
            and dossier.validé_documentation
            and dossier.contient_escale
        ):
            dossier.avis_a_envoyer = True
        self.save()
        return dossier


class AvisArriveeRepository(BaseRepository):
    """Accès base de données pour les avis d'arrivée."""

    def get_or_404(self, avis_id: int) -> AvisArrivee:
        return AvisArrivee.query.get_or_404(avis_id)
