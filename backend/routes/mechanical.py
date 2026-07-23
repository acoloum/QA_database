"""機械性質檢驗 REST API 路由。"""
from flask import Blueprint, jsonify, request
from ..services.mechanical_service import (
    MechanicalNotFoundError,
    MechanicalService,
    MechanicalValidationError,
    parse_vendor_id,
)
from ..extensions import db
from ..utils import auth_required, require_perm, handle_db_error

mechanical_bp = Blueprint('mechanical', __name__)


def _current_user_id():
    user = getattr(request, 'user', None) or {}
    return user.get('user_id')


def _mechanical_error_response(error):
    db.session.rollback()
    if isinstance(error, MechanicalValidationError):
        return jsonify({"error": str(error)}), 400
    if isinstance(error, MechanicalNotFoundError):
        return jsonify({"error": str(error)}), 404
    return jsonify({"error": handle_db_error(error)}), 500


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
        new_id = MechanicalService.create(request.json or {}, _current_user_id())
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return _mechanical_error_response(e)


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['PUT'])
@auth_required
@require_perm('mechanical.edit')
def update_test(test_id):
    """更新機械性質檢驗"""
    try:
        MechanicalService.update(test_id, request.json or {}, _current_user_id())
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


@mechanical_bp.route('/api/mechanical/spec', methods=['GET'])
@auth_required
def get_spec():
    """依材質+尺寸查規格下限（供表單即時顯示）"""
    from ..services.mechanical_spec import lookup_lower_limits
    try:
        material = request.args.get('material', '')
        size = request.args.get('product_size', '')
        vendor_id = parse_vendor_id(request.args.get('vendor_id'))
        limits = lookup_lower_limits(material, size, vendor_id=vendor_id)
        return jsonify({"success": True, "limits": {k: float(v) for k, v in limits.items()}})
    except Exception as e:
        return _mechanical_error_response(e)
