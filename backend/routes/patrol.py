from flask import Blueprint, jsonify, request, send_file
from ..services.patrol_service import PatrolService
from ..utils import auth_required, handle_db_error

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

@patrol_bp.route('/api/patrol/add', methods=['POST', 'OPTIONS'])
@auth_required
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
def patrol_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    # Validate file type
    allowed_extensions = {'.xlsx', '.xls'}
    import os
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({"error": f"不支援的檔案格式: {ext}，僅接受 .xlsx / .xls"}), 400

    # Validate file size (10MB max)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > 10 * 1024 * 1024:
        return jsonify({"error": "檔案大小超過 10MB 限制"}), 400

    try:
        count = PatrolService.import_data(file)
        return jsonify({"success": True, "message": f"匯入成功，共 {count} 筆資料"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
