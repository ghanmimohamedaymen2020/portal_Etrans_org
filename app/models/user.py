from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from config.settings import Config


class Role(db.Model):
    """Rôle utilisateur — entièrement géré par l'admin."""
    __tablename__ = "roles"
    __bind_key__ = "users"

    id          = db.Column(db.Integer, primary_key=True)
    nom         = db.Column(db.String(50))
    name        = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Les rôles protégés sont déterminés par convention métier plutôt que par une colonne DB.
    SYSTEM_ROLE_NAMES = {"admin"}

    @property
    def is_system(self) -> bool:
        return (self.name or "").strip().lower() in self.SYSTEM_ROLE_NAMES

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    """Modèle utilisateur"""
    __tablename__ = "users"
    __bind_key__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    role = db.relationship("Role", backref=db.backref("users", lazy=True))

    def set_password(self, password: str) -> None:
        """Hash et définit le mot de passe"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Vérifie le mot de passe"""
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self, expires_in: int = 3600) -> str:
        """Génère un token de réinitialisation de mot de passe"""
        return jwt.encode(
            {"user_id": self.id, "exp": datetime.utcnow().timestamp() + expires_in},
            Config.SECRET_KEY,
            algorithm=Config.JWT_ALGORITHM,
        )

    def generate_jwt_token(self) -> str:
        """Génère un token JWT"""
        return jwt.encode(
            {"user_id": self.id, "role": self.role.name},
            Config.JWT_SECRET,
            algorithm=Config.JWT_ALGORITHM,
        )

    def has_permission(self, code: str) -> bool:
        """Vérifie si cet utilisateur a une permission donnée (raccourci template)."""
        from app.services.permission_service import has_permission
        return has_permission(self, code)

    def get_permissions(self):
        """Retourne l'ensemble des codes de permission de cet utilisateur."""
        from app.services.permission_service import get_user_permissions
        return get_user_permissions(self)

    def __repr__(self):
        return f"<User {self.username}>"


class PasswordResetToken(db.Model):
    """Modèle pour les tokens de réinitialisation de mot de passe"""
    __tablename__ = "password_reset_tokens"
    __bind_key__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User", backref=db.backref("reset_tokens", lazy=True))

    def is_valid(self) -> bool:
        """Vérifie si le token est valide"""
        return not self.is_used and datetime.utcnow() < self.expires_at
