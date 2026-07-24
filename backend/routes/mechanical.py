"""機械性質檢驗 REST API 路由。"""
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType
from ..services.mechanical_service import (
    MechanicalNotFoundError,
    MechanicalService,
    MechanicalValidationError,
    parse_vendor_id,
)
from ..extensions import db
from ..models import Vendor
from ..utils import auth_required, require_perm, handle_db_error, validate_upload_file

mechanical_bp = Blueprint('mechanical', __name__)


def _current_user_id():
    user = getattr(request, 'user', None) or {}
    return user.get('user_id')


def _mechanical_error_response(error):
    db.session.rollback()
    if isinstance(error, (MechanicalValidationError, BadRequest, UnsupportedMediaType)):
        return jsonify({"error": str(error)}), 400
    if isinstance(error, MechanicalNotFoundError):
        return jsonify({"error": str(error)}), 404
    return jsonify({"error": handle_db_error(error)}), 500


def _json_object():
    """只接受有效 JSON 物件；避免空 body／錯誤 MIME 轉成伺服器錯誤。"""
    if not request.is_json:
        raise MechanicalValidationError("Content-Type 必須為 application/json")
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        raise MechanicalValidationError("請求內容必須為物件")
    return data


@mechanical_bp.route('/api/mechanical/tests', methods=['GET'])
@auth_required
def list_tests():
    """機械性質檢驗清單查詢"""
    try:
        return jsonify(MechanicalService.list(request.args))
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['GET'])
@auth_required
def get_test(test_id):
    """取得單筆機械性質檢驗明細"""
    try:
        return jsonify(MechanicalService.get_detail(test_id))
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/tests', methods=['POST'])
@auth_required
@require_perm('mechanical.create')
def create_test():
    """新增機械性質檢驗"""
    try:
        new_id = MechanicalService.create(_json_object(), _current_user_id())
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['PUT'])
@auth_required
@require_perm('mechanical.edit')
def update_test(test_id):
    """更新機械性質檢驗"""
    try:
        MechanicalService.update(test_id, _json_object(), _current_user_id())
        return jsonify({"success": True})
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['DELETE'])
@auth_required
@require_perm('mechanical.delete')
def delete_test(test_id):
    """刪除機械性質檢驗"""
    try:
        MechanicalService.delete(test_id)
        return jsonify({"success": True})
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/tests/import', methods=['POST'])
@auth_required
@require_perm('mechanical.create')
def import_tests():
    """匯入機械性質 Excel（必榮供應商轉置表格式）"""
    try:
        if 'file' not in request.files:
            raise MechanicalValidationError("沒有上傳檔案")
        file = request.files['file']
        if file.filename == '':
            raise MechanicalValidationError("沒有選擇檔案")
        upload_error = validate_upload_file(file)
        if upload_error:
            raise MechanicalValidationError(upload_error)
        material = (request.form.get('material') or '').strip()
        if not material:
            raise MechanicalValidationError("材質為必填")
        vendor_id = parse_vendor_id(request.form.get('vendor_id'))
        if vendor_id is not None and db.session.get(Vendor, vendor_id) is None:
            raise MechanicalValidationError("指定的廠商不存在")
        result = MechanicalService.import_data(file, material, vendor_id, _current_user_id())
        message = f"匯入完成，新增 {result['created']} 筆"
        if result['skipped']:
            message += f"，略過 {result['skipped']} 筆重複資料"
        if result['errors']:
            message += f"，{len(result['errors'])} 筆失敗"
        return jsonify({
            "success": True,
            "message": message,
            **result,
        })
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/stats', methods=['GET'])
@auth_required
def get_stats():
    """機械性質即時 SPC 預覽（供頁面內嵌圖表使用）"""
    try:
        return jsonify(MechanicalService.get_stats(request.args))
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/spec', methods=['GET'])
@auth_required
def get_spec():
    """依材質+尺寸查規格下限（供表單即時顯示）"""
    from ..services.mechanical_spec import lookup_lower_limits
    try:
        material = request.args.get('material', '')
        size = request.args.get('product_size', '')
        vendor_id = parse_vendor_id(request.args.get('vendor_id'))
        if vendor_id is not None and db.session.get(Vendor, vendor_id) is None:
            raise MechanicalValidationError("指定的廠商不存在")
        limits = lookup_lower_limits(material, size, vendor_id=vendor_id)
        return jsonify({"success": True, "limits": {k: float(v) for k, v in limits.items()}})
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/options', methods=['GET'])
@auth_required
def get_options():
    """取得指定廠商公差中受控且去重的材質與尺寸建議。"""
    try:
        vendor_id = parse_vendor_id(request.args.get('vendor_id'))
        if vendor_id is None:
            return jsonify({"success": True, "materials": [], "product_sizes": []})
        if db.session.get(Vendor, vendor_id) is None:
            raise MechanicalValidationError("指定的廠商不存在")
        return jsonify({"success": True, **MechanicalService.options(vendor_id)})
    except Exception as e:
        return _mechanical_error_response(e)
