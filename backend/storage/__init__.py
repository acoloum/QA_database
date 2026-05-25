"""儲存後端工廠 — 依設定建立對應的 StorageBackend 實例"""
import os
from .base import StorageBackend
from .local import LocalStorage


def create_storage_backend(config: dict) -> StorageBackend:
    """
    從 Flask app.config 建立儲存後端。
    目前支援 'local'（預設）。
    未來新增 's3' / 'azure' 時只需在此加 elif。

    設定範例（.env）：
        STORAGE_BACKEND=local
        UPLOAD_FOLDER=/data/uploads          # 選填，有預設值
    """
    backend_type = config.get('STORAGE_BACKEND_TYPE', 'local')

    if backend_type == 'local':
        upload_folder = config.get(
            'UPLOAD_FOLDER',
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'),
        )
        return LocalStorage(upload_folder)

    raise ValueError(f'未知的儲存後端類型：{backend_type}，目前支援：local')
