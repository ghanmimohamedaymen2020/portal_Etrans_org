"""Exceptions métier centralisées de l'application."""


class AppError(Exception):
    """Exception de base de l'application."""
    http_code: int = 500

    def __init__(self, message: str = "Une erreur interne est survenue."):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """Ressource introuvable (404)."""
    http_code = 404

    def __init__(self, message: str = "Ressource introuvable."):
        super().__init__(message)


class ValidationError(AppError):
    """Données invalides (400)."""
    http_code = 400

    def __init__(self, message: str = "Données invalides."):
        super().__init__(message)


class AuthenticationError(AppError):
    """Authentification échouée (401)."""
    http_code = 401

    def __init__(self, message: str = "Authentification requise."):
        super().__init__(message)


class PermissionDeniedError(AppError):
    """Accès refusé (403)."""
    http_code = 403

    def __init__(self, message: str = "Accès refusé."):
        super().__init__(message)


class DatabaseError(AppError):
    """Erreur base de données (500)."""
    http_code = 500

    def __init__(self, message: str = "Erreur de base de données."):
        super().__init__(message)
