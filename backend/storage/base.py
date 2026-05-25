"""儲存後端抽象介面"""
from abc import ABC, abstractmethod
from typing import Optional
from werkzeug.datastructures import FileStorage


class StorageBackend(ABC):
    """
    所有儲存後端必須實作此介面。
    rel_path 格式固定為 uploads/{entity_type}/{entity_id}/{filename}，
    與資料庫 file_path 欄位一致。
    """

    @abstractmethod
    def save(self, file: FileStorage, rel_path: str) -> int:
        """儲存檔案，回傳 bytes 大小"""

    @abstractmethod
    def delete(self, rel_path: str) -> None:
        """刪除檔案（檔案不存在時靜默忽略）"""

    @abstractmethod
    def exists(self, rel_path: str) -> bool:
        """檔案是否存在"""

    @abstractmethod
    def get_abs_path(self, rel_path: str) -> Optional[str]:
        """
        取得可直接傳給 Flask send_file() 的絕對路徑。
        本地儲存回傳路徑；雲端儲存回傳 None。
        """

    @abstractmethod
    def get_download_url(self, rel_path: str) -> Optional[str]:
        """
        取得可直接 redirect 的下載 URL。
        雲端儲存回傳 presigned URL；本地儲存回傳 None。
        """
