"""Application custom exceptions."""


class AppError(Exception):
    """Base application exception."""


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)


class DatabaseError(AppError):
    def __init__(self, message: str = "Database error"):
        super().__init__(message)
class CustomException(Exception):
    """Base class for all custom exceptions."""
    pass

class NotFoundException(CustomException):
    """Exception raised for not found errors."""
    def __init__(self, message="Resource not found"):
        self.message = message
        super().__init__(self.message)

class ValidationException(CustomException):
    """Exception raised for validation errors."""
    def __init__(self, message="Validation error occurred"):
        self.message = message
        super().__init__(self.message)

class AuthenticationException(CustomException):
    """Exception raised for authentication errors."""
    def __init__(self, message="Authentication failed"):
        self.message = message
        super().__init__(self.message)

class PermissionDeniedException(CustomException):
    """Exception raised for permission denied errors."""
    def __init__(self, message="Permission denied"):
        self.message = message
        super().__init__(self.message)

class DatabaseException(CustomException):
    """Exception raised for database errors."""
    def __init__(self, message="Database error occurred"):
        self.message = message
        super().__init__(self.message)