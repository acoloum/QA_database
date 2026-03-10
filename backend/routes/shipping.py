from flask import Blueprint, jsonify, request, send_file
from ..services.shipping_service import ShippingService
from ..services.spc_report import SpcReportService
from ..utils import auth_required, handle_db_error

shipping_bp = Blueprint('shipping', __name__)

@shipping_bp.route('/api/data', methods=['GET'])
def get_data():
    try:
        result = ShippingService.get_list(request.args)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shipping_bp.route('/api/data/<int:data_id>', methods=['GET'])
@auth_required
def get_shipping_data(data_id):
    """根據 ID 獲取單筆出貨檢驗資料"""
    try:
        result = ShippingService.get_by_id(data_id)
        if result is None:
            return jsonify({'error': '資料不存在'}), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@shipping_bp.route('/api/stats', methods=['GET'])
@auth_required
def get_shipping_stats():
    """獲取出貨檢驗的 SPC 統計數據"""
    try:
        result = ShippingService.get_stats(request.args)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@shipping_bp.route('/api/spc-report', methods=['GET'])
@auth_required
def export_spc_report():
    """匯出 SPC 統計分析報告 (Excel)"""
    try:
        stats_data = ShippingService.get_stats(request.args)
        field = request.args.get('field', '外徑')
        filters = {
            'vendor': request.args.get('vendor', ''),
            'material': request.args.get('material', ''),
            'spec': request.args.get('spec', ''),
            'start_date': request.args.get('start_date', ''),
            'end_date': request.args.get('end_date', ''),
        }
        output = SpcReportService.generate_report(stats_data, field, filters)
        filename = f'SPC報告_{field}_{filters["material"] or "all"}.xlsx'
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@shipping_bp.route('/api/add', methods=['POST'])
@shipping_bp.route('/api/update', methods=['POST'])
@auth_required
def save_data():
    try:
        is_update = request.path.endswith('update')
        ShippingService.save_data(request.json, is_update=is_update)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": handle_db_error(e)}), 500

@shipping_bp.route('/api/delete', methods=['POST'])
@auth_required
def delete_data():
    try:
        record_id = request.json.get('id')
        if not record_id:
            return jsonify({"error": "缺少記錄 ID"}), 400
        
        ShippingService.delete_data(record_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shipping_bp.route('/api/import', methods=['POST', 'OPTIONS'])
@auth_required
def shipping_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    try:
        count = ShippingService.import_data(file)
        return jsonify({"success": True, "message": f"匯入成功，共 {count} 筆資料"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@shipping_bp.route('/api/export/excel')
@auth_required
def export_excel():
    try:
        output = ShippingService.export_excel(request.args)
        return send_file(
            output, 
            as_attachment=True, 
            download_name='出貨檢驗數據.xlsx', 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

