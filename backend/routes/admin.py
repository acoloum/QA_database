from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import text
from datetime import date, timedelta
from ..extensions import db
from ..models import Inspector, Vendor, Machine, Operator, AuditLog
from ..services.date_range import DateWindow, parse_date_window
from ..services.dashboard_service import DashboardService
from ..utils import auth_required, require_permission

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/api/dashboard/stats')
@auth_required
def get_dashboard_stats():
    period = request.args.get('period', 'this_month')
    today = date.today()

    # 自訂日期範圍：格式、順序與跨度驗證失敗時，parse_date_window 拋 ValueError，
    # 由全域 handler 回傳 400 VALIDATION_ERROR。
    if request.args.get('start') or request.args.get('end'):
        window = parse_date_window(request.args)
    elif period == 'this_week':
        # 本週（週一至週日）
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        window = DateWindow(start_date=start, end_date=end)
    elif period == 'last_week':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        window = DateWindow(start_date=start, end_date=end)
    elif period == 'last_month':
        # 上個月
        first_day = today.replace(day=1)
        last_day = first_day - timedelta(days=1)
        start = last_day.replace(day=1)
        end = last_day
        window = DateWindow(start_date=start, end_date=end)
    else:
        # 預設：本月
        start = today.replace(day=1)
        end = today
        window = DateWindow(start_date=start, end_date=end)

    stats = DashboardService.get_stats(window)

    return jsonify({
        "period": period,
        "start_date": window.start_date.isoformat(),
        "end_date": window.end_date.isoformat(),
        "stats": stats
    })


@admin_bp.route('/api/dashboard/todos')
@auth_required
def get_dashboard_todos():
    try:
        return jsonify(DashboardService.get_todos())
    except Exception as e:
        current_app.logger.exception("載入儀表板待辦事項時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/dashboard/trends')
@auth_required
def get_dashboard_trends():
    """P-1：從 36 次查詢降為 6 次 GROUP BY 聚合查詢"""
    try:
        return jsonify(DashboardService.get_trends())
    except Exception as e:
        current_app.logger.exception("載入儀表板趨勢時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


# S-6：以下六個端點加上 @auth_required

@admin_bp.route('/api/inspectors')
@auth_required
def get_inspectors():
    try:
        q = Inspector.query
        group_filter = request.args.get('group')
        if group_filter:
            q = q.filter(Inspector.group == group_filter)
        inspectors = q.order_by(Inspector.group, Inspector.name).all()
        return jsonify([{
            "id":    i.id,
            "name":  i.name.strip() if i.name else "",
            "group": (i.group or "").strip(),
        } for i in inspectors])
    except Exception as e:
        current_app.logger.exception("查詢檢驗人員清單時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/vendors')
@auth_required
def get_vendors():
    try:
        vendors = Vendor.query.all()
        return jsonify([{"id": v.id, "name": v.name.strip() if v.name else ""} for v in vendors])
    except Exception as e:
        current_app.logger.exception("查詢廠商清單時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/machines')
@auth_required
def get_machines():
    try:
        machines = Machine.query.all()
        return jsonify([{"id": m.id, "name": m.name.strip() if m.name else ""} for m in machines])
    except Exception as e:
        current_app.logger.exception("查詢機台清單時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/operators')
@auth_required
def get_operators():
    try:
        operators = Operator.query.all()
        return jsonify([{"id": o.id, "name": o.name.strip() if o.name else ""} for o in operators])
    except Exception as e:
        current_app.logger.exception("查詢操作員清單時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/materials')
@auth_required
def get_materials():
    try:
        result = db.session.execute(text('SELECT DISTINCT "材質" FROM "出貨檢驗數據" WHERE "材質" IS NOT NULL'))
        materials = [row[0].strip() for row in result]
        return jsonify(materials)
    except Exception as e:
        current_app.logger.exception("查詢材質清單時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/specs')
@auth_required
def get_specs():
    try:
        result = db.session.execute(text('SELECT DISTINCT "檢驗規格" FROM "出貨檢驗數據" WHERE "檢驗規格" IS NOT NULL'))
        specs = [row[0].strip() for row in result]
        return jsonify(specs)
    except Exception as e:
        current_app.logger.exception("查詢檢驗規格清單時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/audit-logs', methods=['GET'])
@auth_required
@require_permission('user.manage')
def get_audit_logs(current_user):
    """查詢審計日誌（需 user.manage 權限）"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    module = request.args.get('module')
    user_id = request.args.get('user_id', type=int)

    try:
        q = AuditLog.query.order_by(AuditLog.created_at.desc())
        if module:
            q = q.filter(AuditLog.module == module)
        if user_id:
            q = q.filter(AuditLog.user_id == user_id)

        pagination = q.paginate(page=page, per_page=per_page, error_out=False)
        items = [
            {
                'id': log.id,
                'user_id': log.user_id,
                'username': log.user.username if log.user else '(已刪除)',
                'action': log.action,
                'module': log.module,
                'record_id': log.record_id,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            }
            for log in pagination.items
        ]
        return jsonify({'data': items, 'total': pagination.total, 'page': page, 'per_page': per_page})
    except Exception as e:
        current_app.logger.exception("查詢審計日誌時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500
