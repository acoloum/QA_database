from flask import Blueprint, jsonify, request, send_file
from ..services.patrol_service import PatrolService
from ..utils import auth_required, handle_db_error, validate_upload_file, api_error
from ..authorization import require_permission

patrol_bp = Blueprint('patrol', __name__)

@patrol_bp.route('/api/patrol/options')
@auth_required
@require_permission('patrol.view')
def patrol_options():
    options = PatrolService.get_options()
    return jsonify(options)

@patrol_bp.route('/api/patrol/spc')
@auth_required
@require_permission('patrol.view')
def patrol_spc():
    data = PatrolService.get_spc(request.args)
    return jsonify(data)

@patrol_bp.route('/api/patrol/live-limits')
@auth_required
@require_permission('spc.view')
def patrol_live_limits():
    """巡檢即時模式：查詢生效中的 SPC 管制界限與最近歷史值（唯讀，供前端即時提示）"""
    data = PatrolService.get_live_limits(request.args)
    return jsonify(data)

@patrol_bp.route('/api/patrol/detail/<int:id>')
@auth_required
@require_permission('patrol.view')
def patrol_detail(id):
    data = PatrolService.get_detail(id)
    if data is None:
        return api_error("資料不存在", 404, code="NOT_FOUND")
    return jsonify(data)

@patrol_bp.route('/api/patrol/<int:main_id>/details', methods=['GET'])
@auth_required
@require_permission('patrol.view')
def get_patrol_details_route(main_id):
    """取得單筆巡檢記錄的量測明細（含離群標記）"""
    return jsonify(PatrolService.get_patrol_details(main_id))


@patrol_bp.route('/api/patrol-details/<int:detail_id>/exclusion', methods=['PATCH'])
@auth_required
@require_permission('patrol.edit')
@require_permission('spc.manage')
def set_patrol_detail_exclusion_route(detail_id):
    """標示/解除巡檢量測明細離群排除（AIAG-VDA SPC 2026 §6.6）"""
    try:
        body = request.get_json(silent=True) or {}
        result = PatrolService.set_patrol_detail_exclusion(
            detail_id,
            excluded=bool(body.get('排除統計')),
            reason=body.get('排除原因'),
            actor_id=(request.user.get('id') or request.user.get('user_id')),
        )
        return jsonify(result)
    except ValueError as e:
        return api_error(str(e), 400, code="VALIDATION_ERROR")


@patrol_bp.route('/api/patrol/control-limits', methods=['GET'])
@auth_required
@require_permission('patrol.view')
def get_patrol_control_limits_route():
    """查詢巡檢管制界限凍結狀態（AIAG-VDA SPC 2026 §9.4）"""
    key = {
        "material": request.args.get('material', ''),
        "spec": request.args.get('spec', ''),
        "item": request.args.get('item', '外徑'),
        "position": request.args.get('position', ''),
    }
    legacy = PatrolService.get_frozen_limits(key)
    if legacy:
        legacy.update({"status": "legacy_imported", "audit_incomplete": True})
    return jsonify(legacy or {})


@patrol_bp.route('/api/patrol/control-limits', methods=['POST'])
@auth_required
@require_permission('patrol.view')
def freeze_patrol_control_limits_route():
    """舊凍結流程已停用；正式界限必須走研究送審與核准。"""
    return jsonify({
        "success": False,
        "code": "LEGACY_SPC_LIMITS_READ_ONLY",
        "message": "舊 SPC 界限僅供查閱，請改用研究核准流程",
    }), 410


@patrol_bp.route('/api/patrol/control-limits', methods=['DELETE'])
@auth_required
@require_permission('patrol.view')
def unfreeze_patrol_control_limits_route():
    """舊凍結流程已停用；正式界限必須走研究送審與核准。"""
    return jsonify({
        "success": False,
        "code": "LEGACY_SPC_LIMITS_READ_ONLY",
        "message": "舊 SPC 界限僅供查閱，請改用研究核准流程",
    }), 410


@patrol_bp.route('/api/patrol/add', methods=['POST', 'OPTIONS'])
@auth_required
@require_permission('patrol.create')
def patrol_add():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        patrol_id = PatrolService.add_patrol(request.json)
        return jsonify({"success": True, "id": patrol_id})
    except ValueError as e:
        return api_error(str(e), 400, code="VALIDATION_ERROR")

@patrol_bp.route('/api/patrol/update', methods=['POST'])
@auth_required
@require_permission('patrol.edit')
def patrol_update():
    try:
        PatrolService.update_patrol(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return api_error(str(e), 400, code="VALIDATION_ERROR")

@patrol_bp.route('/api/patrol/delete', methods=['POST'])
@auth_required
@require_permission('patrol.delete')
def patrol_delete():
    record_id = (request.json or {}).get('id')
    if not record_id:
        return api_error("缺少記錄 ID", 400, code="VALIDATION_ERROR")
    PatrolService.delete_patrol(record_id)
    return jsonify({"success": True})

@patrol_bp.route('/api/patrol/history')
@auth_required
@require_permission('patrol.view')
def patrol_history():
    result = PatrolService.get_history(request.args)
    return jsonify(result)

@patrol_bp.route('/api/patrol/export')
@auth_required
@require_permission('patrol.view')
def patrol_export():
    try:
        # 動態檔名：包含測量項目與位置資訊
        item = request.args.get('item', '')
        position = request.args.get('position', '')
        if item:
            from ..services.spc_report import SpcReportService
            from ..services.spc_study_service import SpcStudyService, _require_permission

            actor_id = request.user.get('id') or request.user.get('user_id')
            _require_permission(actor_id, 'spc.view')

            version_id = request.args.get('study_version_id', type=int)
            filters = {
                'm_id': request.args.get('m_id'),
                'op_id': request.args.get('op_id'),
                'cust_id': request.args.get('cust_id'),
                'mat': request.args.get('mat', request.args.get('material', '')),
                'spec': request.args.get('spec', ''),
                'item': item,
                # UI 的「全段」代表不限制位置；研究版本與報表驗證必須使用
                # 同一份 canonical filters，不能將展示文字保存為位置條件。
                'pos': '' if position == '全段' else position,
                's_date': request.args.get('s_date', request.args.get('start_date', '')),
                'e_date': request.args.get('e_date', request.args.get('end_date', '')),
            }
            if version_id is None:
                version_id = SpcStudyService.analyze('patrol', filters, actor_id).id
            output = SpcReportService.generate_version_report(
                version_id, expected_source='patrol', expected_filters=filters
            )
            filename = f'巡檢數據_SPC_{item}_{position or "全段"}.xlsx'
        else:
            output = PatrolService.export_excel(request.args)
            filename = '巡檢數據.xlsx'
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        from ..services.spc_errors import SpcServiceError
        if isinstance(e, SpcServiceError):
            return jsonify({
                "success": False, "code": e.code, "message": e.message,
            }), e.status_code
        raise

@patrol_bp.route('/api/patrol/import', methods=['POST', 'OPTIONS'])
@auth_required
@require_permission('patrol.create')
def patrol_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return api_error("沒有上傳檔案", 400, code="VALIDATION_ERROR")

    file = request.files['file']
    if file.filename == '':
        return api_error("沒有選擇檔案", 400, code="VALIDATION_ERROR")

    upload_error = validate_upload_file(file)
    if upload_error:
        return api_error(upload_error, 400, code="VALIDATION_ERROR")

    try:
        count = PatrolService.import_data(file)
        return jsonify({"success": True, "message": f"匯入成功，共 {count} 筆資料"})
    except ValueError as e:
        return api_error(str(e), 400, code="VALIDATION_ERROR")
