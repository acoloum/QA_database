
from flask import jsonify

class APIError(Exception):
    """Base class for API errors"""
    def __init__(self, message, code="INTERNAL_ERROR", status_code=500, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def to_dict(self):
        rv = {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message
            }
        }
        if self.details:
            rv["error"]["details"] = self.details
        return rv

class ValidationError(APIError):
    def __init__(self, message, details=None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, details=details)

class AuthenticationError(APIError):
    def __init__(self, message="Authentication failed", details=None):
        super().__init__(message, code="AUTH_ERROR", status_code=401, details=details)

class NotFoundError(APIError):
    def __init__(self, message="Resource not found", details=None):
        super().__init__(message, code="NOT_FOUND", status_code=404, details=details)
