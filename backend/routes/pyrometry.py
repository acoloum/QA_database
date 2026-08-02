import io as _io
from functools import wraps
from flask import Blueprint, jsonify, request, send_file
from ..services.pyrometry_service import PyrometryService, PyrometryValidationError
from ..utils import auth_required, handle_db_error, parse_optional_int, validate_upload_file
from ..authorization import require_permission
from ..services.pyrometry_parser import parse_temperature_file

pyrometry_bp = Blueprint('pyrometry', __name__)


def pyrometry_error_response(error, value_error_status=400):
    """集中爐溫模組 route 的錯誤回應格式，避免各端點各自處理。"""
    if isinstance(error, PyrometryValidationError):
        return jsonify({"error": str(error)}), 400
    if isinstance(error, ValueError):
        return jsonify({"error": str(error)}), value_error_status
    return jsonify({"error": handle_db_error(error)}), 500


def pyrometry_route_errors(value_error_status=400):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                return pyrometry_error_response(error, value_error_status=value_error_status)
        return wrapped
    return decorator


# ---------- 設備主檔 ----------
@pyrometry_bp.route('/api/pyrometry/furnaces', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
def list_furnaces():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_furnaces(active_only)})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
@pyrometry_route_errors(value_error_status=404)
def get_furnace(fid):
    return jsonify({"success": True, "data": PyrometryService.get_furnace(fid)})


@pyrometry_bp.route('/api/pyrometry/furnaces', methods=['POST'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors()
def add_furnace():
    new_id = PyrometryService.add_furnace(request.json)
    return jsonify({"success": True, "id": new_id})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['PUT'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors(value_error_status=404)
def update_furnace(fid):
    PyrometryService.update_furnace(fid, request.json)
    return jsonify({"success": True})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>', methods=['DELETE'])
@auth_required
@require_permission('pyrometry.delete')
@pyrometry_route_errors(value_error_status=404)
def delete_furnace(fid):
    PyrometryService.delete_furnace(fid)
    return jsonify({"success": True})


# ---------- 測試紀錄 ----------
@pyrometry_bp.route('/api/pyrometry/tests', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
def search_tests():
    return jsonify(PyrometryService.search_tests(request.args))


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
@pyrometry_route_errors(value_error_status=404)
def get_test(tid):
    return jsonify(PyrometryService.get_test(tid))


@pyrometry_bp.route('/api/pyrometry/tests', methods=['POST'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors()
def create_test():
    new_id = PyrometryService.create_test(request.get_json(silent=True))
    return jsonify({"success": True, "id": new_id})


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['PUT'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors(value_error_status=404)
def update_test(tid):
    PyrometryService.update_test(tid, request.get_json(silent=True))
    return jsonify({"success": True})


@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>', methods=['DELETE'])
@auth_required
@require_permission('pyrometry.delete')
@pyrometry_route_errors(value_error_status=404)
def delete_test(tid):
    PyrometryService.delete_test(tid)
    return jsonify({"success": True})


# ---------- 溫度記錄器校正 ----------
@pyrometry_bp.route('/api/pyrometry/recorders', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
def list_recorders():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_recorders(active_only)})


@pyrometry_bp.route('/api/pyrometry/recorders/<int:rid>', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
@pyrometry_route_errors(value_error_status=404)
def get_recorder(rid):
    return jsonify({"success": True, "data": PyrometryService.get_recorder(rid)})


@pyrometry_bp.route('/api/pyrometry/recorders', methods=['POST'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors()
def add_recorder():
    new_id = PyrometryService.add_recorder(request.json)
    return jsonify({"success": True, "id": new_id})


@pyrometry_bp.route('/api/pyrometry/recorders/<int:rid>', methods=['PUT'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors(value_error_status=404)
def update_recorder(rid):
    PyrometryService.update_recorder(rid, request.json)
    return jsonify({"success": True})


@pyrometry_bp.route('/api/pyrometry/recorders/<int:rid>', methods=['DELETE'])
@auth_required
@require_permission('pyrometry.delete')
@pyrometry_route_errors(value_error_status=404)
def delete_recorder(rid):
    PyrometryService.delete_recorder(rid)
    return jsonify({"success": True})


# ---------- 熱電偶校正 ----------
@pyrometry_bp.route('/api/pyrometry/thermocouples', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
def list_thermocouples():
    active_only = request.args.get('active_only') == '1'
    return jsonify({"success": True, "data": PyrometryService.list_thermocouples(active_only)})


@pyrometry_bp.route('/api/pyrometry/thermocouples/<int:tcid>', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
@pyrometry_route_errors(value_error_status=404)
def get_thermocouple(tcid):
    return jsonify({"success": True, "data": PyrometryService.get_thermocouple(tcid)})


@pyrometry_bp.route('/api/pyrometry/thermocouples', methods=['POST'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors()
def add_thermocouple():
    new_id = PyrometryService.add_thermocouple(request.json)
    return jsonify({"success": True, "id": new_id})


@pyrometry_bp.route('/api/pyrometry/thermocouples/<int:tcid>', methods=['PUT'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors(value_error_status=404)
def update_thermocouple(tcid):
    PyrometryService.update_thermocouple(tcid, request.json)
    return jsonify({"success": True})


@pyrometry_bp.route('/api/pyrometry/thermocouples/<int:tcid>', methods=['DELETE'])
@auth_required
@require_permission('pyrometry.delete')
@pyrometry_route_errors(value_error_status=404)
def delete_thermocouple(tcid):
    PyrometryService.delete_thermocouple(tcid)
    return jsonify({"success": True})


@pyrometry_bp.route('/api/pyrometry/corrections', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
@pyrometry_route_errors()
def corrections():
    """依設定溫度回傳各量測點的修正值（熱電偶+記錄器補正）"""
    try:
        setpoint = float(request.args.get('setpoint') or 0)
    except (TypeError, ValueError):
        raise ValueError('setpoint 必須為數字')
    test_type = request.args.get('type', 'TUS')
    count = parse_optional_int(request.args.get('count'), 'count') or 0
    if count < 0 or count > 100:
        raise ValueError('count 必須介於 0 到 100')
    rid = parse_optional_int(request.args.get('recorder_id'), 'recorder_id')
    ch_param = request.args.get('channels')
    channels = [parse_optional_int(c.strip(), 'channels') for c in ch_param.split(',') if c.strip()] if ch_param else None
    data = PyrometryService.compute_corrections(setpoint, test_type, count, rid, channels)
    return jsonify({"success": True, "data": data})


# ---------- 資料解析 ----------
@pyrometry_bp.route('/api/pyrometry/parse-data', methods=['POST'])
@auth_required
@require_permission('pyrometry.edit')
@pyrometry_route_errors()
def parse_data():
    """上傳時間序列資料檔，回傳通道摘要與繪圖資料（不落地，僅解析）"""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "缺少檔案"}), 400
    upload_error = validate_upload_file(file, allowed_extensions={'.csv', '.xlsx', '.xls'})
    if upload_error:
        return jsonify({"error": upload_error}), 400
    result = parse_temperature_file(file.stream, filename=file.filename)
    return jsonify({"success": True, "data": result})


# ---------- 看板與趨勢 ----------
@pyrometry_bp.route('/api/pyrometry/dashboard', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
def dashboard():
    return jsonify({"success": True, "data": PyrometryService.dashboard()})


@pyrometry_bp.route('/api/pyrometry/furnaces/<int:fid>/tus-trend', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
def tus_trend(fid):
    return jsonify({"success": True, "data": PyrometryService.tus_trend(fid)})


# ---------- 報告匯出 ----------
@pyrometry_bp.route('/api/pyrometry/tests/<int:tid>/export', methods=['GET'])
@auth_required
@require_permission('pyrometry.view')
@pyrometry_route_errors(value_error_status=404)
def export_test(tid):
    content = PyrometryService.export_test_xlsx(tid)
    return send_file(
        _io.BytesIO(content),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'pyrometry_{tid}.xlsx')
