
from flask import Blueprint, jsonify, request, send_file
from ..services.tolerance_service import ToleranceService
from ..utils import auth_required, handle_db_error, require_permission

tolerance_bp = Blueprint('tolerance', __name__)

@tolerance_bp.route('/api/tolerance/search', methods=['GET'])
@auth_required
def search_tolerance():
    """
    查詢公差資料
    ---
    tags:
      - Tolerance
    parameters:
      - name: material
        in: query
        type: string
        description: 材質 (模糊搜尋)
      - name: spec
        in: query
        type: string
        description: 規格 (模糊搜尋)
      - name: vendor_id
        in: query
        type: integer
        description: 廠商ID
      - name: page
        in: query
        type: integer
        default: 1
        description: 頁碼
      - name: page_size
        in: query
        type: integer
        default: 20
        description: 每頁筆數
    responses:
      200:
        description: 公差資料列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            total:
              type: integer
            page:
              type: integer
            total_pages:
              type: integer
    """
    result = ToleranceService.search_tolerance(request.args)
    return jsonify(result)

@tolerance_bp.route('/api/tolerance/<int:id>', methods=['GET'])
@auth_required
def get_tolerance_detail(id):
    """
    獲取單筆公差詳細資料
    ---
    tags:
      - Tolerance
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: 公差主檔ID
    responses:
      200:
        description: 公差詳細資料
        schema:
          type: object
          properties:
            success:
              type: boolean
            main:
              type: object
            details:
              type: array
              items:
                type: object
      404:
        description: 找不到資料
    """
    result = ToleranceService.get_tolerance_detail(id)
    return jsonify(result)

@tolerance_bp.route('/api/tolerance/add', methods=['POST'])
@auth_required
@require_permission('tolerance.manage')
def add_tolerance(current_user):
    """新增公差資料"""
    try:
        new_id = ToleranceService.add_tolerance(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/update/<int:id>', methods=['POST'])
@auth_required
@require_permission('tolerance.manage')
def update_tolerance(current_user, id):
    """更新公差資料"""
    try:
        ToleranceService.update_tolerance(id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/delete/<int:id>', methods=['POST'])
@auth_required
@require_permission('tolerance.manage')
def delete_tolerance(current_user, id):
    """刪除公差資料"""
    try:
        ToleranceService.delete_tolerance(id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/options', methods=['GET'])
@auth_required
def get_tolerance_options():
    """獲取公差選項資料"""
    try:
        options = ToleranceService.get_options()
        return jsonify(options)
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/export', methods=['GET'])
@auth_required
def export_tolerance_excel():
    """匯出公差資料為 Excel"""
    try:
        output = ToleranceService.export_excel(request.args)
        return send_file(output, as_attachment=True, download_name='廠商公差資料.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/check', methods=['GET'])
@auth_required
def check_tolerance():
    """根據廠商+材質+規格查詢公差標準，用於出貨檢驗驗證"""
    try:
        result = ToleranceService.check_tolerance(request.args)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
