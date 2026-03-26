"""Décorateurs d'authentification et d'autorisation."""
from functools import wraps

import jwt
from flask import request, jsonify
from flask_login import current_user

from app.models.user import User
from config.settings import Config


def token_required(f):
    """Décorateur : vérifie le token JWT Bearer dans le header Authorization."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return jsonify({"message": "Token manquant"}), 401

        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"message": "Format de token invalide (Bearer <token>)"}), 401

        token = parts[1]
        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
            user = User.query.get(data["user_id"])
            if not user:
                return jsonify({"message": "Utilisateur introuvable"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expiré"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Token invalide"}), 401

        return f(user, *args, **kwargs)

    return decorated


def role_required(*role_names: str):
    """Décorateur : vérifie que l'utilisateur connecté possède l'un des rôles requis."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"message": "Non authentifié"}), 401
            if current_user.role.name not in role_names:
                return jsonify({"message": "Accès refusé"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
