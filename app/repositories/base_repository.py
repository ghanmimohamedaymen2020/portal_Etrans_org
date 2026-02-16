"""Simple BaseRepository to centralize common DB operations.

This is intentionally minimal — adapt to your application's `db` (SQLAlchemy) API.
"""
from typing import Type, Any, Optional


class BaseRepository:
    def __init__(self, db):
        """Initialize with SQLAlchemy `db` (the instance from `flask_sqlalchemy`)."""
        self.db = db

    def add(self, instance: Any) -> Any:
        self.db.session.add(instance)
        self.db.session.commit()
        return instance

    def get(self, model: Type[Any], pk: Any) -> Optional[Any]:
        return self.db.session.get(model, pk)

    def update(self) -> None:
        self.db.session.commit()

    def delete(self, instance: Any) -> None:
        self.db.session.delete(instance)
        self.db.session.commit()
class BaseRepository:
    def __init__(self, database):
        self.database = database

    def add(self, item):
        self.database.session.add(item)
        self.database.session.commit()

    def get(self, model, item_id):
        return self.database.session.query(model).get(item_id)

    def update(self, item):
        self.database.session.commit()

    def delete(self, item):
        self.database.session.delete(item)
        self.database.session.commit()