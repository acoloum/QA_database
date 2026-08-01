from flask import Blueprint, jsonify, request
from marshmallow import ValidationError as MarshmallowValidationError
from ..services.ncmr_service import NCMRService, NCMRValidationError
from ..authorization import require_permissions
from ..errors import APIError
from ..schemas import NCMRCreateSchema, NCMRUpdateIdentifierSchema, NCMRUpdateSchema
from ..utils import auth_required, bounded_int, parse_optional_date, require_permission
from ..extensions import db

ncmr_bp = Blueprint('ncmr', __name__)

_ncmr_create_schema = NCMRCreateSchema()
_ncmr_update_identifier_schema = NCMRUpdateIdentifierSchema()
_ncmr_update_schema = NCMRUpdateSchema()


def _json_object():
    """取得 JSON 物件；null、array 與無法解析的 body 均不屬於輸入契約。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        db.session.rollback()
        raise APIError(
            '請求內容必須是 JSON 物件',
            code='INVALID_JSON_BODY',
            status_code=400,
        )
    return payload


def _load_schema(schema, payload):
    """將 Marshmallow 欄位錯誤轉為正式 API envelope。"""
    try:
        return schema.load(payload)
    except MarshmallowValidationError as error:
        db.session.rollback()
        raise APIError(
            '資料驗證失敗',
            code='VALIDATION_ERROR',
            status_code=422,
            details=error.messages,
        ) from error


def _call_ncmr_service(callback, *args, **kwargs):
    """把 service 的領域參照錯誤映射為正式 422 契約。"""
    try:
        return callback(*args, **kwargs)
    except NCMRValidationError as error:
        raise APIError(
            error.message,
            code='VALIDATION_ERROR',
            status_code=422,
            details=error.details,
        ) from error


# ==================================================
# 【不合格品管理】NCMR API
# ==================================================

@ncmr_bp.route('/api/ncmr', methods=['GET'])
@auth_required
@require_permission('ncmr.view')
def get_ncmr_list():
    try:
        params = {
            'page': bounded_int(request.args.get('page'), 1, 1, 1000000),
            'per_page': bounded_int(request.args.get('per_page'), 20, 1, 100),
            'status': request.args.get('status') or None,
            'date_from': parse_optional_date(request.args.get('date_from'), 'date_from'),
            'date_to': parse_optional_date(request.args.get('date_to'), 'date_to'),
            'source': request.args.get('source') or None,
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_ncmr_list(**params)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/add', methods=['POST'])
@auth_required
@require_permission('ncmr.create')
def add_ncmr(current_user):
    payload = _load_schema(_ncmr_create_schema, _json_object())
    ncmr_number = _call_ncmr_service(
        NCMRService.add_ncmr,
        payload,
        actor_id=current_user.id if current_user else None,
    )
    return jsonify({"success": True, "ncmr_number": ncmr_number}), 201

@ncmr_bp.route('/api/ncmr/update', methods=['POST'])
@auth_required
@require_permissions('ncmr.edit', 'ncmr.edit_own', mode='any')
def update_ncmr(current_user):
    raw_payload = _json_object()
    identifier = _load_schema(_ncmr_update_identifier_schema, raw_payload)
    _call_ncmr_service(
        NCMRService.update_ncmr,
        {**raw_payload, '識別碼': identifier['識別碼']},
        actor_id=current_user.id if current_user else None,
        actor=current_user,
        payload_loader=lambda payload: _load_schema(_ncmr_update_schema, payload),
    )
    return jsonify({"success": True})

@ncmr_bp.route('/api/ncmr/delete', methods=['POST'])
@auth_required
@require_permission('ncmr.delete')
def delete_ncmr(current_user):
    ncmr_id = _json_object().get('id')
    if not ncmr_id:
        raise APIError('缺少識別碼', code='VALIDATION_ERROR', status_code=400)
    NCMRService.delete_ncmr(
        ncmr_id,
        actor_id=current_user.id if current_user else None,
    )
    return jsonify({"success": True})

@ncmr_bp.route('/api/ncmr/source_info', methods=['GET'])
@auth_required
@require_permission('ncmr.view')
def get_source_info():
    try:
        info = NCMRService.get_source_info(request.args.get('type'), request.args.get('id'))
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/open-capa', methods=['POST'])
@auth_required
@require_permissions('ncmr.edit', 'capa.create')
def open_capa_from_ncmr(current_user, ncmr_id):
    """POST /api/ncmr/<id>/open-capa — 從 NCMR 開立 CAPA（8D）

    Body（選填）:
    {
      "severity": "Critical | Major | Minor"
    }
    """
    from ..services.capa_service import CAPAService
    data = request.get_json() or {}
    capa = CAPAService.open_from_ncmr(
        ncmr_id,
        severity=data.get('severity', 'Major'),
        actor_id=current_user.id if current_user else None,
    )
    return jsonify(capa), 201


@ncmr_bp.route('/api/ncmr/<int:ncmr_id>', methods=['GET'])
@auth_required
@require_permission('ncmr.view')
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
@require_permission('ncmr.view')
def get_dispositions(ncmr_id):
    try:
        return jsonify(NCMRService.get_dispositions(ncmr_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/reworks', methods=['GET'])
@auth_required
@require_permission('ncmr.view')
def get_ncmr_reworks(ncmr_id):
    try:
        return jsonify(NCMRService.get_ncmr_reworks(ncmr_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ncmr_bp.route('/api/ncmr/<int:ncmr_id>/dispositions', methods=['POST'])
@auth_required
@require_permission('ncmr.disposition')
def create_disposition(current_user, ncmr_id):
    try:
        handler_id = current_user.inspector_id if current_user else None
        did = NCMRService.create_disposition(
            ncmr_id,
            request.json or {},
            handler_id,
            actor_id=current_user.id if current_user else None,
        )
        return jsonify({"success": True, "id": did})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@ncmr_bp.route('/api/ncmr/dispositions/<int:disposition_id>', methods=['PUT'])
@auth_required
@require_permission('ncmr.disposition')
def update_disposition(current_user, disposition_id):
    try:
        NCMRService.update_disposition(
            disposition_id,
            request.json or {},
            actor_id=current_user.id if current_user else None,
        )
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@ncmr_bp.route('/api/ncmr/dispositions/<int:disposition_id>', methods=['DELETE'])
@auth_required
@require_permission('ncmr.disposition')
def delete_disposition(current_user, disposition_id):
    NCMRService.delete_disposition(
        disposition_id,
        actor_id=current_user.id if current_user else None,
    )
    return jsonify({"success": True})


@ncmr_bp.route('/api/ncmr/risk-releases', methods=['GET'])
@auth_required
@require_permission('ncmr.view')
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
@require_permission('capa.view')
def get_capa_list():
    try:
        params = {
            'page': bounded_int(request.args.get('page'), 1, 1, 1000000),
            'per_page': bounded_int(request.args.get('per_page'), 20, 1, 100),
            'status': request.args.get('status') or None,
            'date_from': parse_optional_date(request.args.get('date_from'), 'date_from'),
            'date_to': parse_optional_date(request.args.get('date_to'), 'date_to'),
            'vendor': request.args.get('vendor') or None,
            'material': request.args.get('material') or None,
            'product_info': request.args.get('product_info') or None,
        }
        result = NCMRService.get_capa_list(**params)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/create', methods=['POST'])
@auth_required
@require_permission('capa.create')
def create_capa(current_user):
    try:
        result = NCMRService.create_capa(request.json)
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/detail/<int:id>')
@auth_required
@require_permission('capa.view')
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
@require_permission('capa.edit')
def update_capa(current_user):
    try:
        NCMRService.update_capa(request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ncmr_bp.route('/api/capa/delete', methods=['POST'])
@auth_required
@require_permission('capa.close')
def delete_capa(current_user):
    try:
        capa_id = request.json.get('id')
        if not capa_id:
            return jsonify({"error": "缺少識別碼"}), 400
        NCMRService.delete_capa(capa_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
