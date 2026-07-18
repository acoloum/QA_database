"""SPC 服務層可供 API 穩定對應的錯誤契約。"""


class SpcServiceError(Exception):
    """SPC 服務基礎錯誤，包含機器可讀代碼與 HTTP 狀態。"""

    status_code = 400

    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class SpcNotFound(SpcServiceError):
    status_code = 404


class SpcForbidden(SpcServiceError):
    status_code = 403


class SpcConflict(SpcServiceError):
    status_code = 409


class SpcValidationError(SpcServiceError):
    status_code = 422
