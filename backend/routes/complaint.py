"""客訴路由 — CRUD、統計、開立 CAPA"""
from flask import Blueprint, jsonify, request
from datetime import date
from ..extensions import db
from ..services.complaint_service import ComplaintService
from ..services.complaint_stats_service import ComplaintStatsService
from ..utils import auth_required, require_permission, log_audit

complaint_bp = Blueprint('complaint', __name__)


# ── 列表 / 建立 ───────────────────────────────────────────────
@complaint_bp.route('/api/complaints', methods=['GET'])
@auth_required
def list_complaints(current_user):
    """GET /api/complaints — 客訴列表，支援多維篩選"""
    try:
        result = ComplaintService.list_complaints(
            customer       = request.args.get('customer'),
            material       = request.args.get('material'),
            spec           = request.args.get('spec'),
            status         = request.args.get('status'),
            complaint_type = request.args.get('complaint_type'),
            date_from      = _parse_date(request.args.get('date_from')),
            date_to        = _parse_date(request.args.get('date_to')),
            is_repeat      = _parse_bool(request.args.get('is_repeat')),
            page           = int(request.args.get('page', 1)),
            per_page       = int(request.args.get('per_page', 20)),
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@complaint_bp.route('/api/complaints', methods=['POST'])
@auth_required
def create_complaint(current_user):
    """POST /api/complaints — 新增客訴"""
    data = request.get_json() or {}
    try:
        result = ComplaintService.create(data, creator_id=current_user.id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 單筆操作 ─────────────────────────────────────────────────
@complaint_bp.route('/api/complaints/<int:complaint_id>', methods=['GET'])
@auth_required
def get_complaint(current_user, complaint_id: int):
    """GET /api/complaints/<id>"""
    c = ComplaintService.get_detail(complaint_id)
    if not c:
        return jsonify({'error': '客訴不存在'}), 404
    return jsonify(c), 200


@complaint_bp.route('/api/complaints/<int:complaint_id>', methods=['PUT'])
@auth_required
def update_complaint(current_user, complaint_id: int):
    """PUT /api/complaints/<id>"""
    data = request.get_json() or {}
    try:
        result = ComplaintService.update(complaint_id, data)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@complaint_bp.route('/api/complaints/<int:complaint_id>', methods=['DELETE'])
@auth_required
@require_permission('complaint.delete')
def delete_complaint(current_user, complaint_id: int):
    """DELETE /api/complaints/<id>"""
    try:
        ComplaintService.delete(complaint_id)
        log_audit(current_user.id, 'delete', '客訴', complaint_id)
        db.session.commit()
        return jsonify({'message': '刪除成功'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 開立 CAPA ────────────────────────────────────────────────
@complaint_bp.route('/api/complaints/<int:complaint_id>/open-capa', methods=['POST'])
@auth_required
def open_capa_from_complaint(current_user, complaint_id: int):
    """POST /api/complaints/<id>/open-capa — 從客訴開立 CAPA"""
    try:
        from ..services.capa_service import CAPAService
        source_info = ComplaintService.prepare_capa_source(complaint_id)
        capa = CAPAService.create_from_source(
            source_type  = source_info['source_type'],
            source_id    = source_info['source_id'],
            symptom      = source_info['symptom'],
            severity     = source_info.get('severity', 'Major'),
            creator_id   = current_user.id,
        )
        # 更新客訴關聯，並將狀態改為「處理中」
        from ..models import CustomerComplaint
        c = db.session.get(CustomerComplaint, complaint_id)
        if c:
            c.related_capa_id = capa['id']
            c.status = '處理中'
            db.session.commit()
        return jsonify(capa), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ── 從客訴開立重工 ────────────────────────────────────────────
@complaint_bp.route('/api/complaints/<int:complaint_id>/open-rework', methods=['POST'])
@auth_required
def open_rework_from_complaint(current_user, complaint_id: int):
    """POST /api/complaints/<id>/open-rework — 從客訴開立重工申請單"""
    try:
        result = ComplaintService.open_rework(complaint_id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Dashboard 快查 ───────────────────────────────────────────
@complaint_bp.route('/api/complaints/overdue', methods=['GET'])
@auth_required
def overdue_complaints(current_user):
    """GET /api/complaints/overdue — 逾期客訴列表"""
    return jsonify(ComplaintService.overdue_list()), 200


@complaint_bp.route('/api/complaints/recent-repeats', methods=['GET'])
@auth_required
def recent_repeat_complaints(current_user):
    """GET /api/complaints/recent-repeats — 近 30 天重複客訴"""
    days = int(request.args.get('days', 30))
    return jsonify(ComplaintService.recent_repeats(days=days)), 200


# ── 統計 ─────────────────────────────────────────────────────
@complaint_bp.route('/api/complaints/stats/by-customer', methods=['GET'])
@auth_required
def stats_by_customer(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_customer(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/by-product', methods=['GET'])
@auth_required
def stats_by_product(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_product(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/by-category', methods=['GET'])
@auth_required
def stats_by_category(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_category(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/by-month', methods=['GET'])
@auth_required
def stats_by_month(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.by_month(df, dt)), 200


@complaint_bp.route('/api/complaints/stats/warranty', methods=['GET'])
@auth_required
def stats_warranty(current_user):
    df, dt = _date_params()
    return jsonify(ComplaintStatsService.warranty_stats(df, dt)), 200


# ── 工具函數 ─────────────────────────────────────────────────
def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except Exception:
        return None


def _parse_bool(val):
    if val is None:
        return None
    return str(val).lower() in ('1', 'true', 'yes')


def _date_params():
    return (
        _parse_date(request.args.get('date_from')),
        _parse_date(request.args.get('date_to')),
    )
