"""CARA 路由 — 對外矯正措施要求，簡化 5 步驟（D2/D3/D4/D6/D8）"""
from flask import Blueprint, jsonify, request
from ..services.cara_service import CARAService
from ..utils import auth_required

cara_bp = Blueprint('cara', __name__)


# ── 列表 ─────────────────────────────────────────────────────
@cara_bp.route('/api/caras', methods=['GET'])
@auth_required
def list_caras(current_user):
    """GET /api/caras — CARA 列表，支援篩選"""
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(max(1, int(request.args.get('per_page', 20))), 100)
    except (ValueError, TypeError):
        return jsonify({'error': 'page 與 per_page 必須為整數'}), 400

    try:
        result = CARAService.list_caras(
            status    = request.args.get('status') or None,
            vendor    = request.args.get('vendor') or None,
            date_from = request.args.get('date_from') or None,
            date_to   = request.args.get('date_to') or None,
            page      = page,
            per_page  = per_page,
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 開立 CARA ─────────────────────────────────────────────────
@cara_bp.route('/api/caras', methods=['POST'])
@auth_required
def create_cara(current_user):
    """POST /api/caras — 從 IQC 來料異常 NCMR 開立 CARA

    Body:
    {
      "ncmr_id": 123,
      "d1_leader_id": 5
    }
    """
    data = request.get_json() or {}
    if current_user:
        data.setdefault('d1_leader_id', current_user.id)
    try:
        result = CARAService.create(data)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 單筆明細 ─────────────────────────────────────────────────
@cara_bp.route('/api/caras/<int:cara_id>', methods=['GET'])
@auth_required
def get_cara(current_user, cara_id: int):
    """GET /api/caras/<id> — CARA 明細"""
    detail = CARAService.get_detail(cara_id)
    if not detail:
        return jsonify({'error': 'CARA 不存在'}), 404
    return jsonify(detail), 200


# ── 步驟更新 ─────────────────────────────────────────────────
@cara_bp.route('/api/caras/<int:cara_id>/step', methods=['PATCH'])
@auth_required
def update_step(current_user, cara_id: int):
    """PATCH /api/caras/<id>/step — 更新 D2/D3/D4/D6/D8 步驟欄位

    Body（所有欄位皆為選填）:
    {
      "D2_what": "...", "D2_where": "...", ...,
      "D3_action": "...", "D3_effective_date": "2025-05-01",
      "D4_tool": "5why", "D4_five_why": [...], "D4_root_cause": "...",
      "D6_implement_date": "2025-05-20", "D6_result": "...", "D6_verified": true,
      "D8_confirmation": "...",
      "D1_leader_id": 5
    }
    """
    data = request.get_json() or {}
    try:
        result = CARAService.update_step(cara_id, data)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── D8 結案 ───────────────────────────────────────────────────
@cara_bp.route('/api/caras/<int:cara_id>/close', methods=['POST'])
@auth_required
def close_cara(current_user, cara_id: int):
    """POST /api/caras/<id>/close — D8 結案（需 D6 verified）

    Body:
    {
      "D8_confirmation": "結案確認聲明（必填）"
    }
    """
    data = request.get_json() or {}
    confirmation = data.get('D8_confirmation') or ''
    if not confirmation.strip():
        return jsonify({'error': 'D8 結案確認聲明為必填'}), 400
    try:
        result = CARAService.close(cara_id, confirmation)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 刪除 ─────────────────────────────────────────────────────
@cara_bp.route('/api/caras/<int:cara_id>', methods=['DELETE'])
@auth_required
def delete_cara(current_user, cara_id: int):
    """DELETE /api/caras/<id> — 刪除 CARA（結案後不可刪）"""
    try:
        CARAService.delete(cara_id)
        return jsonify({'message': '刪除成功'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
