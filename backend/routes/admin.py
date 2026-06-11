from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import text, func, or_, case, and_
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
from ..extensions import db
from ..models import Inspector, Vendor, Machine, Operator, ShippingData, PatrolMain, NCMR, CorrectiveAction, ReworkRequest, AuditLog
from ..utils import auth_required, require_permission

admin_bp = Blueprint('admin', __name__)

def get_stats_for_period(start_date, end_date, compare_start=None, compare_end=None):
    """取得指定期間的統計數據（P-2：每個模型一次查詢同時取得 current / previous 計數）"""

    prev_period_days = (end_date - start_date).days + 1

    if compare_start and compare_end:
        pass
    else:
        compare_start = start_date - timedelta(days=prev_period_days)
        compare_end = start_date - timedelta(days=1)

    # ---------- 待處理計數（點時間，無法合併，保留原本四個函式）----------

    # 注意：須與各清單頁一致，使用 active_query() 排除軟刪除紀錄

    def count_pending_ncmr():
        return NCMR.active_query().filter(
            NCMR.status.notin_(['已結案', 'CAR已完成'])
        ).count()

    def count_pending_capa():
        return CorrectiveAction.active_query().filter(
            CorrectiveAction.eight_d_number != None,
            CorrectiveAction.status.in_(['待處理', '進行中'])
        ).count()

    def count_pending_rework():
        return ReworkRequest.active_query().filter(
            ReworkRequest.status.notin_(['已完成', '已拒絕'])
        ).count()

    # ---------- ShippingData：一次查詢同時取得 current / previous ----------
    shipping_row = db.session.query(
        func.sum(case(
            (and_(ShippingData.date >= start_date, ShippingData.date <= end_date), 1),
            else_=0
        )).label('current'),
        func.sum(case(
            (and_(ShippingData.date >= compare_start, ShippingData.date <= compare_end), 1),
            else_=0
        )).label('previous'),
    ).first()
    _shipping_current = int(shipping_row.current or 0)
    _shipping_previous = int(shipping_row.previous or 0)

    # ShippingData NG：只需 current 期間的 NG 數（rate 僅對當期計算）
    _shipping_ng = db.session.query(
        func.sum(case(
            (and_(ShippingData.date >= start_date, ShippingData.date <= end_date,
                  ShippingData.is_ng == True), 1),
            else_=0
        ))
    ).scalar() or 0
    _shipping_ng = int(_shipping_ng)

    # ---------- PatrolMain：一次查詢同時取得 current / previous ----------
    patrol_row = db.session.query(
        func.sum(case(
            (and_(PatrolMain.date >= start_date, PatrolMain.date <= end_date), 1),
            else_=0
        )).label('current'),
        func.sum(case(
            (and_(PatrolMain.date >= compare_start, PatrolMain.date <= compare_end), 1),
            else_=0
        )).label('previous'),
    ).first()
    _patrol_current = int(patrol_row.current or 0)
    _patrol_previous = int(patrol_row.previous or 0)

    _patrol_ng = db.session.query(
        func.sum(case(
            (and_(PatrolMain.date >= start_date, PatrolMain.date <= end_date,
                  PatrolMain.is_ng == True), 1),
            else_=0
        ))
    ).scalar() or 0
    _patrol_ng = int(_patrol_ng)

    # ---------- NCMR：一次查詢同時取得 current / previous（排除軟刪除）----------
    ncmr_row = db.session.query(
        func.sum(case(
            (and_(NCMR.date >= start_date, NCMR.date <= end_date), 1),
            else_=0
        )).label('current'),
        func.sum(case(
            (and_(NCMR.date >= compare_start, NCMR.date <= compare_end), 1),
            else_=0
        )).label('previous'),
    ).filter(NCMR.deleted_at.is_(None)).first()
    _ncmr_current = int(ncmr_row.current or 0)
    _ncmr_previous = int(ncmr_row.previous or 0)

    # ---------- CorrectiveAction（CAPA / CAR）：一次查詢各取兩期 ----------
    capa_row = db.session.query(
        func.sum(case(
            (and_(CorrectiveAction.created_at >= start_date,
                  CorrectiveAction.created_at <= end_date,
                  CorrectiveAction.eight_d_number != None), 1),
            else_=0
        )).label('current'),
        func.sum(case(
            (and_(CorrectiveAction.created_at >= compare_start,
                  CorrectiveAction.created_at <= compare_end,
                  CorrectiveAction.eight_d_number != None), 1),
            else_=0
        )).label('previous'),
    ).filter(CorrectiveAction.deleted_at.is_(None)).first()
    _capa_current = int(capa_row.current or 0)
    _capa_previous = int(capa_row.previous or 0)

    # ---------- ReworkRequest：一次查詢同時取得 current / previous ----------
    rework_row = db.session.query(
        func.sum(case(
            (and_(ReworkRequest.created_at >= start_date,
                  ReworkRequest.created_at <= end_date), 1),
            else_=0
        )).label('current'),
        func.sum(case(
            (and_(ReworkRequest.created_at >= compare_start,
                  ReworkRequest.created_at <= compare_end), 1),
            else_=0
        )).label('previous'),
    ).filter(ReworkRequest.deleted_at.is_(None)).first()
    _rework_current = int(rework_row.current or 0)
    _rework_previous = int(rework_row.previous or 0)

    # ---------- 組裝回應 ----------
    stats = {
        "shipping": {
            "current": _shipping_current,
            "previous": _shipping_previous,
            "ng_count": _shipping_ng,
            "ng_rate": round((_shipping_ng / _shipping_current * 100), 1) if _shipping_current > 0 else None,
            "pending": 0
        },
        "patrol": {
            "current": _patrol_current,
            "previous": _patrol_previous,
            "ng_count": _patrol_ng,
            "ng_rate": round((_patrol_ng / _patrol_current * 100), 1) if _patrol_current > 0 else None,
            "pending": 0
        },
        "ncmr": {
            "current": _ncmr_current,
            "previous": _ncmr_previous,
            "pending": count_pending_ncmr()
        },
        "capa": {
            "current": _capa_current,
            "previous": _capa_previous,
            "pending": count_pending_capa()
        },
        "rework": {
            "current": _rework_current,
            "previous": _rework_previous,
            "pending": count_pending_rework()
        }
    }

    # 計算趨勢
    for key in stats:
        curr = stats[key]['current']
        prev = stats[key]['previous']
        if prev == 0:
            stats[key]['trend'] = 'up' if curr > 0 else 'stable'
            stats[key]['change_pct'] = 0
        else:
            change = ((curr - prev) / prev) * 100
            stats[key]['change_pct'] = round(change, 1)
            if change > 10:
                stats[key]['trend'] = 'up'
            elif change < -10:
                stats[key]['trend'] = 'down'
            else:
                stats[key]['trend'] = 'stable'

    return stats


@admin_bp.route('/api/dashboard/stats')
@auth_required
def get_dashboard_stats():
    period = request.args.get('period', 'this_month')
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    today = date.today()

    try:
        if start_date and end_date:
            # 自訂日期範圍
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        elif period == 'this_week':
            # 本週（週一至週日）
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif period == 'last_week':
            start = today - timedelta(days=today.weekday() + 7)
            end = start + timedelta(days=6)
        elif period == 'last_month':
            # 上個月
            first_day = today.replace(day=1)
            last_day = first_day - timedelta(days=1)
            start = last_day.replace(day=1)
            end = last_day
        else:
            # 預設：本月
            start = today.replace(day=1)
            end = today

        stats = get_stats_for_period(start, end)

        return jsonify({
            "period": period,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "stats": stats
        })
    except Exception as e:
        current_app.logger.exception("載入儀表板統計時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/dashboard/todos')
@auth_required
def get_dashboard_todos():
    today = date.today()

    try:
        todos = []

        pending_ncmrs = NCMR.active_query().filter(NCMR.status == '待處理').order_by(NCMR.date.desc()).limit(5).all()
        for n in pending_ncmrs:
            todos.append({
                "type": "ncmr",
                "id": n.ncmr_number,
                "title": f"NCMR {n.ncmr_number} 待處理",
                "description": n.description[:50] + "..." if n.description and len(n.description or "") > 50 else n.description,
                "date": n.date.isoformat() if n.date else None,
                "priority": "high",
                "path": "/ncmr"
            })

        # CAPA 項目（8D 編號存在）
        pending_capas = CorrectiveAction.active_query().filter(
            CorrectiveAction.eight_d_number != None,
            CorrectiveAction.status.in_(['待處理', '進行中'])
        ).order_by(CorrectiveAction.created_at.desc()).limit(5).all()
        for c in pending_capas:
            todos.append({
                "type": "capa",
                "id": c.eight_d_number,
                "title": f"CAPA {c.eight_d_number} {c.status}",
                "description": c.d2[:50] + "..." if c.d2 and len(c.d2) > 50 else c.d2,
                "date": c.created_at.isoformat() if c.created_at else None,
                "priority": "medium",
                "path": "/capa"
            })

        pending_reworks = ReworkRequest.active_query().filter(
            ReworkRequest.status.in_(['待審核', '已通過', '進行中'])
        ).order_by(ReworkRequest.created_at.desc()).limit(5).all()
        for r in pending_reworks:
            todos.append({
                "type": "rework",
                "id": r.rework_number,
                "title": f"重工 {r.rework_number} {r.status}",
                "description": r.reason[:50] + "..." if r.reason and len(r.reason) > 50 else r.reason,
                "date": r.created_at.isoformat() if r.created_at else None,
                "priority": "medium",
                "path": "/rework"
            })

        todos.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)

        return jsonify(todos[:10])
    except Exception as e:
        current_app.logger.exception("載入儀表板待辦事項時發生錯誤: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@admin_bp.route('/api/dashboard/trends')
@auth_required
def get_dashboard_trends():
    """P-1：從 36 次查詢降為 6 次 GROUP BY 聚合查詢"""
    try:
        today = date.today()

        # 安全的跨年月份計算（使用 relativedelta）
        months = []
        for i in range(5, -1, -1):
            m = today.replace(day=1) - relativedelta(months=i)
            months.append(m.strftime('%Y-%m'))

        six_months_ago = today.replace(day=1) - relativedelta(months=5)

        # --- NCMR 按月聚合（1 次查詢）---
        ncmr_rows = db.session.query(
            func.to_char(NCMR.date, 'YYYY-MM').label('month'),
            func.count().label('cnt')
        ).filter(
            NCMR.date >= six_months_ago
        ).group_by(
            func.to_char(NCMR.date, 'YYYY-MM')
        ).all()
        ncmr_dict = {row.month: row.cnt for row in ncmr_rows}

        # --- ShippingData OK 按月聚合（1 次查詢）---
        shipping_ok_rows = db.session.query(
            func.to_char(ShippingData.date, 'YYYY-MM').label('month'),
            func.count().label('cnt')
        ).filter(
            ShippingData.date >= six_months_ago,
            or_(ShippingData.is_ng == False, ShippingData.is_ng == None)
        ).group_by(
            func.to_char(ShippingData.date, 'YYYY-MM')
        ).all()
        shipping_ok_dict = {row.month: row.cnt for row in shipping_ok_rows}

        # --- ShippingData NG 按月聚合（1 次查詢）---
        shipping_ng_rows = db.session.query(
            func.to_char(ShippingData.date, 'YYYY-MM').label('month'),
            func.count().label('cnt')
        ).filter(
            ShippingData.date >= six_months_ago,
            ShippingData.is_ng == True
        ).group_by(
            func.to_char(ShippingData.date, 'YYYY-MM')
        ).all()
        shipping_ng_dict = {row.month: row.cnt for row in shipping_ng_rows}

        # --- PatrolMain OK 按月聚合（1 次查詢）---
        patrol_ok_rows = db.session.query(
            func.to_char(PatrolMain.date, 'YYYY-MM').label('month'),
            func.count().label('cnt')
        ).filter(
            PatrolMain.date >= six_months_ago,
            or_(PatrolMain.is_ng == False, PatrolMain.is_ng == None)
        ).group_by(
            func.to_char(PatrolMain.date, 'YYYY-MM')
        ).all()
        patrol_ok_dict = {row.month: row.cnt for row in patrol_ok_rows}

        # --- PatrolMain NG 按月聚合（1 次查詢）---
        patrol_ng_rows = db.session.query(
            func.to_char(PatrolMain.date, 'YYYY-MM').label('month'),
            func.count().label('cnt')
        ).filter(
            PatrolMain.date >= six_months_ago,
            PatrolMain.is_ng == True
        ).group_by(
            func.to_char(PatrolMain.date, 'YYYY-MM')
        ).all()
        patrol_ng_dict = {row.month: row.cnt for row in patrol_ng_rows}

        # --- ReworkRequest 按月聚合（1 次查詢）---
        rework_rows = db.session.query(
            func.to_char(func.cast(ReworkRequest.created_at, db.Date), 'YYYY-MM').label('month'),
            func.count().label('cnt')
        ).filter(
            func.cast(ReworkRequest.created_at, db.Date) >= six_months_ago
        ).group_by(
            func.to_char(func.cast(ReworkRequest.created_at, db.Date), 'YYYY-MM')
        ).all()
        rework_dict = {row.month: row.cnt for row in rework_rows}

        # 補零並組裝既有回應格式
        trends = {
            "ncmr_by_month": [{"month": m, "count": ncmr_dict.get(m, 0)} for m in months],
            "shipping_ok_by_month": [{"month": m, "count": shipping_ok_dict.get(m, 0)} for m in months],
            "shipping_ng_by_month": [{"month": m, "count": shipping_ng_dict.get(m, 0)} for m in months],
            "patrol_ok_by_month": [{"month": m, "count": patrol_ok_dict.get(m, 0)} for m in months],
            "patrol_ng_by_month": [{"month": m, "count": patrol_ng_dict.get(m, 0)} for m in months],
            "rework_by_month": [{"month": m, "count": rework_dict.get(m, 0)} for m in months],
        }

        return jsonify(trends)
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
