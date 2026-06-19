import io as _io
from flask import Blueprint, jsonify, request, send_file
from ..services.pyrometry_service import PyrometryService, PyrometryValidationError
from ..utils import auth_required, require_perm, handle_db_error, validate_upload_file
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
@require_perm('pyrometry.edit')
def add_furnace():
    try:
        new_id = PyrometryService.add_furnace(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['PUT'])
@auth_required
@require_perm('pyrometry.edit')
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
@require_perm('pyrometry.delete')
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
@require_perm('pyrometry.edit')
def create_test():
    try:
        new_id = PyrometryService.create_test(request.get_json(silent=True))
        return jsonify({"success": True, "id": new_id})
    except PyrometryValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['PUT'])
@auth_required
@require_perm('pyrometry.edit')
def update_test(tid):
    try:
        PyrometryService.update_test(tid, request.get_json(silent=True))
        return jsonify({"success": True})
    except PyrometryValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['DELETE'])
@auth_required
@require_perm('pyrometry.delete')
def delete_test(tid):
    try:
        PyrometryService.delete_test(tid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


# ---------- 溫度記錄器校正 ----------
@pyrometry_bp.route('/api/pyrometry/recorders', methods=['GET'])
@auth_required
def list_recorders():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_recorders(active_only)})


@pyrometry_bp.route('/api/pyrometry/recorders/<int:rid>', methods=['GET'])
@auth_required
def get_recorder(rid):
    try:
        return jsonify({"success": True, "data": PyrometryService.get_recorder(rid)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@pyrometry_bp.route('/api/pyrometry/recorders', methods=['POST'])
@auth_required
@require_perm('pyrometry.edit')
def add_recorder():
    try:
        new_id = PyrometryService.add_recorder(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/recorders/<int:rid>', methods=['PUT'])
@auth_required
@require_perm('pyrometry.edit')
def update_recorder(rid):
    try:
        PyrometryService.update_recorder(rid, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/recorders/<int:rid>', methods=['DELETE'])
@auth_required
@require_perm('pyrometry.delete')
def delete_recorder(rid):
    try:
        PyrometryService.delete_recorder(rid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


# ---------- 熱電偶校正 ----------
@pyrometry_bp.route('/api/pyrometry/thermocouples', methods=['GET'])
@auth_required
def list_thermocouples():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_thermocouples(active_only)})


@pyrometry_bp.route('/api/pyrometry/thermocouples/<int:tcid>', methods=['GET'])
@auth_required
def get_thermocouple(tcid):
    try:
        return jsonify({"success": True, "data": PyrometryService.get_thermocouple(tcid)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@pyrometry_bp.route('/api/pyrometry/thermocouples', methods=['POST'])
@auth_required
@require_perm('pyrometry.edit')
def add_thermocouple():
    try:
        new_id = PyrometryService.add_thermocouple(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/thermocouples/<int:tcid>', methods=['PUT'])
@auth_required
@require_perm('pyrometry.edit')
def update_thermocouple(tcid):
    try:
        PyrometryService.update_thermocouple(tcid, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/thermocouples/<int:tcid>', methods=['DELETE'])
@auth_required
@require_perm('pyrometry.delete')
def delete_thermocouple(tcid):
    try:
        PyrometryService.delete_thermocouple(tcid)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@pyrometry_bp.route('/api/pyrometry/corrections', methods=['GET'])
@auth_required
def corrections():
    """依設定溫度回傳各量測點的修正值（熱電偶+記錄器補正）"""
    try:
        setpoint = float(request.args.get('setpoint') or 0)
        test_type = request.args.get('type', 'TUS')
        count = int(request.args.get('count') or 0)
        rid = request.args.get('recorder_id')
        rid = int(rid) if rid else None
        ch_param = request.args.get('channels')
        channels = [int(c) for c in ch_param.split(',') if c.strip()] if ch_param else None
        data = PyrometryService.compute_corrections(setpoint, test_type, count, rid, channels)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


# ---------- 資料解析 ----------
@pyrometry_bp.route('/api/pyrometry/parse-data', methods=['POST'])
@auth_required
@require_perm('pyrometry.edit')
def parse_data():
    """上傳時間序列資料檔，回傳通道摘要與繪圖資料（不落地，僅解析）"""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "缺少檔案"}), 400
    upload_error = validate_upload_file(file, allowed_extensions={'.csv', '.xlsx', '.xls'})
    if upload_error:
        return jsonify({"error": upload_error}), 400
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


# ---------- 報告匯出 ----------
@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>/export', methods=['GET'])
@auth_required
def export_test(tid):
    try:
        content = PyrometryService.export_test_xlsx(tid)
        return send_file(
            _io.BytesIO(content),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'pyrometry_{tid}.xlsx')
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
