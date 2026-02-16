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