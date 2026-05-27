
from flask import Blueprint, jsonify, request, current_app
from ..services.rework_service import ReworkService
from ..utils import auth_required, require_permission, log_audit
from ..extensions import db

rework_bp = Blueprint('rework', __name__)

@rework_bp.route('/api/rework/statistics', methods=['GET'])
@auth_required
def get_rework_statistics():
    """獲取重工統計數據"""
    try:
        data = ReworkService.get_statistics(request.args)
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("Rework statistics error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/applications', methods=['GET'])
@auth_required
def get_rework_applications():
    """獲取重工申請列表"""
    try:
        data = ReworkService.get_application_list(request.args)
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("Rework applications error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/apply', methods=['POST'])
@auth_required
@require_permission('rework.create')
def apply_rework(current_user):
    """提交重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        result = ReworkService.create_application(request.json)
        log_audit(current_user.id, 'create', '重工', result.get('id') if isinstance(result, dict) else None)
        db.session.commit()
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Apply rework error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/application/<int:rework_id>', methods=['PUT'])
@auth_required
def update_rework_application(rework_id):
    """更新重工申請單"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.update_application(rework_id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Update rework application error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/approve', methods=['POST'])
@auth_required
@require_permission('rework.approve')
def approve_rework(current_user):
    """審核重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.approve_application(request.json)
        rework_id = request.json.get('rework_id')
        log_audit(current_user.id, 'approve', '重工', rework_id)
        db.session.commit()
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Approve rework error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/executions', methods=['GET'])
@auth_required
def get_rework_executions():
    """獲取重工執行記錄"""
    try:
        data = ReworkService.get_execution_list(request.args.get('rework_id'))
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("Rework executions error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/execute', methods=['POST'])
@auth_required
def execute_rework():
    """記錄重工執行"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.create_execution(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Execute rework error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['GET'])
@auth_required
def get_execution(execution_id):
    """獲取單筆執行記錄"""
    try:
        item = ReworkService.get_execution(execution_id)
        if not item:
            return jsonify({"error": "找不到執行記錄"}), 404
        return jsonify(item)
    except Exception as e:
        current_app.logger.exception("Get execution error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['PUT'])
@auth_required
def update_execution(execution_id):
    """更新執行記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.update_execution(execution_id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Update execution error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['DELETE'])
@auth_required
def delete_execution(execution_id):
    """刪除執行記錄"""
    try:
        ReworkService.delete_execution(execution_id)
        return jsonify({"success": True})
    except Exception as e:
        current_app.logger.exception("Delete execution error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/inspections', methods=['GET'])
@auth_required
def get_rework_inspections():
    """獲取重工品檢記錄"""
    try:
        rework_id = request.args.get('rework_id')
        data = ReworkService.get_inspection_list(rework_id)
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("Rework inspections error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/costs', methods=['GET'])
@auth_required
def get_rework_costs():
    """獲取重工成本記錄"""
    try:
        rework_id = request.args.get('rework_id')
        data = ReworkService.get_cost_list(rework_id)
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("Rework costs error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/cost', methods=['POST'])
@auth_required
def add_rework_cost():
    """新增重工成本記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.create_cost(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Add rework cost error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['GET'])
@auth_required
def get_rework_cost(cost_id):
    """獲取單筆成本記錄"""
    try:
        data = ReworkService.get_cost(cost_id)
        if not data:
            return jsonify({"error": "找不到資料"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("Get rework cost error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['PUT'])
@auth_required
def update_rework_cost(cost_id):
    """更新成本記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.update_cost(cost_id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Update rework cost error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['DELETE'])
@auth_required
def delete_rework_cost(cost_id):
    """刪除成本記錄"""
    try:
        ReworkService.delete_cost(cost_id)
        return jsonify({"success": True})
    except Exception as e:
        current_app.logger.exception("Delete rework cost error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/inspect', methods=['POST'])
@auth_required
def inspect_rework():
    """記錄重工品檢"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.create_inspection(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Inspect rework error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['GET'])
@auth_required
def get_inspection(inspection_id):
    """獲取單筆品檢記錄"""
    try:
        item = ReworkService.get_inspection(inspection_id)
        if not item:
            return jsonify({"error": "找不到品檢記錄"}), 404
        return jsonify(item)
    except Exception as e:
        current_app.logger.exception("Get inspection error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['PUT'])
@auth_required
def update_inspection(inspection_id):
    """更新品檢記錄"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.update_inspection(inspection_id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Update inspection error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['DELETE'])
@auth_required
def delete_inspection(inspection_id):
    """刪除品檢記錄"""
    try:
        ReworkService.delete_inspection(inspection_id)
        return jsonify({"success": True})
    except Exception as e:
        current_app.logger.exception("Delete inspection error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/close', methods=['POST'])
@auth_required
def close_rework():
    """結案重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        ReworkService.close_rework(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Close rework error: %s", str(e))
        return jsonify({"error": str(e)}), 500

@rework_bp.route('/api/rework/delete', methods=['POST'])
@auth_required
@require_permission('rework.delete')
def delete_rework(current_user):
    """刪除重工申請"""
    if not request.json:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    try:
        rework_id = request.json.get('rework_id')
        if not rework_id:
            return jsonify({"error": "缺少重工ID"}), 400
        ReworkService.delete_rework(rework_id)
        log_audit(current_user.id, 'delete', '重工', rework_id)
        db.session.commit()
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Delete rework error: %s", str(e))
        return jsonify({"error": str(e)}), 500
