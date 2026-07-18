from flask import Blueprint, jsonify, request, send_file
from ..services.patrol_service import PatrolService
from ..utils import auth_required, require_perm, handle_db_error, validate_upload_file

patrol_bp = Blueprint('patrol', __name__)

@patrol_bp.route('/api/patrol/options')
@auth_required
def patrol_options():
    try:
        options = PatrolService.get_options()
        return jsonify(options)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/spc')
@auth_required
def patrol_spc():
    try:
        data = PatrolService.get_spc(request.args)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/detail/<int:id>')
@auth_required
def patrol_detail(id):
    try:
        data = PatrolService.get_detail(id)
        if data is None:
            return jsonify({"error": "資料不存在"}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/<int:main_id>/details', methods=['GET'])
@auth_required
def get_patrol_details_route(main_id):
    """取得單筆巡檢記錄的量測明細（含離群標記）"""
    try:
        return jsonify(PatrolService.get_patrol_details(main_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol-details/<int:detail_id>/exclusion', methods=['PATCH'])
@auth_required
@require_perm('patrol.edit')
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
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/control-limits', methods=['GET'])
@auth_required
def get_patrol_control_limits_route():
    """查詢巡檢管制界限凍結狀態（AIAG-VDA SPC 2026 §9.4）"""
    try:
        key = {
            "material": request.args.get('material', ''),
            "spec": request.args.get('spec', ''),
            "item": request.args.get('item', '外徑'),
            "position": request.args.get('position', ''),
        }
        return jsonify(PatrolService.get_frozen_limits(key) or {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/control-limits', methods=['POST'])
@auth_required
@require_perm('patrol.edit')
def freeze_patrol_control_limits_route():
    """凍結巡檢目前管制界限（AIAG-VDA SPC 2026 §9.4）"""
    try:
        body = request.get_json(silent=True) or {}
        key = {
            "material": body.get('material', ''),
            "spec": body.get('spec', ''),
            "item": body.get('item', '外徑'),
            "position": body.get('position', ''),
        }
        # skip_frozen_limits=True：即使此 key 已凍結，也要取得依目前資料重新計算
        # 的數值，避免「重新凍結」只是把舊的凍結值原封不動寫回去（§9.4）
        stats = PatrolService.get_spc(
            {'mat': key['material'], 'spec': key['spec'], 'item': key['item'], 'pos': key['position']},
            skip_frozen_limits=True,
        )
        limits = {k: stats[k] for k in ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl")}
        limits["avg_n"] = stats.get("avg_subgroup_size", 5)
        result = PatrolService.freeze_control_limits(key, limits, note=body.get('note', ''))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/control-limits', methods=['DELETE'])
@auth_required
@require_perm('patrol.edit')
def unfreeze_patrol_control_limits_route():
    """解除巡檢管制界限凍結（AIAG-VDA SPC 2026 §9.4）"""
    try:
        key = {
            "material": request.args.get('material', ''),
            "spec": request.args.get('spec', ''),
            "item": request.args.get('item', '外徑'),
            "position": request.args.get('position', ''),
        }
        PatrolService.unfreeze_control_limits(key)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@patrol_bp.route('/api/patrol/add', methods=['POST', 'OPTIONS'])
@auth_required
@require_perm('patrol.create')
def patrol_add():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        patrol_id = PatrolService.add_patrol(request.json)
        return jsonify({"success": True, "id": patrol_id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/update', methods=['POST'])
@auth_required
@require_perm('patrol.create')
def patrol_update():
    try:
        PatrolService.update_patrol(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/delete', methods=['POST'])
@auth_required
@require_perm('patrol.delete')
def patrol_delete():
    try:
        record_id = request.json.get('id')
        if not record_id:
            return jsonify({"error": "缺少記錄 ID"}), 400
        PatrolService.delete_patrol(record_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/history')
@auth_required
def patrol_history():
    try:
        result = PatrolService.get_history(request.args)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/export')
@auth_required
def patrol_export():
    try:
        output = PatrolService.export_excel(request.args)
        # 動態檔名：包含測量項目與位置資訊
        item = request.args.get('item', '')
        position = request.args.get('position', '')
        if item:
            filename = f'巡檢數據_SPC_{item}_{position or "全段"}.xlsx'
        else:
            filename = '巡檢數據.xlsx'
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/import', methods=['POST', 'OPTIONS'])
@auth_required
@require_perm('patrol.create')
def patrol_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    upload_error = validate_upload_file(file)
    if upload_error:
        return jsonify({"error": upload_error}), 400

    try:
        count = PatrolService.import_data(file)
        return jsonify({"success": True, "message": f"匯入成功，共 {count} 筆資料"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
