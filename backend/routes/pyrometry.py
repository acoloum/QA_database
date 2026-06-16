from flask import Blueprint, jsonify, request
from ..services.pyrometry_service import PyrometryService
from ..utils import auth_required, handle_db_error
from ..services.pyrometry_parser import parse_temperature_file

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


# ---------- 測試紀錄 ----------
@pyrometry_bp.route('/api/pyrometry/tests', methods=['GET'])
@auth_required
def search_tests():
    return jsonify(PyrometryService.search_tests(request.args))


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['GET'])
@auth_required
def get_test(tid):
    try:
        return jsonify(PyrometryService.get_test(tid))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@pyrometry_bp.route('/api/pyrometry/tests', methods=['POST'])
@auth_required
def create_test():
    try:
        new_id = PyrometryService.create_test(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['PUT'])
@auth_required
def update_test(tid):
    try:
        PyrometryService.update_test(tid, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['DELETE'])
@auth_required
def delete_test(tid):
    try:
        PyrometryService.delete_test(tid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


# ---------- 資料解析 ----------
@pyrometry_bp.route('/api/pyrometry/parse-data', methods=['POST'])
@auth_required
def parse_data():
    """上傳時間序列資料檔，回傳通道摘要與繪圖資料（不落地，僅解析）"""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "缺少檔案"}), 400
    try:
        result = parse_temperature_file(file.stream, filename=file.filename)
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


# ---------- 看板與趨勢 ----------
@pyrometry_bp.route('/api/pyrometry/dashboard', methods=['GET'])
@auth_required
def dashboard():
    return jsonify({"success": True, "data": PyrometryService.dashboard()})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>/tus-trend', methods=['GET'])
@auth_required
def tus_trend(fid):
    return jsonify({"success": True, "data": PyrometryService.tus_trend(fid)})
