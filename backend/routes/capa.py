"""CAPA 路由 — D0-D8 8D 流程 CRUD、步驟更新、Gate 檢查、結案"""
from flask import Blueprint, jsonify, request
from ..services.capa_service import CAPAService
from ..services.task_service import TaskService
from ..utils import auth_required, require_permission, log_audit
from ..extensions import db

capa_bp = Blueprint('capa', __name__)


# ── 列表 ─────────────────────────────────────────────────────
@capa_bp.route('/api/capas', methods=['GET'])
@auth_required
def list_capas(current_user):
    """GET /api/capas — CAPA 列表，支援多維篩選"""
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(max(1, int(request.args.get('per_page', 20))), 100)
    except (ValueError, TypeError):
        return jsonify({'error': 'page 與 per_page 必須為整數'}), 400

    try:
        result = CAPAService.list_capas(
            source_type = request.args.get('source_type') or None,
            status      = request.args.get('status') or None,
            date_from   = request.args.get('date_from') or None,
            date_to     = request.args.get('date_to') or None,
            customer    = request.args.get('customer') or None,
            page        = page,
            per_page    = per_page,
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 逾期查詢（Dashboard 用）──────────────────────────────────
@capa_bp.route('/api/capas/overdue', methods=['GET'])
@auth_required
def overdue_capas(current_user):
    """GET /api/capas/overdue — 依 D0 客戶要求結案日計算逾期 CAPA"""
    try:
        from datetime import date
        from ..models import CorrectiveAction
        today = date.today()
        items = CorrectiveAction.query.filter(
            CorrectiveAction.status.in_(['進行中']),
            CorrectiveAction.d0_deadline.isnot(None),
            CorrectiveAction.d0_deadline < today,
        ).order_by(CorrectiveAction.d0_deadline.asc()).all()
        return jsonify([CAPAService._to_list_dict(ca) for ca in items]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 單筆明細 ─────────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>', methods=['GET'])
@auth_required
def get_capa(current_user, capa_id: int):
    """GET /api/capas/<id> — CAPA 明細"""
    detail = CAPAService.get_detail(capa_id)
    if not detail:
        return jsonify({'error': 'CAPA 不存在'}), 404
    return jsonify(detail), 200


# ── 步驟更新 ─────────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>/step', methods=['PATCH'])
@auth_required
def update_step(current_user, capa_id: int):
    """PATCH /api/capas/<id>/step — 更新任意 D0-D8 步驟欄位

    Body（所有欄位皆為選填，只傳需要更新的欄位）:
    {
      "D0_symptom": "...", "D0_severity": "Critical", "D0_deadline": "2025-06-30",
      "D1_champion_id": 3, "D1_leader_id": 5, "D1_members": [2, 4, 7],
      "D2_what": "...", "D2_where": "...", ...,
      "D3_action": "...", "D3_effective_date": "2025-05-01", "D3_verification": "...",
      "D4_tool": "5why", "D4_five_why": [...], "D4_fishbone": {...}, "D4_root_cause": "...",
      "D5_action": "...", "D5_planned_date": "2025-05-15", "D5_verify_plan": "...",
      "D6_implement_date": "2025-05-20", "D6_result": "...", "D6_verified": true,
      "D7_actions": [{"type": "pfmea", "checked": true, "assignee_id": 5, "due_date": "2025-06-01"}],
      "D8_confirmation": "...", "D8_recognition": "..."
    }
    """
    data = request.get_json() or {}
    try:
        result = CAPAService.update_step(capa_id, data)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── D6 Gate 檢查 ─────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>/d6-gate', methods=['GET'])
@auth_required
def check_d6_gate(current_user, capa_id: int):
    """GET /api/capas/<id>/d6-gate — 查詢 D6 驗證是否通過"""
    try:
        passed = CAPAService.check_d6_gate(capa_id)
        return jsonify({'d6_passed': passed}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 結案 Gate 檢查 ────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>/close-gate', methods=['GET'])
@auth_required
def check_close_gate(current_user, capa_id: int):
    """GET /api/capas/<id>/close-gate — 查詢 D8 結案 gate（任務狀態）"""
    try:
        gate = TaskService.check_close_gate('capa', capa_id)
        d6   = CAPAService.check_d6_gate(capa_id)
        missing = CAPAService.get_missing_step_labels(capa_id)
        gate['d6_passed'] = d6
        gate['missing_steps'] = missing
        gate['can_close'] = gate['can_close'] and d6 and not missing
        return jsonify(gate), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── D8 結案 ───────────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>/close', methods=['POST'])
@auth_required
@require_permission('capa.close')
def close_capa(current_user, capa_id: int):
    """POST /api/capas/<id>/close — D8 結案（需通過 D6 gate 與任務 gate）

    Body:
    {
      "D8_confirmation": "結案確認聲明（必填）",
      "D8_recognition": "團隊表揚內容（選填）"
    }
    """
    data = request.get_json() or {}
    confirmation = data.get('D8_confirmation') or ''
    if not confirmation.strip():
        return jsonify({'error': 'D8 結案確認聲明為必填'}), 400
    try:
        result = CAPAService.close(
            capa_id      = capa_id,
            confirmation = confirmation,
            recognition  = data.get('D8_recognition'),
        )
        log_audit(current_user.id, 'close', 'CAPA', capa_id)
        db.session.commit()
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 刪除 ─────────────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>', methods=['DELETE'])
@auth_required
@require_permission('capa.close')
def delete_capa(current_user, capa_id: int):
    """DELETE /api/capas/<id> — 刪除 CAPA（同步刪除 pending 橫展任務）"""
    try:
        CAPAService.delete(capa_id)
        log_audit(current_user.id, 'delete', 'CAPA', capa_id)
        db.session.commit()
        return jsonify({'message': '刪除成功'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 報表下載 ────────────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>/report/pdf', methods=['GET'])
@auth_required
def download_pdf(current_user, capa_id: int):
    """GET /api/capas/<id>/report/pdf — 下載 AIAG 8D 報表 PDF"""
    detail = CAPAService.get_detail(capa_id)
    if not detail:
        return jsonify({'error': 'CAPA 不存在'}), 404
    try:
        from flask import send_file
        from ..services.eightd_pdf import generate_8d_pdf
        buf = generate_8d_pdf(detail)
        filename = f"8D_{detail.get('no', capa_id)}.pdf"
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@capa_bp.route('/api/capas/<int:capa_id>/report/excel', methods=['GET'])
@auth_required
def download_excel(current_user, capa_id: int):
    """GET /api/capas/<id>/report/excel — 下載 AIAG 8D 報表 Excel"""
    detail = CAPAService.get_detail(capa_id)
    if not detail:
        return jsonify({'error': 'CAPA 不存在'}), 404
    try:
        from flask import send_file
        from ..services.eightd_excel import generate_8d_excel
        buf = generate_8d_excel(detail)
        filename = f"8D_{detail.get('no', capa_id)}.xlsx"
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
