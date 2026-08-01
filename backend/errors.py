def build_error_envelope(message: str, code: str, details=None) -> dict:
    """建立唯一的 API 錯誤資料結構，供 helper 與例外處理器共用。"""
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}


class APIError(Exception):
    """API 錯誤基底類別。"""
    def __init__(self, message, code="INTERNAL_ERROR", status_code=500, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def to_dict(self):
        return build_error_envelope(self.message, self.code, self.details)

class ValidationError(APIError):
    def __init__(self, message, details=None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, details=details)

class AuthenticationError(APIError):
    def __init__(self, message="Authentication failed", details=None):
        super().__init__(message, code="AUTH_ERROR", status_code=401, details=details)


class AuthorizationError(APIError):
    def __init__(self, message="權限不足", details=None):
        super().__init__(
            message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )

class NotFoundError(APIError):
    def __init__(self, message="Resource not found", details=None):
        super().__init__(message, code="NOT_FOUND", status_code=404, details=details)
