from flask import Blueprint, jsonify, request
from marshmallow import Schema, fields, validate, ValidationError
from ..services.ncmr_service import NCMRService
from ..utils import auth_required

ncmr_bp = Blueprint('ncmr', __name__)

class NCMRCreateSchema(Schema):
    發現日期 = fields.Date(required=True)
    來源 = fields.String(required=True, validate=validate.Length(min=1, max=100))
    廠商 = fields.String(load_default=None, validate=validate.Length(max=200))
    材質 = fields.String(load_default=None, validate=validate.Length(max=100))
    批號 = fields.String(load_default=None, validate=validate.Length(max=100))
    產品資訊 = fields.String(load_default=None, validate=validate.Length(max=500))
    產品數量 = fields.Integer(load_default=None, validate=validate.Range(min=0))
    不良描述 = fields.String(load_default=None, validate=validate.Length(max=1000))
    不合格數量 = fields.Integer(load_default=None, validate=validate.Range(min=0))

_ncmr_create_schema = NCMRCreateSchema()

# ==================================================
# 【不合格品管理】NCMR API
# ==================================================

@ncmr_bp.route('/api/ncmr', methods=['GET'])
@auth_required
def get_ncmr_list():
    try:
        data = NCMRService.get_ncmr_list(request.args.get('status'))
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/add', methods=['POST'])
@auth_required
def add_ncmr():
    try:
        _ncmr_create_schema.load(request.json or {})
    except ValidationError as err:
        return jsonify({"error": "資料驗證失敗", "details": err.messages}), 400
    try:
        ncmr_number = NCMRService.add_ncmr(request.json)
        return jsonify({"success": True, "ncmr_number": ncmr_number})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/update', methods=['POST'])
@auth_required
def update_ncmr():
    try:
        NCMRService.update_ncmr(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/delete', methods=['POST'])
@auth_required
def delete_ncmr():
    try:
        ncmr_id = request.json.get('id')
        if not ncmr_id:
            return jsonify({"error": "缺少識別碼"}), 400
        NCMRService.delete_ncmr(ncmr_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/source_info', methods=['GET'])
@auth_required
def get_source_info():
    try:
        info = NCMRService.get_source_info(request.args.get('type'), request.args.get('id'))
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/<int:ncmr_id>', methods=['GET'])
@auth_required
def get_ncmr_info(ncmr_id):
    try:
        info = NCMRService.get_ncmr_info(ncmr_id)
        if info is None:
            return jsonify({"error": "找不到NCMR記錄"}), 404
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================
# 【CAR矯正】API
# ==================================================

@ncmr_bp.route('/api/cara', methods=['GET'])
@auth_required
def get_cara_list():
    try:
        data = NCMRService.get_cara_list()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/cara/create', methods=['POST'])
@auth_required
def create_cara():
    try:
        result = NCMRService.create_cara(request.json)
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/cara/detail/<int:id>')
@auth_required
def get_cara_detail(id):
    try:
        data = NCMRService.get_cara_detail(id)
        if data is None:
            return jsonify({"error": "找不到資料"}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/cara/update', methods=['POST'])
@auth_required
def update_cara():
    try:
        NCMRService.update_cara(request.json)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/cara/delete', methods=['POST'])
@auth_required
def delete_cara():
    try:
        cara_id = request.json.get('id')
        if not cara_id:
            return jsonify({"error": "缺少識別碼"}), 400
        NCMRService.delete_cara(cara_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================
# 【異常矯正】CAPA API (8D)
# ==================================================

@ncmr_bp.route('/api/capa', methods=['GET'])
@auth_required
def get_capa_list():
    try:
        data = NCMRService.get_capa_list()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/create', methods=['POST'])
@auth_required
def create_capa():
    try:
        result = NCMRService.create_capa(request.json)
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/detail/<int:id>')
@auth_required
def get_capa_detail(id):
    try:
        data = NCMRService.get_capa_detail(id)
        if data is None:
            return jsonify({"error": "找不到資料"}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/update', methods=['POST'])
@auth_required
def update_capa():
    try:
        NCMRService.update_capa(request.json)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/delete', methods=['POST'])
@auth_required
def delete_capa():
    try:
        capa_id = request.json.get('id')
        if not capa_id:
            return jsonify({"error": "缺少識別碼"}), 400
        NCMRService.delete_capa(capa_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
