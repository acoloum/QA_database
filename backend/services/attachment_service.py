"""附件服務 — 共用附件上傳、查詢、下載、刪除"""
import os
import uuid
from typing import List, Optional, Dict, Any
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app
from ..extensions import db
from ..models import (
    Attachment,
    EquipmentCalibrationRecord,
    MeasurementEquipment,
)
from ..utils import log_audit
from .msa_errors import (
    MsaConflict,
    MsaInternalError,
    MsaNotFound,
    MsaValidationError,
)

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
VALID_ENTITY_TYPES = {
    'capa',
    'task',
    'complaint',
    'pyrometry',
    'measurement_equipment',
    'equipment_calibration',
}
MSA_ATTACHMENT_ENTITY_TYPES = {
    'measurement_equipment',
    'equipment_calibration',
}
CALIBRATION_ATTACHMENT_TYPES = {
    'external': {
        'application/pdf',
        'image/jpeg',
        'image/png',
    },
    'internal': {
        'application/pdf',
        'image/jpeg',
        'image/png',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    },
}


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
        mimetype = (file.mimetype or '').lower()
        if mimetype and mimetype not in ALLOWED_MIME_TYPES:
            return False, f'不允許的 MIME 類型 {mimetype}'
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
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f'無效的實體類型：{entity_type}')

        is_msa = entity_type in MSA_ATTACHMENT_ENTITY_TYPES
        target = None
        if is_msa:
            target = AttachmentService._validate_msa_target(
                entity_type,
                entity_id,
                for_write=True,
            )
        ok, msg = AttachmentService._allowed_file(file)
        if not ok:
            if is_msa:
                raise MsaValidationError(
                    'MSA_ATTACHMENT_FILE_INVALID',
                    msg,
                    details={'entity_type': entity_type},
                )
            raise ValueError(msg)
        if (
            entity_type == 'equipment_calibration'
            and target.data_level == 'detailed'
        ):
            mimetype = (file.mimetype or '').lower()
            allowed_types = CALIBRATION_ATTACHMENT_TYPES.get(
                target.calibration_type,
                set(),
            )
            if mimetype not in allowed_types:
                raise MsaValidationError(
                    'MSA_ATTACHMENT_FILE_INVALID',
                    '附件格式不符合此校正類型',
                    details={
                        'entity_type': entity_type,
                        'calibration_type': target.calibration_type,
                        'mime_type': mimetype,
                        'allowed_mime_types': sorted(allowed_types),
                    },
                )

        original = secure_filename(file.filename or 'unnamed')
        if not original:
            original = 'unnamed'
        if len(original) > 255:
            if is_msa:
                raise MsaValidationError(
                    'MSA_ATTACHMENT_FILE_INVALID',
                    '附件檔名超過允許長度',
                    details={
                        'entity_type': entity_type,
                        'field': 'file_name',
                        'max_length': 255,
                    },
                )
            raise ValueError('附件檔名超過允許長度')
        if purpose is not None and len(purpose) > 30:
            if is_msa:
                raise MsaValidationError(
                    'MSA_ATTACHMENT_FIELD_TOO_LONG',
                    'purpose 超過允許長度',
                    details={'field': 'purpose', 'max_length': 30},
                )
            raise ValueError('purpose 超過允許長度')
        ext = original.rsplit('.', 1)[-1].lower() if '.' in original else ''
        unique_name = f'{uuid.uuid4().hex}.{ext}' if ext else uuid.uuid4().hex
        rel_path = os.path.join('uploads', entity_type, str(entity_id), unique_name)

        storage = _get_storage()
        file_saved = False
        try:
            file_size = storage.save(file, rel_path)
            file_saved = True
            att = Attachment(
                entity_type=entity_type,
                entity_id=entity_id,
                d_step=d_step,
                file_name=original,
                file_path=rel_path,
                mime_type=file.mimetype or '',
                file_size=file_size,
                uploaded_by=uploader_id,
                purpose=purpose,
            )
            db.session.add(att)
            db.session.flush()
            result = AttachmentService._to_dict(att)
            if is_msa:
                log_audit(
                    uploader_id,
                    'upload',
                    'msa_attachment',
                    att.id,
                    new_val=result,
                )
            db.session.commit()
            return result
        except Exception as error:
            db.session.rollback()
            if file_saved:
                try:
                    storage.delete(rel_path)
                except Exception as cleanup_error:
                    if is_msa:
                        raise MsaInternalError(
                            'MSA_ATTACHMENT_COMPENSATION_FAILED',
                            '附件資料儲存失敗，且孤兒檔補償清理失敗',
                            details={
                                'entity_type': entity_type,
                                'entity_id': entity_id,
                                'file_path': rel_path,
                            },
                        ) from cleanup_error
            if is_msa:
                if isinstance(
                    error,
                    (MsaConflict, MsaNotFound, MsaValidationError),
                ):
                    raise
                raise MsaInternalError(
                    'MSA_ATTACHMENT_PERSIST_FAILED',
                    '附件資料未能完成儲存',
                    details={
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                    },
                ) from error
            raise

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

        is_msa = att.entity_type in MSA_ATTACHMENT_ENTITY_TYPES
        if not is_msa:
            snapshot = AttachmentService._model_snapshot(att)
            db.session.delete(att)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            try:
                _get_storage().delete(snapshot['file_path'])
            except Exception as storage_error:
                try:
                    db.session.add(Attachment(**snapshot))
                    db.session.commit()
                except Exception as compensation_error:
                    db.session.rollback()
                    raise RuntimeError('附件刪除失敗且資料庫連結補償失敗') from compensation_error
                raise RuntimeError('附件實體刪除失敗，附件連結已恢復') from storage_error
            return True

        AttachmentService._validate_msa_target(
            att.entity_type,
            att.entity_id,
            for_write=True,
        )
        snapshot = AttachmentService._model_snapshot(att)
        audit_snapshot = AttachmentService._to_dict(att)
        storage = _get_storage()
        try:
            db.session.delete(att)
            log_audit(
                requester_id,
                'delete',
                'msa_attachment',
                att_id,
                old_val=audit_snapshot,
            )
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            raise MsaInternalError(
                'MSA_ATTACHMENT_PERSIST_FAILED',
                '附件刪除未能完成資料庫交易',
                details={'attachment_id': att_id},
            ) from error

        try:
            storage.delete(snapshot['file_path'])
        except Exception as storage_error:
            try:
                restored = Attachment(**snapshot)
                db.session.add(restored)
                log_audit(
                    requester_id,
                    'delete_compensated',
                    'msa_attachment',
                    att_id,
                    old_val={'deleted': True},
                    new_val=audit_snapshot,
                )
                db.session.commit()
            except Exception as compensation_error:
                db.session.rollback()
                raise MsaInternalError(
                    'MSA_ATTACHMENT_COMPENSATION_FAILED',
                    '實體檔刪除失敗，且附件連結補償失敗',
                    details={'attachment_id': att_id},
                ) from compensation_error
            raise MsaInternalError(
                'MSA_ATTACHMENT_STORAGE_DELETE_FAILED',
                '實體檔刪除失敗，附件連結已恢復',
                details={'attachment_id': att_id},
            ) from storage_error
        return True

    @staticmethod
    def _validate_msa_target(
        entity_type: str,
        entity_id: int,
        *,
        for_write: bool,
    ):
        if entity_type == 'measurement_equipment':
            target = db.session.get(MeasurementEquipment, entity_id)
        elif entity_type == 'equipment_calibration':
            target = (
                db.session.execute(
                    db.select(EquipmentCalibrationRecord)
                    .where(EquipmentCalibrationRecord.id == entity_id)
                    .with_for_update()
                )
                .scalar_one_or_none()
            )
        else:
            return None
        if target is None:
            raise MsaNotFound(
                'MSA_ATTACHMENT_TARGET_NOT_FOUND',
                '找不到附件所屬的 MSA 實體',
                details={
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                },
            )
        if (
            for_write
            and entity_type == 'equipment_calibration'
            and target.status == 'approved'
        ):
            raise MsaConflict(
                'MSA_ATTACHMENT_TARGET_IMMUTABLE',
                '核准後的校驗附件不可新增或刪除',
                details={
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'status': target.status,
                },
            )
        return target

    @staticmethod
    def _model_snapshot(att: Attachment) -> Dict[str, Any]:
        return {
            'id': att.id,
            'entity_type': att.entity_type,
            'entity_id': att.entity_id,
            'd_step': att.d_step,
            'file_name': att.file_name,
            'file_path': att.file_path,
            'mime_type': att.mime_type,
            'file_size': att.file_size,
            'uploaded_by': att.uploaded_by,
            'purpose': att.purpose,
            'uploaded_at': att.uploaded_at,
        }

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
            'purpose':     att.purpose,
            'uploaded_at': att.uploaded_at.isoformat() if att.uploaded_at else None,
        }
