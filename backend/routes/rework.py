
from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from ..services.rework_service import ReworkService
from ..errors import APIError
from ..utils import auth_required
from ..authorization import require_permission

rework_bp = Blueprint('rework', __name__)


def rework_error_response(error, context):
    """集中重工 route 錯誤回應與記錄格式。"""
    if isinstance(error, APIError):
        return jsonify(error.to_dict()), error.status_code
    if isinstance(error, ValueError):
        return jsonify({"error": str(error)}), 400
    current_app.logger.exception("%s error: %s", context, str(error))
    return jsonify({"error": "伺服器內部錯誤"}), 500


def require_rework_id():
    """子表清單一律限縮在單張重工單，缺少 rework_id 時直接回 400。

    未指定時舊行為是整表掃描並回傳所有重工單的子紀錄，既無意義也不安全。
    """
    rework_id = request.args.get('rework_id')
    if not rework_id:
        raise ValueError("缺少必要參數 rework_id")
    return rework_id


def rework_route_errors(context, *, propagate_unexpected=False):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                if propagate_unexpected and not isinstance(error, (APIError, ValueError)):
                    raise
                return rework_error_response(error, context)
        return wrapped
    return decorator


@rework_bp.route('/api/rework/statistics', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Rework statistics')
def get_rework_statistics():
    """獲取重工統計數據"""
    data = ReworkService.get_statistics(request.args)
    return jsonify(data)

@rework_bp.route('/api/rework/applications', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Rework applications')
def get_rework_applications():
    """獲取重工申請列表"""
    data = ReworkService.get_application_list(request.args)
    return jsonify(data)

@rework_bp.route('/api/rework/apply', methods=['POST'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Apply rework', propagate_unexpected=True)
def apply_rework(current_user):
    """提交重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    result = ReworkService.create_application(request.json, actor_id=current_user.id)
    return jsonify({"success": True, **result})

@rework_bp.route('/api/rework/application/<int:rework_id>', methods=['PUT'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Update rework application')
def update_rework_application(rework_id):
    """更新重工申請單"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.update_application(rework_id, request.json)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/approve', methods=['POST'])
@auth_required
@require_permission('rework.approve')
@rework_route_errors('Approve rework', propagate_unexpected=True)
def approve_rework(current_user):
    """審核重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.approve_application(request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/executions', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Rework executions')
def get_rework_executions():
    """獲取指定重工單的執行記錄"""
    rework_id = require_rework_id()
    data = ReworkService.get_execution_list(rework_id)
    return jsonify(data)

@rework_bp.route('/api/rework/execute', methods=['POST'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Execute rework', propagate_unexpected=True)
def execute_rework(current_user):
    """記錄重工執行"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.create_execution(request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Get execution')
def get_execution(execution_id):
    """獲取單筆執行記錄"""
    item = ReworkService.get_execution(execution_id)
    if not item:
        return jsonify({"error": "找不到執行記錄"}), 404
    return jsonify(item)

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['PUT'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Update execution', propagate_unexpected=True)
def update_execution(current_user, execution_id):
    """更新執行記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.update_execution(execution_id, request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['DELETE'])
@auth_required
@require_permission('rework.delete')
@rework_route_errors('Delete execution', propagate_unexpected=True)
def delete_execution(current_user, execution_id):
    """刪除執行記錄"""
    ReworkService.delete_execution(execution_id, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/inspections', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Rework inspections')
def get_rework_inspections():
    """獲取指定重工單的品檢記錄"""
    rework_id = require_rework_id()
    data = ReworkService.get_inspection_list(rework_id)
    return jsonify(data)

@rework_bp.route('/api/rework/costs', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Rework costs')
def get_rework_costs():
    """獲取指定重工單的成本記錄"""
    rework_id = require_rework_id()
    data = ReworkService.get_cost_list(rework_id)
    return jsonify(data)

@rework_bp.route('/api/rework/cost', methods=['POST'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Add rework cost', propagate_unexpected=True)
def add_rework_cost(current_user):
    """新增重工成本記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.create_cost(request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Get rework cost')
def get_rework_cost(cost_id):
    """獲取單筆成本記錄"""
    data = ReworkService.get_cost(cost_id)
    if not data:
        return jsonify({"error": "找不到資料"}), 404
    return jsonify(data)

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['PUT'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Update rework cost', propagate_unexpected=True)
def update_rework_cost(current_user, cost_id):
    """更新成本記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.update_cost(cost_id, request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['DELETE'])
@auth_required
@require_permission('rework.delete')
@rework_route_errors('Delete rework cost', propagate_unexpected=True)
def delete_rework_cost(current_user, cost_id):
    """刪除成本記錄"""
    ReworkService.delete_cost(cost_id, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/inspect', methods=['POST'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Inspect rework', propagate_unexpected=True)
def inspect_rework(current_user):
    """記錄重工品檢"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.create_inspection(request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['GET'])
@auth_required
@require_permission('rework.view')
@rework_route_errors('Get inspection')
def get_inspection(inspection_id):
    """獲取單筆品檢記錄"""
    item = ReworkService.get_inspection(inspection_id)
    if not item:
        return jsonify({"error": "找不到品檢記錄"}), 404
    return jsonify(item)

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['PUT'])
@auth_required
@require_permission('rework.create')
@rework_route_errors('Update inspection', propagate_unexpected=True)
def update_inspection(current_user, inspection_id):
    """更新品檢記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.update_inspection(inspection_id, request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['DELETE'])
@auth_required
@require_permission('rework.delete')
@rework_route_errors('Delete inspection', propagate_unexpected=True)
def delete_inspection(current_user, inspection_id):
    """刪除品檢記錄"""
    ReworkService.delete_inspection(inspection_id, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/close', methods=['POST'])
@auth_required
@require_permission('rework.approve')
@rework_route_errors('Close rework', propagate_unexpected=True)
def close_rework(current_user):
    """結案重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    ReworkService.close_rework(request.json, actor_id=current_user.id)
    return jsonify({"success": True})

@rework_bp.route('/api/rework/delete', methods=['POST'])
@auth_required
@require_permission('rework.delete')
@rework_route_errors('Delete rework', propagate_unexpected=True)
def delete_rework(current_user):
    """刪除重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    rework_id = request.json.get('rework_id')
    if not rework_id:
        return jsonify({"error": "缺少重工ID"}), 400
    ReworkService.delete_rework(rework_id, actor_id=current_user.id)
    return jsonify({"success": True})
