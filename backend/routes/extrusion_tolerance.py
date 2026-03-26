
from flask import Blueprint, jsonify, request
from ..services.extrusion_tolerance_service import ExtrusionToleranceService
from ..utils import auth_required, handle_db_error

extrusion_tolerance_bp = Blueprint('extrusion_tolerance', __name__)


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/search', methods=['GET'])
@auth_required
def search():
    """查詢擠壓公差列表"""
    return jsonify(ExtrusionToleranceService.search(request.args))


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/<int:id>', methods=['GET'])
@auth_required
def get_detail(id):
    """取得單筆擠壓公差詳細"""
    try:
        return jsonify(ExtrusionToleranceService.get_detail(id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/add', methods=['POST'])
@auth_required
def add():
    """新增擠壓公差"""
    try:
        new_id = ExtrusionToleranceService.add(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/update/<int:id>', methods=['POST'])
@auth_required
def update(id):
    """更新擠壓公差"""
    try:
        ExtrusionToleranceService.update(id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/delete/<int:id>', methods=['POST'])
@auth_required
def delete(id):
    """刪除擠壓公差"""
    try:
        ExtrusionToleranceService.delete(id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/options', methods=['GET'])
@auth_required
def get_options():
    """取得材質、規格選項"""
    try:
        return jsonify(ExtrusionToleranceService.get_options())
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/check', methods=['GET'])
@auth_required
def check():
    """依材質+規格查詢對應公差（供巡檢 NG 比對用）"""
    try:
        return jsonify(ExtrusionToleranceService.check(request.args))
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
