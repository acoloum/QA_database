from flask import Blueprint, jsonify, request, send_file
from ..services.patrol_service import PatrolService
from ..utils import auth_required, handle_db_error

patrol_bp = Blueprint('patrol', __name__)

@patrol_bp.route('/api/patrol/options')
def patrol_options():
    try:
        options = PatrolService.get_options()
        return jsonify(options)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/spc')
def patrol_spc():
    try:
        data = PatrolService.get_spc(request.args)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/detail/<int:id>')
def patrol_detail(id):
    try:
        data = PatrolService.get_detail(id)
        if data is None:
            return jsonify({"error": "資料不存在"}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/add', methods=['POST', 'OPTIONS'])
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
def patrol_update():
    try:
        PatrolService.update_patrol(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/delete', methods=['POST'])
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
def patrol_export():
    try:
        output = PatrolService.export_excel(request.args)
        return send_file(
            output, 
            as_attachment=True, 
            download_name='巡檢數據.xlsx', 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@patrol_bp.route('/api/patrol/import', methods=['POST', 'OPTIONS'])
def patrol_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    try:
        count = PatrolService.import_data(file)
        return jsonify({"success": True, "message": f"匯入成功，共 {count} 筆資料"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
