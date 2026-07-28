"""校正服務對 API 與呼叫端公開的穩定錯誤契約。"""


class CalibrationServiceError(Exception):
    """具 HTTP 語意與可程式判定錯誤碼的校正服務基底例外。"""

    status_code = 400

    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class CalibrationNotFound(CalibrationServiceError):
    """找不到校正受管資源。"""

    status_code = 404


class CalibrationForbidden(CalibrationServiceError):
    """目前身分不得執行指定校正動作。"""

    status_code = 403


class CalibrationConflict(CalibrationServiceError):
    """校正動作與既有受管狀態衝突。"""

    status_code = 409


class CalibrationValidationError(CalibrationServiceError):
    """校正輸入或資格證據未符合受控要求。"""

    status_code = 422
