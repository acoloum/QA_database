"""附件路由 — 上傳、查詢、下載、刪除"""
from flask import Blueprint, jsonify, request, send_file, redirect
from ..services.attachment_service import AttachmentService
from ..utils import auth_required

attachment_bp = Blueprint('attachment', __name__)


@attachment_bp.route('/attachments/upload', methods=['POST'])
@auth_required
def upload_attachment(current_user):
    """
    POST /api/attachments/upload
    Form-data: file, entity_type, entity_id, d_step(選填)
    """
    if 'file' not in request.files:
        return jsonify({'error': '未提供檔案'}), 400

    file        = request.files['file']
    entity_type = request.form.get('entity_type', '')
    entity_id   = request.form.get('entity_id', '')
    d_step_raw  = request.form.get('d_step')

    if not entity_type or not entity_id:
        return jsonify({'error': '缺少 entity_type 或 entity_id'}), 400

    try:
        entity_id_int = int(entity_id)
        d_step = int(d_step_raw) if d_step_raw is not None and d_step_raw != '' else None
        result = AttachmentService.upload(
            file=file,
            entity_type=entity_type,
            entity_id=entity_id_int,
            d_step=d_step,
            uploader_id=current_user.id,
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'上傳失敗：{e}'}), 500


@attachment_bp.route('/attachments', methods=['GET'])
@auth_required
def list_attachments(current_user):
    """
    GET /api/attachments?entity_type=capa&entity_id=123[&d_step=4]
    """
    entity_type = request.args.get('entity_type', '')
    entity_id   = request.args.get('entity_id', '')
    d_step_raw  = request.args.get('d_step')

    if not entity_type or not entity_id:
        return jsonify({'error': '缺少 entity_type 或 entity_id'}), 400

    try:
        d_step = int(d_step_raw) if d_step_raw is not None else None
        items = AttachmentService.list_by_entity(
            entity_type=entity_type,
            entity_id=int(entity_id),
            d_step=d_step,
        )
        return jsonify(items), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@attachment_bp.route('/attachments/<int:att_id>/download', methods=['GET'])
@auth_required
def download_attachment(current_user, att_id: int):
    """GET /api/attachments/<id>/download"""
    att = AttachmentService.get_by_id(att_id)
    if not att:
        return jsonify({'error': '附件不存在'}), 404

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

    return jsonify({'error': '檔案不存在於伺服器'}), 404


@attachment_bp.route('/attachments/<int:att_id>', methods=['DELETE'])
@auth_required
def delete_attachment(current_user, att_id: int):
    """DELETE /api/attachments/<id>"""
    try:
        AttachmentService.delete(
            att_id=att_id,
            requester_id=current_user.id,
            requester_role=getattr(current_user, 'role', 'user'),
        )
        return jsonify({'message': '刪除成功'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500
