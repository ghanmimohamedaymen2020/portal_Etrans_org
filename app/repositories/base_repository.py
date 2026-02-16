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