"""附件路由 — 上傳、查詢、下載、刪除"""
from functools import wraps

from flask import Blueprint, jsonify, request, send_file, redirect
from typing import Optional
from ..services.attachment_service import AttachmentService
from ..services.attachment_service import MSA_ATTACHMENT_ENTITY_TYPES
from ..services.msa_errors import MsaInternalError, MsaServiceError
from ..authorization import require_permissions
from ..errors import AuthorizationError
from ..utils import auth_required
from ..models import Role


def _parse_d_step(raw: Optional[str]) -> Optional[int]:
    """將 'D0'、'D2'、'2' 等格式統一轉為整數；None 或空字串回傳 None"""
    if raw is None or raw == '':
        return None
    return int(raw.lstrip('Dd'))

attachment_bp = Blueprint('attachment', __name__)


_ENTITY_PERMISSION_PREFIX = {
    'capa': 'capa',
    'task': 'task',
    'complaint': 'complaint',
    'pyrometry': 'pyrometry',
    'measurement_equipment': 'msa',
    'equipment_calibration': 'msa',
}


def _has_entity_permission(current_user, entity_type: str, action: str) -> bool:
    """依附件所屬實體檢查模組權限，避免只靠 entity_id 猜測讀取附件。"""
    if not bool(getattr(current_user, 'is_active', False)):
        return False
    role_code = getattr(current_user, 'role', None)
    if entity_type in MSA_ATTACHMENT_ENTITY_TYPES:
        if role_code == 'admin':
            return True
        role = Role.query.filter_by(code=role_code).first() if role_code else None
        if not role:
            return False
        if entity_type == 'equipment_calibration':
            calibration_permissions = (
                ('calibration.view',)
                if action == 'view'
                else ('calibration.execute', 'calibration.manage')
            )
            if any(
                role.has_permission(permission)
                for permission in calibration_permissions
            ):
                return True
        required = 'msa.view' if action == 'view' else 'msa.manage'
        return role.has_permission(required)
    if role_code in ('admin', 'manager'):
        return True
    prefix = _ENTITY_PERMISSION_PREFIX.get(entity_type)
    if not prefix:
        return False
    role = Role.query.filter_by(code=role_code).first() if role_code else None
    if not role:
        return False
    if action == 'view' and role.has_permission(f'{prefix}.edit'):
        return True
    return role.has_permission(f'{prefix}.{action}')


def _require_entity_permission(current_user, entity_type: str, action: str):
    if entity_type not in _ENTITY_PERMISSION_PREFIX:
        return jsonify({'error': f'無效的實體類型：{entity_type}'}), 400
    if not _has_entity_permission(current_user, entity_type, action):
        if entity_type in MSA_ATTACHMENT_ENTITY_TYPES:
            if entity_type == 'equipment_calibration':
                required = (
                    'calibration.view 或 msa.view'
                    if action == 'view'
                    else (
                        'calibration.execute、calibration.manage '
                        '或 msa.manage'
                    )
                )
            else:
                required = 'msa.view' if action == 'view' else 'msa.manage'
            return _msa_error(
                'MSA_ATTACHMENT_PERMISSION_DENIED',
                '權限不足',
                403,
                details={
                    'entity_type': entity_type,
                    'permission': required,
                },
            )
        return jsonify({'error': '權限不足'}), 403
    return None


def _msa_error(code: str, message: str, status: int, *, details=None):
    return jsonify({
        'error': {
            'code': code,
            'message': message,
            'details': details or {},
        }
    }), status


def _msa_service_error(error: MsaServiceError):
    return _msa_error(
        error.code,
        error.message,
        error.status_code,
        details=error.details,
    )


def _preserve_attachment_authorization_contract(function):
    """將中央權限拒絕翻譯為已公開的 MSA 附件錯誤契約。"""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except AuthorizationError:
            entity_type = request.form.get('entity_type')
            if not entity_type and kwargs.get('att_id') is not None:
                attachment = AttachmentService.get_by_id(kwargs['att_id'])
                entity_type = attachment.get('entity_type') if attachment else None
            if entity_type in MSA_ATTACHMENT_ENTITY_TYPES:
                required = (
                    'calibration.execute、calibration.manage 或 msa.manage'
                    if entity_type == 'equipment_calibration'
                    else 'msa.manage'
                )
                return _msa_error(
                    'MSA_ATTACHMENT_PERMISSION_DENIED',
                    '權限不足',
                    403,
                    details={
                        'entity_type': entity_type,
                        'permission': required,
                    },
                )
            raise

    return wrapped


def _missing_attachment_error(att_id: int):
    """只有呼叫端明確提供 MSA 實體 context 時才使用 MSA 契約。"""
    entity_type = request.args.get('entity_type')
    if entity_type in MSA_ATTACHMENT_ENTITY_TYPES:
        return _msa_error(
            'MSA_ATTACHMENT_NOT_FOUND',
            '附件不存在',
            404,
            details={'attachment_id': att_id},
        )
    return jsonify({'error': '附件不存在'}), 404


@attachment_bp.route('/api/attachments/upload', methods=['POST'])
@auth_required
@_preserve_attachment_authorization_contract
@require_permissions(
    'capa.edit', 'task.edit', 'complaint.edit', 'pyrometry.edit',
    'msa.manage', 'calibration.execute', 'calibration.manage',
    mode='any',
)
def upload_attachment(current_user):
    """
    POST /api/attachments/upload
    Form-data: file, entity_type, entity_id, d_step(選填)
    """
    entity_type = request.form.get('entity_type', '')
    entity_id   = request.form.get('entity_id', '')
    is_msa = entity_type in MSA_ATTACHMENT_ENTITY_TYPES
    if 'file' not in request.files:
        if is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_FILE_REQUIRED',
                '未提供檔案',
                422,
            )
        return jsonify({'error': '未提供檔案'}), 400

    file        = request.files['file']
    d_step_raw  = request.form.get('d_step')
    purpose = request.form.get('purpose') or None

    if not entity_type or not entity_id:
        if is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_TARGET_REQUIRED',
                '缺少 entity_type 或 entity_id',
                422,
            )
        return jsonify({'error': '缺少 entity_type 或 entity_id'}), 400

    permission_error = _require_entity_permission(current_user, entity_type, 'edit')
    if permission_error:
        return permission_error

    try:
        entity_id_int = int(entity_id)
        d_step = _parse_d_step(d_step_raw)
        result = AttachmentService.upload(
            file=file,
            entity_type=entity_type,
            entity_id=entity_id_int,
            d_step=d_step,
            uploader_id=current_user.id,
            purpose=purpose,
        )
        return jsonify(result), 201
    except MsaServiceError as e:
        return _msa_service_error(e)
    except ValueError as e:
        if is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_VALIDATION_ERROR',
                str(e),
                422,
                details={'entity_type': entity_type},
            )
        return jsonify({'error': str(e)}), 400
    except Exception:
        if is_msa:
            return _msa_service_error(
                MsaInternalError(
                    'MSA_ATTACHMENT_INTERNAL_ERROR',
                    '附件上傳發生未預期錯誤',
                )
            )
        raise


@attachment_bp.route('/api/attachments', methods=['GET'])
@auth_required
def list_attachments(current_user):
    """
    GET /api/attachments?entity_type=capa&entity_id=123[&d_step=4]
    """
    entity_type = request.args.get('entity_type', '')
    entity_id   = request.args.get('entity_id', '')
    is_msa = entity_type in MSA_ATTACHMENT_ENTITY_TYPES
    d_step_raw  = request.args.get('d_step')

    if not entity_type or not entity_id:
        if is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_TARGET_REQUIRED',
                '缺少 entity_type 或 entity_id',
                422,
            )
        return jsonify({'error': '缺少 entity_type 或 entity_id'}), 400

    permission_error = _require_entity_permission(current_user, entity_type, 'view')
    if permission_error:
        return permission_error

    try:
        d_step = _parse_d_step(d_step_raw)
        items = AttachmentService.list_by_entity(
            entity_type=entity_type,
            entity_id=int(entity_id),
            d_step=d_step,
        )
        return jsonify(items), 200
    except MsaServiceError as e:
        return _msa_service_error(e)
    except ValueError as e:
        if is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_VALIDATION_ERROR',
                str(e),
                422,
                details={'entity_type': entity_type},
            )
        raise
    except Exception:
        if is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_INTERNAL_ERROR',
                '附件清單查詢發生未預期錯誤',
                500,
            )
        raise


@attachment_bp.route('/api/attachments/<int:att_id>/download', methods=['GET'])
@auth_required
def download_attachment(current_user, att_id: int):
    """GET /api/attachments/<id>/download"""
    att = AttachmentService.get_by_id(att_id)
    if not att:
        return _missing_attachment_error(att_id)

    permission_error = _require_entity_permission(current_user, att['entity_type'], 'view')
    if permission_error:
        return permission_error

    # 本地儲存：直接回傳檔案
    abs_path = AttachmentService.get_file_path(att_id)
    if abs_path:
        return send_file(
            abs_path,
            mimetype=att['mime_type'] or 'application/octet-stream',
            as_attachment=True,
            download_name=att['file_name'],
        )

    # 雲端儲存：redirect 至 presigned URL
    url = AttachmentService.get_download_url(att_id)
    if url:
        return redirect(url)

    if att['entity_type'] in MSA_ATTACHMENT_ENTITY_TYPES:
        return _msa_error(
            'MSA_ATTACHMENT_FILE_NOT_FOUND',
            '檔案不存在於伺服器',
            404,
            details={'attachment_id': att_id},
        )
    return jsonify({'error': '檔案不存在於伺服器'}), 404


@attachment_bp.route('/api/attachments/<int:att_id>', methods=['DELETE'])
@auth_required
@_preserve_attachment_authorization_contract
@require_permissions(
    'capa.edit', 'task.edit', 'complaint.edit', 'pyrometry.edit',
    'msa.manage', 'calibration.execute', 'calibration.manage',
    mode='any',
)
def delete_attachment(current_user, att_id: int):
    """DELETE /api/attachments/<id>"""
    try:
        att = AttachmentService.get_by_id(att_id)
        if not att:
            return _missing_attachment_error(att_id)
        is_msa = att['entity_type'] in MSA_ATTACHMENT_ENTITY_TYPES
        permission_error = _require_entity_permission(current_user, att['entity_type'], 'edit')
        if permission_error:
            return permission_error
        AttachmentService.delete(
            att_id=att_id,
            requester_id=current_user.id,
            requester_role=getattr(current_user, 'role', 'user'),
        )
        return jsonify({'message': '刪除成功'}), 200
    except MsaServiceError as e:
        return _msa_service_error(e)
    except ValueError as e:
        if 'is_msa' in locals() and is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_NOT_FOUND',
                str(e),
                404,
                details={'attachment_id': att_id},
            )
        return jsonify({'error': str(e)}), 404
    except PermissionError as e:
        if 'is_msa' in locals() and is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_OWNERSHIP_DENIED',
                str(e),
                403,
                details={'attachment_id': att_id},
            )
        return jsonify({'error': str(e)}), 403
    except Exception:
        if 'is_msa' in locals() and is_msa:
            return _msa_error(
                'MSA_ATTACHMENT_INTERNAL_ERROR',
                '附件刪除發生未預期錯誤',
                500,
                details={'attachment_id': att_id},
            )
        raise
