"""附件服務 — 共用附件上傳、查詢、下載、刪除"""
import os
import uuid
from typing import List, Optional, Dict, Any
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app
from ..extensions import db
from ..models import Attachment

# 允許的 MIME 類型白名單
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv',
}

ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'csv',
}

MAX_FILE_SIZE    = 10 * 1024 * 1024
VALID_ENTITY_TYPES = {'capa', 'task', 'complaint'}


def _get_storage():
    """取得目前 app 設定的儲存後端"""
    return current_app.config['STORAGE']


class AttachmentService:

    @staticmethod
    def _allowed_file(file: FileStorage) -> tuple[bool, str]:
        filename = file.filename or ''
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return False, f'不允許的檔案類型 .{ext}，允許類型：{", ".join(sorted(ALLOWED_EXTENSIONS))}'
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            return False, f'檔案大小 {size / 1024 / 1024:.1f} MB 超過上限 10 MB'
        return True, ''

    @staticmethod
    def upload(
        file: FileStorage,
        entity_type: str,
        entity_id: int,
        d_step: Optional[int],
        uploader_id: Optional[int],
    ) -> Dict[str, Any]:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f'無效的實體類型：{entity_type}')

        ok, msg = AttachmentService._allowed_file(file)
        if not ok:
            raise ValueError(msg)

        original = secure_filename(file.filename or 'unnamed')
        ext = original.rsplit('.', 1)[-1].lower() if '.' in original else ''
        unique_name = f'{uuid.uuid4().hex}.{ext}' if ext else uuid.uuid4().hex
        rel_path = os.path.join('uploads', entity_type, str(entity_id), unique_name)

        file_size = _get_storage().save(file, rel_path)

        att = Attachment(
            entity_type=entity_type,
            entity_id=entity_id,
            d_step=d_step,
            file_name=original,
            file_path=rel_path,
            mime_type=file.mimetype or '',
            file_size=file_size,
            uploaded_by=uploader_id,
        )
        db.session.add(att)
        db.session.commit()
        return AttachmentService._to_dict(att)

    @staticmethod
    def list_by_entity(
        entity_type: str,
        entity_id: int,
        d_step: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        q = Attachment.query.filter_by(entity_type=entity_type, entity_id=entity_id)
        if d_step is not None:
            q = q.filter_by(d_step=d_step)
        q = q.order_by(Attachment.d_step.asc().nullsfirst(), Attachment.uploaded_at.asc())
        return [AttachmentService._to_dict(a) for a in q.all()]

    @staticmethod
    def get_file_path(att_id: int) -> Optional[str]:
        """取得可傳給 send_file() 的絕對路徑；雲端後端回傳 None"""
        att = db.session.get(Attachment, att_id)
        if not att:
            return None
        return _get_storage().get_abs_path(att.file_path)

    @staticmethod
    def get_download_url(att_id: int) -> Optional[str]:
        """取得可直接 redirect 的下載 URL；本地後端回傳 None"""
        att = db.session.get(Attachment, att_id)
        if not att:
            return None
        return _get_storage().get_download_url(att.file_path)

    @staticmethod
    def get_by_id(att_id: int) -> Optional[Dict[str, Any]]:
        att = db.session.get(Attachment, att_id)
        return AttachmentService._to_dict(att) if att else None

    @staticmethod
    def delete(att_id: int, requester_id: int, requester_role: str) -> bool:
        att = db.session.get(Attachment, att_id)
        if not att:
            raise ValueError('附件不存在')
        if att.uploaded_by != requester_id and requester_role not in ('admin', 'manager'):
            raise PermissionError('無權限刪除此附件')

        _get_storage().delete(att.file_path)
        db.session.delete(att)
        db.session.commit()
        return True

    @staticmethod
    def _to_dict(att: Attachment) -> Dict[str, Any]:
        return {
            'id':          att.id,
            'entity_type': att.entity_type,
            'entity_id':   att.entity_id,
            'd_step':      att.d_step,
            'file_name':   att.file_name,
            'file_path':   att.file_path,
            'mime_type':   att.mime_type,
            'file_size':   att.file_size,
            'uploaded_by': att.uploaded_by,
            'uploaded_at': att.uploaded_at.isoformat() if att.uploaded_at else None,
        }
