"""Repository de base — opérations CRUD communes."""
from typing import Any, Optional, Type


class BaseRepository:
    """Encapsule les opérations SQLAlchemy répétitives.

    Usage :
        class DossierRepository(BaseRepository):
            def find_by_numero(self, numero):
                return Dossier.query.filter_by(numero=numero).first()
    """

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #

    def add(self, instance: Any) -> Any:
        """Persiste une nouvelle instance et retourne l'objet sauvegardé."""
        self.db.session.add(instance)
        self.db.session.commit()
        return instance

    def get(self, model: Type[Any], pk: Any) -> Optional[Any]:
        """Récupère une instance par sa clé primaire."""
        return self.db.session.get(model, pk)

    def save(self) -> None:
        """Commit la session en cours (après des modifications manuelles)."""
        self.db.session.commit()

    def delete(self, instance: Any) -> None:
        """Supprime une instance et commit."""
        self.db.session.delete(instance)
        self.db.session.commit()

    def rollback(self) -> None:
        """Annule la transaction en cours."""
        self.db.session.rollback()
