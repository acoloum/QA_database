from flask import Blueprint, jsonify, request, send_file
from ..services.shipping_service import ShippingService
from ..services.spc_report import SpcReportService
from ..utils import api_error, auth_required, require_perm, handle_db_error, validate_upload_file

shipping_bp = Blueprint('shipping', __name__)

@shipping_bp.route('/api/data', methods=['GET'])
@auth_required
@require_perm('shipping.view')
def get_data():
    try:
        result = ShippingService.get_list(request.args)
        return jsonify(result)
    except Exception:
        raise

@shipping_bp.route('/api/data/<int:data_id>', methods=['GET'])
@auth_required
@require_perm('shipping.view')
def get_shipping_data(data_id):
    """根據 ID 獲取單筆出貨檢驗資料"""
    try:
        result = ShippingService.get_by_id(data_id)
        if result is None:
            return api_error('資料不存在', 404)
        return jsonify(result)
    except Exception:
        raise

@shipping_bp.route('/api/stats', methods=['GET'])
@auth_required
@require_perm('shipping.view')
def get_shipping_stats():
    """獲取出貨檢驗的 SPC 統計數據"""
    try:
        result = ShippingService.get_stats(request.args)
        return jsonify(result)
    except Exception:
        raise

@shipping_bp.route('/api/data/<int:data_id>/measurements', methods=['GET'])
@auth_required
@require_perm('shipping.view')
def get_shipping_measurements(data_id):
    """取得單筆出貨記錄的量測明細（含離群標記）"""
    try:
        return jsonify(ShippingService.get_measurements(data_id))
    except Exception:
        raise


@shipping_bp.route('/api/measurements/<int:measurement_id>/exclusion', methods=['PATCH'])
@auth_required
@require_perm('shipping.edit')
@require_perm('spc.manage')
def set_measurement_exclusion(measurement_id):
    """標示/解除量測值離群排除（AIAG-VDA SPC 2026 §6.6）"""
    try:
        body = request.get_json(silent=True) or {}
        result = ShippingService.set_measurement_exclusion(
            measurement_id,
            excluded=bool(body.get('排除統計')),
            reason=body.get('排除原因'),
            actor_id=(request.user.get('id') or request.user.get('user_id')),
        )
        return jsonify(result)
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception:
        raise


@shipping_bp.route('/api/control-limits', methods=['GET'])
@auth_required
@require_perm('spc.view')
def get_control_limits_route():
    """查詢管制界限凍結狀態（AIAG-VDA SPC 2026 §9.4）"""
    try:
        key = {
            "vendor": request.args.get('vendor', ''),
            "material": request.args.get('material', ''),
            "spec": request.args.get('spec', ''),
            "field": request.args.get('field', '外徑'),
        }
        legacy = ShippingService.get_frozen_limits(key)
        if legacy:
            legacy.update({"status": "legacy_imported", "audit_incomplete": True})
        return jsonify(legacy or {})
    except Exception:
        raise


@shipping_bp.route('/api/control-limits', methods=['POST'])
@auth_required
@require_perm('spc.view')
def freeze_control_limits_route():
    """舊凍結流程已停用；正式界限必須走研究送審與核准。"""
    return jsonify({
        "success": False,
        "code": "LEGACY_SPC_LIMITS_READ_ONLY",
        "message": "舊 SPC 界限僅供查閱，請改用研究核准流程",
    }), 410


@shipping_bp.route('/api/control-limits', methods=['DELETE'])
@auth_required
@require_perm('spc.view')
def unfreeze_control_limits_route():
    """舊凍結流程已停用；正式界限必須走研究送審與核准。"""
    return jsonify({
        "success": False,
        "code": "LEGACY_SPC_LIMITS_READ_ONLY",
        "message": "舊 SPC 界限僅供查閱，請改用研究核准流程",
    }), 410


@shipping_bp.route('/api/spc-report', methods=['GET'])
@auth_required
@require_perm('shipping.view')
@require_perm('spc.view')
def export_spc_report():
    """只由不可變研究版本匯出 SPC 報告，避免混入目前來源資料。"""
    try:
        field = request.args.get('field', '外徑')
        filters = {
            'vendor': request.args.get('vendor', ''),
            'material': request.args.get('material', ''),
            'spec': request.args.get('spec', ''),
            'field': field,
            'start_date': request.args.get('start_date', ''),
            'end_date': request.args.get('end_date', ''),
        }
        version_id = request.args.get('study_version_id', type=int)
        if version_id is None:
            from ..services.spc_study_service import SpcStudyService

            actor_id = request.user.get('id') or request.user.get('user_id')
            version = SpcStudyService.analyze('shipping', filters, actor_id)
            version_id = version.id
        output = SpcReportService.generate_version_report(
            version_id, expected_source='shipping', expected_filters=filters
        )

        filename = f'出貨檢驗_SPC報告_{field}_{filters["material"] or "all"}.xlsx'
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

@shipping_bp.route('/api/add', methods=['POST'])
@auth_required
@require_perm('shipping.create')
def save_data():
    try:
        ShippingService.save_data(request.json, is_update=False)
        return jsonify({"success": True})
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception as e:
        db_err = handle_db_error(e)
        return api_error(db_err.get('message', '資料庫錯誤'), 500, details=db_err)


@shipping_bp.route('/api/update', methods=['POST'])
@auth_required
@require_perm('shipping.edit')
def update_data():
    try:
        ShippingService.save_data(request.json, is_update=True)
        return jsonify({"success": True})
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception as e:
        db_err = handle_db_error(e)
        return api_error(db_err.get('message', '資料庫錯誤'), 500, details=db_err)

@shipping_bp.route('/api/delete', methods=['POST'])
@auth_required
@require_perm('shipping.delete')
def delete_data():
    try:
        record_id = request.json.get('id')
        if not record_id:
            return api_error("缺少記錄 ID", 400)
        
        ShippingService.delete_data(record_id)
        return jsonify({"success": True})
    except Exception:
        raise

@shipping_bp.route('/api/import', methods=['POST', 'OPTIONS'])
@auth_required
@require_perm('shipping.create')
def shipping_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return api_error("沒有上傳檔案", 400)

    file = request.files['file']
    if file.filename == '':
        return api_error("沒有選擇檔案", 400)

    upload_error = validate_upload_file(file)
    if upload_error:
        return api_error(upload_error, 400)

    try:
        count = ShippingService.import_data(file)
        return jsonify({"success": True, "message": f"匯入成功，共 {count} 筆資料"})
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception:
        raise

@shipping_bp.route('/api/export/excel')
@auth_required
@require_perm('shipping.view')
def export_excel():
    try:
        output = ShippingService.export_excel(request.args)
        return send_file(
            output, 
            as_attachment=True, 
            download_name='出貨檢驗數據.xlsx', 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception:
        raise

