from flask import Blueprint, jsonify, request
from ..services.pyrometry_service import PyrometryService
from ..utils import auth_required, handle_db_error

pyrometry_bp = Blueprint('pyrometry', __name__)


# ---------- 設備主檔 ----------
@pyrometry_bp.route('/api/pyrometry/furnaces', methods=['GET'])
@auth_required
def list_furnaces():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_furnaces(active_only)})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['GET'])
@auth_required
def get_furnace(fid):
    try:
        return jsonify({"success": True, "data": PyrometryService.get_furnace(fid)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@pyrometry_bp.route('/api/pyrometry/furnaces', methods=['POST'])
@auth_required
def add_furnace():
    try:
        new_id = PyrometryService.add_furnace(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['PUT'])
@auth_required
def update_furnace(fid):
    try:
        PyrometryService.update_furnace(fid, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['DELETE'])
@auth_required
def delete_furnace(fid):
    try:
        PyrometryService.delete_furnace(fid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
