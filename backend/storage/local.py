"""本地檔案系統儲存後端"""
import os
from typing import Optional
from werkzeug.datastructures import FileStorage
from .base import StorageBackend


class LocalStorage(StorageBackend):
    """
    將附件儲存於本機磁碟。
    upload_folder 範例：/app/backend/uploads
    rel_path 範例：uploads/capa/21/abc123.pdf
    abs_path 解析：os.path.join(root_dir, rel_path)
                  其中 root_dir = os.path.dirname(upload_folder)
    """

    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        # rel_path 以 "uploads/..." 開頭，root_dir 是 uploads/ 的上一層
        self.root_dir = os.path.dirname(upload_folder)

    def _abs(self, rel_path: str) -> str:
        return os.path.join(self.root_dir, rel_path)

    def save(self, file: FileStorage, rel_path: str) -> int:
        abs_path = self._abs(rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        file.save(abs_path)
        return os.path.getsize(abs_path)

    def delete(self, rel_path: str) -> None:
        abs_path = self._abs(rel_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)

    def exists(self, rel_path: str) -> bool:
        return os.path.exists(self._abs(rel_path))

    def get_abs_path(self, rel_path: str) -> Optional[str]:
        p = self._abs(rel_path)
        return p if os.path.exists(p) else None

    def get_download_url(self, rel_path: str) -> Optional[str]:
        return None
