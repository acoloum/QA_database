"""客訴路由 — CRUD、統計、開立 CAPA"""
from flask import Blueprint, jsonify, request
from ..services.complaint_service import ComplaintService
from ..services.complaint_stats_service import ComplaintStatsService
from ..errors import APIError
from ..authorization import require_permissions
from ..utils import auth_required, bounded_int, parse_optional_date
from ..authorization import require_permission

complaint_bp = Blueprint('complaint', __name__)


# ── 列表 / 建立 ───────────────────────────────────────────────
@complaint_bp.route('/api/complaints', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def list_complaints(current_user):
    """GET /api/complaints — 客訴列表，支援多維篩選"""
    try:
        result = ComplaintService.list_complaints(
            customer       = request.args.get('customer'),
            material       = request.args.get('material'),
            spec           = request.args.get('spec'),
            status         = request.args.get('status'),
            complaint_type = request.args.get('complaint_type'),
            date_from      = _parse_date(request.args.get('date_from'), 'date_from'),
            date_to        = _parse_date(request.args.get('date_to'), 'date_to'),
            is_repeat      = _parse_bool(request.args.get('is_repeat')),
            page           = bounded_int(request.args.get('page'), 1, 1, 1000000),
            per_page       = bounded_int(request.args.get('per_page'), 20, 1, 100),
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        raise


@complaint_bp.route('/api/complaints', methods=['POST'])
@auth_required
@require_permission('complaint.create')
def create_complaint(current_user):
    """POST /api/complaints — 新增客訴"""
    data = request.get_json() or {}
    try:
        result = ComplaintService.create(data, creator_id=current_user.id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        raise


# ── 單筆操作 ─────────────────────────────────────────────────
@complaint_bp.route('/api/complaints/<int:complaint_id>', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def get_complaint(current_user, complaint_id: int):
    """GET /api/complaints/<id>"""
    c = ComplaintService.get_detail(complaint_id)
    if not c:
        return jsonify({'error': '客訴不存在'}), 404
    return jsonify(c), 200


@complaint_bp.route('/api/complaints/<int:complaint_id>', methods=['PUT'])
@auth_required
@require_permission('complaint.edit')
def update_complaint(current_user, complaint_id: int):
    """PUT /api/complaints/<id>"""
    data = request.get_json() or {}
    try:
        result = ComplaintService.update(complaint_id, data)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        raise


@complaint_bp.route('/api/complaints/<int:complaint_id>', methods=['DELETE'])
@auth_required
@require_permission('complaint.delete')
def delete_complaint(current_user, complaint_id: int):
    """DELETE /api/complaints/<id>"""
    try:
        ComplaintService.delete(complaint_id, actor_id=current_user.id)
        return jsonify({'message': '刪除成功'}), 200
    except APIError as e:
        return jsonify(e.to_dict()), e.status_code
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


# ── 開立 CAPA ────────────────────────────────────────────────
@complaint_bp.route('/api/complaints/<int:complaint_id>/open-capa', methods=['POST'])
@auth_required
@require_permissions('complaint.edit', 'capa.create')
def open_capa_from_complaint(current_user, complaint_id: int):
    """POST /api/complaints/<id>/open-capa — 從客訴開立 CAPA"""
    try:
        capa = ComplaintService.open_capa(complaint_id, actor_id=current_user.id)
        return jsonify(capa), 201
    except APIError as e:
        return jsonify(e.to_dict()), e.status_code
    except ValueError as e:
        return jsonify({'error': str(e)}), 400



# ── 從客訴開立重工 ────────────────────────────────────────────
@complaint_bp.route('/api/complaints/<int:complaint_id>/open-rework', methods=['POST'])
@auth_required
@require_permissions('complaint.edit', 'rework.create')
def open_rework_from_complaint(current_user, complaint_id: int):
    """POST /api/complaints/<id>/open-rework — 從客訴開立重工申請單"""
    try:
        result = ComplaintService.open_rework(complaint_id, actor_id=current_user.id)
        return jsonify(result), 201
    except APIError as e:
        return jsonify(e.to_dict()), e.status_code
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ── Dashboard 快查 ───────────────────────────────────────────
@complaint_bp.route('/api/complaints/overdue', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def overdue_complaints(current_user):
    """GET /api/complaints/overdue — 逾期客訴列表"""
    return jsonify(ComplaintService.overdue_list()), 200


@complaint_bp.route('/api/complaints/recent-repeats', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def recent_repeat_complaints(current_user):
    """GET /api/complaints/recent-repeats — 近 30 天重複客訴"""
    days = bounded_int(request.args.get('days'), 30, 1, 365)
    return jsonify(ComplaintService.recent_repeats(days=days)), 200


# ── 統計 ─────────────────────────────────────────────────────
@complaint_bp.route('/api/complaints/stats/by-customer', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def stats_by_customer(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_customer(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/by-product', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def stats_by_product(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_product(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/by-category', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def stats_by_category(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_category(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/by-month', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def stats_by_month(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_month(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/warranty', methods=['GET'])
@auth_required
@require_permission('complaint.view')
def stats_warranty(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.warranty_stats(df, dt)), 200


# ── 工具函數 ─────────────────────────────────────────────────
def _parse_date(val, field_name='date'):
    return parse_optional_date(val, field_name)


def _parse_bool(val):
    if val is None:
        return None
    return str(val).lower() in ('1', 'true', 'yes')


def _date_params():
    try:
        return (
            _parse_date(request.args.get('date_from'), 'date_from'),
            _parse_date(request.args.get('date_to'), 'date_to'),
        )
    except ValueError:
        return (None, None)
