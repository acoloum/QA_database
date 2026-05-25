"""附件服務 — 共用附件上傳、查詢、下載、刪除"""
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app
from ..extensions import db
from ..models import Attachment

# 允許的 MIME 類型白名單
ALLOWED_MIME_TYPES = {
    # 圖片
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    # 文件
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    # 文字
    'text/plain', 'text/csv',
}

ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'csv',
}

MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
VALID_ENTITY_TYPES = {'capa', 'cara', 'task', 'complaint'}


class AttachmentService:

    @staticmethod
    def _get_upload_dir(entity_type: str, entity_id: int) -> str:
        """取得並確認儲存目錄"""
        base = current_app.config.get('UPLOAD_FOLDER',
               os.path.join(os.path.dirname(current_app.root_path), 'backend', 'uploads'))
        upload_dir = os.path.join(base, entity_type, str(entity_id))
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    @staticmethod
    def _allowed_file(file: FileStorage) -> tuple[bool, str]:
        """驗證檔案類型與大小"""
        # 副檔名檢查
        filename = file.filename or ''
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return False, f'不允許的檔案類型 .{ext}，允許類型：{", ".join(sorted(ALLOWED_EXTENSIONS))}'

        # 讀取大小
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            mb = size / (1024 * 1024)
            return False, f'檔案大小 {mb:.1f} MB 超過上限 10 MB'

        return True, ''

    @staticmethod
    def upload(
        file: FileStorage,
        entity_type: str,
        entity_id: int,
        d_step: Optional[int],
        uploader_id: Optional[int],
    ) -> Dict[str, Any]:
        """上傳附件，回傳附件資訊"""
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f'無效的實體類型：{entity_type}')

        ok, msg = AttachmentService._allowed_file(file)
        if not ok:
            raise ValueError(msg)

        # 產生安全唯一檔名
        original = secure_filename(file.filename or 'unnamed')
        ext = original.rsplit('.', 1)[-1].lower() if '.' in original else ''
        unique_name = f'{uuid.uuid4().hex}.{ext}' if ext else uuid.uuid4().hex
        save_dir = AttachmentService._get_upload_dir(entity_type, entity_id)
        save_path = os.path.join(save_dir, unique_name)

        file.save(save_path)
        file_size = os.path.getsize(save_path)
        mime = file.mimetype or ''
        # 相對路徑儲存（方便移植）
        rel_path = os.path.join('uploads', entity_type, str(entity_id), unique_name)

        att = Attachment(
            entity_type=entity_type,
            entity_id=entity_id,
            d_step=d_step,
            file_name=original,
            file_path=rel_path,
            mime_type=mime,
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
        """查詢實體所有附件，可篩選 D 步驟"""
        q = Attachment.query.filter_by(entity_type=entity_type, entity_id=entity_id)
        if d_step is not None:
            q = q.filter_by(d_step=d_step)
        q = q.order_by(Attachment.d_step.asc().nullsfirst(), Attachment.uploaded_at.asc())
        return [AttachmentService._to_dict(a) for a in q.all()]

    @staticmethod
    def get_file_path(att_id: int) -> Optional[str]:
        """取得附件的絕對路徑（用於 send_file）"""
        att = Attachment.query.get(att_id)
        if not att:
            return None
        base = current_app.config.get('UPLOAD_FOLDER',
               os.path.join(os.path.dirname(current_app.root_path), 'backend', 'uploads'))
        # rel_path 是 uploads/{type}/{id}/{file}
        abs_path = os.path.join(os.path.dirname(base), att.file_path)
        return abs_path if os.path.exists(abs_path) else None

    @staticmethod
    def get_by_id(att_id: int) -> Optional[Dict[str, Any]]:
        att = Attachment.query.get(att_id)
        return AttachmentService._to_dict(att) if att else None

    @staticmethod
    def delete(att_id: int, requester_id: int, requester_role: str) -> bool:
        """刪除附件（僅上傳者或 admin/品保主管可操作）"""
        att = Attachment.query.get(att_id)
        if not att:
            raise ValueError('附件不存在')

        # 權限：上傳者本人 OR admin 角色
        if att.uploaded_by != requester_id and requester_role not in ('admin', 'manager'):
            raise PermissionError('無權限刪除此附件')

        # 刪除實體檔案
        base = current_app.config.get('UPLOAD_FOLDER',
               os.path.join(os.path.dirname(current_app.root_path), 'backend', 'uploads'))
        abs_path = os.path.join(os.path.dirname(base), att.file_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)

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
