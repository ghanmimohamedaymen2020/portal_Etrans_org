"""Service métier pour l'authentification et la gestion des utilisateurs."""
import re
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from flask import current_app, has_request_context, url_for

from app import db
from app.models.user import PasswordResetToken, Role, User
from app.utils.email import send_email
from app.utils.exceptions import ValidationError


PASSWORD_REGEX = {
    "min_length": 8,
    "uppercase": re.compile(r"[A-Z]"),
    "lowercase": re.compile(r"[a-z]"),
    "digit": re.compile(r"[0-9]"),
    "special": re.compile(r"[!@#$%^&*]"),
}


class AuthService:
    """Authentification, changement/réinitialisation de mot de passe, gestion users."""

    # ------------------------------------------------------------------ #
    #  Validation mot de passe                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def validate_password(password: str) -> List[str]:
        """Retourne une liste d'erreurs de validation (vide = OK)."""
        errors = []
        if len(password) < PASSWORD_REGEX["min_length"]:
            errors.append("Au moins 8 caractères.")
        if not PASSWORD_REGEX["uppercase"].search(password):
            errors.append("Au moins une majuscule.")
        if not PASSWORD_REGEX["lowercase"].search(password):
            errors.append("Au moins une minuscule.")
        if not PASSWORD_REGEX["digit"].search(password):
            errors.append("Au moins un chiffre.")
        if not PASSWORD_REGEX["special"].search(password):
            errors.append("Au moins un caractère spécial (!@#$%^&*).")
        return errors

    # ------------------------------------------------------------------ #
    #  Mot de passe oublié / reset                                        #
    # ------------------------------------------------------------------ #

    def send_reset_email(self, email: str) -> bool:
        """Génère un token de reset et envoie l'e-mail. Retourne True si user trouvé."""
        user = User.query.filter_by(email=email).first()
        if not user:
            return False

        token_str = secrets.token_urlsafe(32)
        token = PasswordResetToken(
            user_id=user.id,
            token=token_str,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.session.add(token)
        db.session.commit()

        if has_request_context():
            reset_link = url_for("auth.reset_password", token=token_str, _external=True)
        else:
            base_url = current_app.config.get("APP_BASE_URL", "http://localhost:5000")
            reset_link = f"{base_url.rstrip('/')}/reset-password/{token_str}"

        sent = send_email(
            recipient=email,
            subject="Réinitialisation de votre mot de passe",
            body=(
                "Cliquez sur ce lien pour réinitialiser votre mot de passe : "
                f"{reset_link}"
            ),
            html=(
                "<p>Cliquez sur ce lien pour réinitialiser votre mot de passe :</p>"
                f"<p><a href=\"{reset_link}\">{reset_link}</a></p>"
            ),
        )
        return sent

    @staticmethod
    def send_password_changed_email(email: str, username: str) -> bool:
        """Envoie une notification après changement de mot de passe."""
        return send_email(
            recipient=email,
            subject="Votre mot de passe a été modifié",
            body=(
                f"Bonjour {username},\n\n"
                "Votre mot de passe E-Trans vient d'etre modifie.\n"
                "Si ce n'etait pas vous, contactez immediatement l'administrateur."
            ),
            html=(
                f"<p>Bonjour {username},</p>"
                "<p>Votre mot de passe E-Trans vient d'etre modifie.</p>"
                "<p>Si ce n'etait pas vous, contactez immediatement l'administrateur.</p>"
            ),
        )

    def reset_password(self, token_str: str, new_password: str) -> None:
        """Réinitialise le mot de passe via un token valide."""
        token = PasswordResetToken.query.filter_by(token=token_str).first()
        if not token or not token.is_valid():
            raise ValidationError("Token invalide ou expiré.")

        errors = self.validate_password(new_password)
        if errors:
            raise ValidationError(" ".join(errors))

        token.user.set_password(new_password)
        token.is_used = True
        db.session.commit()

        # Notification non bloquante: le reset reste valide meme si l'email echoue.
        self.send_password_changed_email(token.user.email, token.user.username)

    # ------------------------------------------------------------------ #
    #  Gestion des utilisateurs (admin)                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_user(username: str, email: str, password: str, role_id: int) -> User:
        errors = AuthService.validate_password(password)
        if errors:
            raise ValidationError(" ".join(errors))

        user = User(username=username, email=email, role_id=role_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def update_user(user_id: int, data: dict) -> User:
        user = User.query.get_or_404(user_id)
        if "username" in data:
            user.username = (data["username"] or "").strip()
        if "email" in data:
            user.email = (data["email"] or "").strip()
        if "role_id" in data:
            try:
                new_role_id = int(data["role_id"])
            except (TypeError, ValueError):
                raise ValidationError("Rôle invalide.")

            role = Role.query.get(new_role_id)
            if not role:
                raise ValidationError("Rôle introuvable.")

            user.role_id = role.id

        # Le formulaire admin envoie "password". On garde aussi "new_password"
        # pour compatibilité avec d'autres appels éventuels.
        raw_password = (data.get("password") or data.get("new_password") or "").strip()
        if raw_password:
            errors = AuthService.validate_password(raw_password)
            if errors:
                raise ValidationError(" ".join(errors))
            user.set_password(raw_password)

        db.session.commit()
        return user

    @staticmethod
    def toggle_user_status(user_id: int) -> User:
        user = User.query.get_or_404(user_id)
        user.is_active = not user.is_active
        db.session.commit()
        return user

    @staticmethod
    def delete_user(user_id: int) -> None:
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
