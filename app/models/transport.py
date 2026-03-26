from app import db
from datetime import datetime


class Dossier(db.Model):
    """Modèle pour les dossiers de transport"""
    __tablename__ = "dossiers"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False, index=True)
    type_conteneur = db.Column(db.String(10))           # FCL ou LCL
    date_arrivee = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(50), default="nouveau")  # nouveau, validé, avis_envoyé
    contient_imo = db.Column(db.Boolean, default=False)
    avis_envoye = db.Column(db.Boolean, default=False)
    avis_a_envoyer = db.Column(db.Boolean, default=False)
    version_avis = db.Column(db.Integer, default=1)
    validé_transit = db.Column(db.Boolean, default=False)
    validé_documentation = db.Column(db.Boolean, default=False)
    contient_escale = db.Column(db.Boolean, default=False)
    contient_fret = db.Column(db.Boolean, default=False)
    avis_precedent_id = db.Column(db.Integer, db.ForeignKey("dossiers.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    avis_versions = db.relationship(
        "Dossier", remote_side=[id], backref="avis_precedent"
    )

    def __repr__(self):
        return f"<Dossier {self.numero}>"


class AvisArrivee(db.Model):
    """Modèle pour les avis d'arrivée"""
    __tablename__ = "avis_arrivees"

    id = db.Column(db.Integer, primary_key=True)
    dossier_id = db.Column(db.Integer, db.ForeignKey("dossiers.id"), nullable=False)
    numero_bl = db.Column(db.String(50), unique=True, nullable=False, index=True)
    contenu = db.Column(db.Text)
    statut = db.Column(db.String(50), default="brouillon")   # brouillon, envoyé
    version = db.Column(db.Integer, default=1)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_envoi = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dossier = db.relationship("Dossier", backref=db.backref("avis_arrivees", lazy=True))

    def __repr__(self):
        return f"<AvisArrivee {self.numero_bl}>"
