
from flask import Blueprint, jsonify, request, send_file
from ..services.tolerance_service import ToleranceService
from ..utils import auth_required, handle_db_error

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
def add_tolerance():
    """新增公差資料"""
    try:
        new_id = ToleranceService.add_tolerance(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/update/<int:id>', methods=['POST'])
@auth_required
def update_tolerance(id):
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
def delete_tolerance(id):
    """刪除公差資料"""
    try:
        ToleranceService.delete_tolerance(id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500

@tolerance_bp.route('/api/tolerance/options', methods=['GET'])
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

@tolerance_bp.route('/api/tolerance/check', methods=['GET', 'OPTIONS'])
def check_tolerance():
    """根據廠商+材質+規格查詢公差標準，用於出貨檢驗驗證"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # Auth verification handled in service or here? 
    # Legacy code did verification manually in route.
    # We should keep it consistent. 
    # Since specific auth logic (token manual check) was present, let's keep it or rely on @auth_required if possible.
    # ORIGINAL CODE manual check:
    # token = request.headers.get('Authorization') ... verify_token(token)
    # The @auth_required decorator does exactly this. 
    # However, legacy code manually checked it because maybe it wanted to support OPTIONS without auth?
    # Flask routes with OPTIONS method usually handle CORS automatically if configured, but here manual.
    # I will apply @auth_required to GET but handle OPTIONS separately found in decorator?
    # Actually @auth_required usually wraps the function. 
    # Let's use manual check to be safe and identical to legacy behavior for now, or just use @auth_required.
    # The legacy code:
    # if request.method == 'OPTIONS': return ..., 200
    # verify_token...
    
    # I'll implement manual check to match legacy `check_tolerance` exact behavior regarding token reading.
    from ..utils import verify_token
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': '缺少認證 Token'}), 401
    if token.startswith('Bearer '):
        token = token[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({'error': '無效或過期的 Token'}), 401
    
    try:
        result = ToleranceService.check_tolerance(request.args)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
