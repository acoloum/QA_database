"""MSA 服務對 API 與呼叫端公開的穩定錯誤契約。"""


class MsaServiceError(Exception):
    """具 HTTP 語意與可程式判定錯誤碼的 MSA 基底例外。"""

    status_code = 400

    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class MsaNotFound(MsaServiceError):
    """找不到 MSA 受管資源。"""

    status_code = 404


class MsaForbidden(MsaServiceError):
    """目前身分沒有進行 MSA 動作的權限。"""

    status_code = 403


class MsaConflict(MsaServiceError):
    """MSA 動作與既有受管狀態衝突。"""

    status_code = 409


class MsaValidationError(MsaServiceError):
    """MSA 輸入或資格證據未符合正式研究要求。"""

    status_code = 422
