"""機械性質檢驗 REST API 路由。"""
from flask import Blueprint, jsonify, request
from ..services.mechanical_service import MechanicalService
from ..utils import auth_required, require_perm, handle_db_error

mechanical_bp = Blueprint('mechanical', __name__)


def _current_user_id():
    user = getattr(request, 'user', None) or {}
    return user.get('user_id')


@mechanical_bp.route('/api/mechanical/tests', methods=['GET'])
@auth_required
def list_tests():
    """機械性質檢驗清單查詢"""
    try:
        return jsonify(MechanicalService.list(request.args))
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['GET'])
@auth_required
def get_test(test_id):
    """取得單筆機械性質檢驗明細"""
    try:
        return jsonify(MechanicalService.get_detail(test_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@mechanical_bp.route('/api/mechanical/tests', methods=['POST'])
@auth_required
@require_perm('mechanical.create')
def create_test():
    """新增機械性質檢驗"""
    try:
        new_id = MechanicalService.create(request.json or {}, _current_user_id())
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['PUT'])
@auth_required
@require_perm('mechanical.edit')
def update_test(test_id):
    """更新機械性質檢驗"""
    try:
        MechanicalService.update(test_id, request.json or {}, _current_user_id())
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/tests/<int:test_id>', methods=['DELETE'])
@auth_required
@require_perm('mechanical.delete')
def delete_test(test_id):
    """刪除機械性質檢驗"""
    try:
        MechanicalService.delete(test_id)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@mechanical_bp.route('/api/mechanical/spec', methods=['GET'])
@auth_required
def get_spec():
    """依材質+尺寸查規格下限（供表單即時顯示）"""
    from ..services.mechanical_spec import lookup_lower_limits
    material = request.args.get('material', '')
    size = request.args.get('product_size', '')
    limits = lookup_lower_limits(material, size)
    return jsonify({"success": True, "limits": {k: float(v) for k, v in limits.items()}})
