"""Modèles RBAC — Permissions, RolePermission, UserPermission."""
from datetime import datetime
from app import db


# ---------------------------------------------------------------------------
# Catalogue de toutes les permissions disponibles
# ---------------------------------------------------------------------------
ALL_PERMISSIONS = [
    # ── Cartes KPI ──────────────────────────────────────────────────────────
    ("card.freight",            "Carte",    "Freight (mois + année)"),
    ("card.timbrage",           "Carte",    "Factures Timbrage (mois)"),
    ("card.agent",              "Carte",    "Factures Agent (mois)"),
    ("card.surestaries",        "Carte",    "Factures Surestarie (mois)"),
    ("card.magasinage",         "Carte",    "Factures Magasinage (mois)"),
    ("card.avis_non_timbres",   "Carte",    "Avis non timbrés"),
    ("card.marchandises",       "Carte",    "Marchandises non retirées"),
    # ── Graphiques ──────────────────────────────────────────────────────────
    ("chart.ca_mensuel",        "Graphique","CA mensuel (histogramme)"),
    ("chart.ca_activite",       "Graphique","CA par activité (donut)"),
    ("chart.freight_devise",    "Graphique","Marge fret par devise"),
    # ── Listes / détails au clic ────────────────────────────────────────────
    ("detail.factures_ff",      "Détail",   "Détail factures FF (clic barre)"),
    ("detail.factures_aa",      "Détail",   "Détail Avis AA (clic carte)"),
    ("detail.freight",          "Détail",   "Détail fret par commercial"),
    ("detail.timbrage",         "Détail",   "Liste Timbrage (page liste)"),
    ("detail.agent",            "Détail",   "Liste Agent (page liste)"),
    ("detail.magasinage",       "Détail",   "Liste Magasinage (page liste)"),
    ("detail.surestaries",      "Détail",   "Liste Surestaries (page liste)"),
    # ── Export ──────────────────────────────────────────────────────────────
    ("export.csv",              "Export",   "Export CSV"),
    ("export.xlsx",             "Export",   "Export XLSX"),
]

PERMISSION_CODES = {code for code, *_ in ALL_PERMISSIONS}


class Permission(db.Model):
    """Catalogue de toutes les permissions de l'application."""
    __tablename__ = "permissions"
    __bind_key__ = "users"

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(60), unique=True, nullable=False, index=True)
    category    = db.Column(db.String(30), nullable=False)   # Carte / Graphique / Détail / Export
    label       = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f"<Permission {self.code}>"


class RolePermission(db.Model):
    """Permissions accordées à un rôle (base)."""
    __tablename__ = "role_permissions"
    __bind_key__ = "users"

    id              = db.Column(db.Integer, primary_key=True)
    role_id         = db.Column(db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id   = db.Column(db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)

    role        = db.relationship("Role", backref=db.backref("role_permissions", lazy="dynamic", cascade="all, delete-orphan"))
    permission  = db.relationship("Permission", backref=db.backref("role_permissions", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )


class UserPermission(db.Model):
    """Override de permissions au niveau d'un utilisateur individuel.

    granted=True  → permission accordée même si le rôle ne la donne pas
    granted=False → permission retirée même si le rôle la donne
    """
    __tablename__ = "user_permissions"
    __bind_key__ = "users"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_id   = db.Column(db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    granted         = db.Column(db.Boolean, nullable=False, default=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user        = db.relationship("User", backref=db.backref("user_permissions", lazy="dynamic", cascade="all, delete-orphan"))
    permission  = db.relationship("Permission", backref=db.backref("user_permissions", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),
    )
