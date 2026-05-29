from flask import Blueprint, jsonify, request
from marshmallow import Schema, fields, validate, ValidationError, EXCLUDE
from ..services.ncmr_service import NCMRService
from ..utils import auth_required, require_permission, log_audit
from ..extensions import db

ncmr_bp = Blueprint('ncmr', __name__)

class NCMRCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    日期 = fields.Date(required=True)
    來源 = fields.String(required=True, validate=validate.Length(min=1, max=100))
    廠商 = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=200))
    材質 = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    批號 = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    產品資訊 = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=500))
    產品數量 = fields.Integer(load_default=None, allow_none=True, validate=validate.Range(min=0))
    不良描述 = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=1000))
    不合格數量 = fields.Integer(load_default=None, allow_none=True, validate=validate.Range(min=0))

_ncmr_create_schema = NCMRCreateSchema()

# ==================================================
# 【不合格品管理】NCMR API
# ==================================================

@ncmr_bp.route('/api/ncmr', methods=['GET'])
@auth_required
def get_ncmr_list():
    try:
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(max(1, int(request.args.get('per_page', 20))), 100)
        except (ValueError, TypeError):
            return jsonify({"error": "page 與 per_page 必須為整數"}), 400
        params = {
            'page': page,
            'per_page': per_page,
            'status': request.args.get('status') or None,
            'date_from': request.args.get('date_from') or None,
            'date_to': request.args.get('date_to') or None,
            'source': request.args.get('source') or None,
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_ncmr_list(**params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/add', methods=['POST'])
@auth_required
@require_permission('ncmr.create')
def add_ncmr(current_user):
    payload = {k: (None if v == '' else v) for k, v in (request.json or {}).items()}
    try:
        _ncmr_create_schema.load(payload)
    except ValidationError as err:
        return jsonify({"error": "資料驗證失敗", "details": err.messages}), 400
    try:
        ncmr_number = NCMRService.add_ncmr(request.json)
        try:
            log_audit(current_user.id if current_user else None, 'create', 'NCMR',
                      new_val={'ncmr_number': ncmr_number})
            db.session.commit()
        except Exception:
            db.session.rollback()
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
@require_permission('ncmr.delete')
def delete_ncmr(current_user):
    try:
        ncmr_id = request.json.get('id')
        if not ncmr_id:
            return jsonify({"error": "缺少識別碼"}), 400
        NCMRService.delete_ncmr(ncmr_id)
        try:
            log_audit(current_user.id if current_user else None, 'delete', 'NCMR',
                      record_id=ncmr_id)
            db.session.commit()
        except Exception:
            db.session.rollback()
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

@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/open-capa', methods=['POST'])
@auth_required
def open_capa_from_ncmr(current_user, ncmr_id):
    """POST /api/ncmr/<id>/open-capa — 從 NCMR 開立 CAPA（8D）

    Body（選填）:
    {
      "severity": "Critical | Major | Minor"
    }
    """
    from ..services.capa_service import CAPAService
    from ..models import NCMR as NCMRModel
    from ..extensions import db
    data = request.get_json() or {}
    try:
        ncmr = NCMRModel.query.get(ncmr_id)
        if not ncmr:
            return jsonify({'error': f'NCMR #{ncmr_id} 不存在'}), 404

        # 若該 NCMR 已有關聯 CAPA，阻止重複開立
        if getattr(ncmr, 'related_capa_id', None):
            return jsonify({'error': '此 NCMR 已開立 CAPA，不可重複開立'}), 409

        severity   = data.get('severity', 'Major')
        creator_id = current_user.id if current_user else None
        capa = CAPAService.create_from_source(
            source_type = 'ncmr',
            source_id   = ncmr_id,
            symptom     = ncmr.description,
            severity    = severity,
            creator_id  = creator_id,
        )

        # 回寫 NCMR 關聯
        ncmr.related_capa_id     = capa['id']
        ncmr.related_capa_source = 'capa'
        db.session.commit()

        return jsonify(capa), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
# 【不合格品處置】Disposition API（IATF 16949 §8.7）
# ==================================================

@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/dispositions', methods=['GET'])
@auth_required
def get_dispositions(ncmr_id):
    try:
        return jsonify(NCMRService.get_dispositions(ncmr_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/dispositions', methods=['POST'])
@auth_required
@require_permission('ncmr.disposition')
def create_disposition(current_user, ncmr_id):
    try:
        handler_id = current_user.inspector_id if current_user else None
        did = NCMRService.create_disposition(ncmr_id, request.json or {}, handler_id)
        try:
            log_audit(current_user.id if current_user else None, 'create', 'NCMR_DISPOSITION',
                      record_id=did, new_val=request.json)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": True, "id": did})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/dispositions/<int:disposition_id>', methods=['PUT'])
@auth_required
@require_permission('ncmr.disposition')
def update_disposition(current_user, disposition_id):
    try:
        NCMRService.update_disposition(disposition_id, request.json or {})
        try:
            log_audit(current_user.id if current_user else None, 'update', 'NCMR_DISPOSITION',
                      record_id=disposition_id, new_val=request.json)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/dispositions/<int:disposition_id>', methods=['DELETE'])
@auth_required
@require_permission('ncmr.disposition')
def delete_disposition(current_user, disposition_id):
    try:
        NCMRService.delete_disposition(disposition_id)
        try:
            log_audit(current_user.id if current_user else None, 'delete', 'NCMR_DISPOSITION',
                      record_id=disposition_id)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/risk-releases', methods=['GET'])
@auth_required
def get_risk_releases():
    try:
        return jsonify(NCMRService.get_risk_releases())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================
# 【異常矯正】CAPA API (8D)
# ==================================================

@ncmr_bp.route('/api/capa', methods=['GET'])
@auth_required
def get_capa_list():
    try:
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(max(1, int(request.args.get('per_page', 20))), 100)
        except (ValueError, TypeError):
            return jsonify({"error": "page 與 per_page 必須為整數"}), 400
        params = {
            'page': page,
            'per_page': per_page,
            'status': request.args.get('status') or None,
            'date_from': request.args.get('date_from') or None,
            'date_to': request.args.get('date_to') or None,
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_capa_list(**params)
        return jsonify(result)
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
