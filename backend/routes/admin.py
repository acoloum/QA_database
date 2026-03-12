from flask import Blueprint, jsonify, request
from sqlalchemy import text, func
from datetime import datetime, timedelta, date
from ..extensions import db
from ..models import Inspector, Vendor, Machine, Operator, ShippingData, PatrolMain, NCMR, CorrectiveAction, ReworkRequest

admin_bp = Blueprint('admin', __name__)

def get_stats_for_period(start_date, end_date, compare_start=None, compare_end=None):
    """取得指定期間的統計數據"""
    
    prev_period_days = (end_date - start_date).days + 1
    
    if compare_start and compare_end:
        compare_prev = True
    else:
        compare_prev = False
        compare_start = start_date - timedelta(days=prev_period_days)
        compare_end = start_date - timedelta(days=1)
    
    def count_for_model(model, date_field, start, end, extra_filter=None):
        query = model.query.filter(date_field >= start, date_field <= end)
        if extra_filter is not None:
            query = query.filter(extra_filter)
        return query.count()
    
    def count_pending_ncmr():
        # Count all NCMR not yet fully resolved
        return NCMR.query.filter(
            NCMR.status.notin_(['已結案', 'CAR已完成'])
        ).count()
    
    def count_pending_capa():
        return CorrectiveAction.query.filter(
            CorrectiveAction.eight_d_number != None,
            CorrectiveAction.status.in_(['待處理', '進行中'])
        ).count()
    
    def count_pending_cara():
        return CorrectiveAction.query.filter(
            CorrectiveAction.car_number != None,
            CorrectiveAction.status.in_(['待處理', '進行中'])
        ).count()
    
    def count_pending_rework():
        # Count all rework not yet completed (includes 申請中, 待審核, 已核准, 執行中, etc.)
        return ReworkRequest.query.filter(
            ReworkRequest.status.notin_(['已完成', '已拒絕'])
        ).count()
    
    stats = {
        "shipping": {
            "current": count_for_model(ShippingData, ShippingData.date, start_date, end_date),
            "previous": count_for_model(ShippingData, ShippingData.date, compare_start, compare_end),
            "pending": 0
        },
        "patrol": {
            "current": count_for_model(PatrolMain, PatrolMain.date, start_date, end_date),
            "previous": count_for_model(PatrolMain, PatrolMain.date, compare_start, compare_end),
            "pending": 0
        },
        "ncmr": {
            "current": count_for_model(NCMR, NCMR.date, start_date, end_date),
            "previous": count_for_model(NCMR, NCMR.date, compare_start, compare_end),
            "pending": count_pending_ncmr()
        },
        "capa": {
            "current": count_for_model(
                CorrectiveAction, CorrectiveAction.created_at, start_date, end_date,
                CorrectiveAction.eight_d_number != None
            ),
            "previous": count_for_model(
                CorrectiveAction, CorrectiveAction.created_at, compare_start, compare_end,
                CorrectiveAction.eight_d_number != None
            ),
            "pending": count_pending_capa()
        },
        "rework": {
            "current": count_for_model(ReworkRequest, ReworkRequest.created_at, start_date, end_date),
            "previous": count_for_model(ReworkRequest, ReworkRequest.created_at, compare_start, compare_end),
            "pending": count_pending_rework()
        },
        "cara": {
            "current": count_for_model(
                CorrectiveAction, CorrectiveAction.created_at, start_date, end_date,
                CorrectiveAction.car_number != None
            ),
            "previous": count_for_model(
                CorrectiveAction, CorrectiveAction.created_at, compare_start, compare_end,
                CorrectiveAction.car_number != None
            ),
            "pending": count_pending_cara()
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
            # 本週 (週一至週日)
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
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/dashboard/todos')
def get_dashboard_todos():
    from datetime import date, timedelta
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    try:
        todos = []
        
        pending_ncmrs = NCMR.query.filter(NCMR.status == '待處理').order_by(NCMR.date.desc()).limit(5).all()
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
        
        # CAR items (car_number exists)
        pending_cars = CorrectiveAction.query.filter(
            CorrectiveAction.car_number != None,
            CorrectiveAction.status.in_(['待處理', '進行中'])
        ).order_by(CorrectiveAction.created_at.desc()).limit(5).all()
        for c in pending_cars:
            todos.append({
                "type": "cara",
                "id": c.car_number,
                "title": f"CAR {c.car_number} {c.status}",
                "description": c.d2[:50] + "..." if c.d2 and len(c.d2) > 50 else c.d2,
                "date": c.created_at.isoformat() if c.created_at else None,
                "priority": "medium",
                "path": "/cara"
            })
        
        # CAPA items (8D number exists)
        pending_capas = CorrectiveAction.query.filter(
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
        
        pending_reworks = ReworkRequest.query.filter(
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
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def parse_spec(spec_str):
    if not spec_str: return {}
    s = str(spec_str).replace('×', '*').replace('x', '*').replace('X', '*')
    while '**' in s: s = s.replace('**', '*')
    parts = s.split('*')
    res = {}
    nums = []
    for p in parts:
        try: nums.append(float(p.strip()))
        except ValueError: pass
    if len(nums) >= 2:
        res['外徑'] = nums[0]
        val2 = nums[1]
        if val2 < (nums[0] / 2.0):
            res['厚度'] = val2
            res['內徑'] = nums[0] - (val2 * 2.0)
        else:
            res['內徑'] = val2
            res['厚度'] = (nums[0] - val2) / 2.0
        if len(nums) >= 3:
            res['長度'] = nums[2]
    elif len(nums) == 1:
        res['外徑'] = nums[0]
    return res

def check_shipping_violation(item, tolerances):
    if not tolerances:
        return False
        
    spec_values = parse_spec(item.spec)
    
    std_limits = {}
    for t in tolerances:
        lsl = float('-inf')
        usl = float('inf')
        
        tc_min = t.get('尺寸下限')
        tc_max = t.get('尺寸上限')
        tol_min = t.get('公差下限')
        tol_max = t.get('公差上限')
        t_std = t.get('標準值')
        t_item = t.get('項目')
        
        if tc_min is not None and tc_max is not None:
            lsl = tc_min
            usl = tc_max
        elif tol_min is not None and tol_max is not None:
            std_val = spec_values.get(t_item, 0)
            if std_val == 0 and t_std is not None:
                std_val = t_std
            if std_val == 0:
                continue
            lsl = std_val + tol_min
            usl = std_val + tol_max
        elif tc_max is not None:
            lsl = 0
            usl = tc_max
        elif tc_min is not None:
            lsl = tc_min
            usl = float('inf')
        else:
            continue
            
        std_limits[t_item] = {'lsl': lsl, 'usl': usl}

    items_to_check = ["外徑", "內徑", "真圓度", "厚度", "同心度", "長度", "硬度", "真直度"]
    gc = item.group_count or 5

    def safe_float(v):
        try: return float(v)
        except (ValueError, TypeError): return None
        
    attr_map = {
        '外徑': 'od',
        '內徑': 'id',
        '厚度': 'th',
        '同心度': 'concentricity',
        '長度': 'length',
        '硬度': 'hardness',
        '真直度': 'straightness',
        '真圓度': 'roundness'
    }

    for it in items_to_check:
        tol = std_limits.get(it)
        if not tol: continue

        attr_prefix = attr_map[it]
        is_minmax = it in ["外徑", "內徑", "厚度"]
        
        for g in range(1, int(gc) + 1):
            if is_minmax:
                v_min = safe_float(getattr(item, f"{attr_prefix}{g}_min", None))
                v_max = safe_float(getattr(item, f"{attr_prefix}{g}_max", None))
                if v_min is not None and (v_min < tol['lsl'] or v_min > tol['usl']): return True
                if v_max is not None and (v_max < tol['lsl'] or v_max > tol['usl']): return True
            else:
                v = safe_float(getattr(item, f"{attr_prefix}{g}", None))
                if v is not None and (v < tol['lsl'] or v > tol['usl']): return True
                
    return False

@admin_bp.route('/api/dashboard/trends')
def get_dashboard_trends():
    from datetime import date, timedelta
    from ..services.tolerance_service import ToleranceService
    
    try:
        trends = {
            "ncmr_by_month": [],
            "shipping_ok_by_month": [],
            "shipping_ng_by_month": [],
            "rework_by_month": []
        }
        
        # Use proper month arithmetic to avoid issues with months of different lengths
        today = date.today()
        current_month_start = today.replace(day=1)
        
        tolerance_cache = {}
        
        for i in range(5, -1, -1):
            # Calculate the target month by subtracting months properly
            year = current_month_start.year
            month = current_month_start.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_start = date(year, month, 1)
            
            # Calculate month end: first day of next month minus 1 day
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)
            
            ncmr_count = NCMR.query.filter(
                NCMR.date >= month_start,
                NCMR.date <= month_end
            ).count()
            
            shipping_records = ShippingData.query.filter(
                ShippingData.date >= month_start,
                ShippingData.date <= month_end
            ).all()
            
            ok_count = 0
            ng_count = 0
            
            for r in shipping_records:
                key = (r.material, r.spec, r.vendor_id)
                if key not in tolerance_cache:
                    res = ToleranceService.check_tolerance({
                        'material': r.material,
                        'spec': r.spec,
                        'vendor_id': r.vendor_id
                    })
                    if res.get('found'):
                        tolerance_cache[key] = res.get('tolerances', [])
                    else:
                        tolerance_cache[key] = []
                
                tolerances = tolerance_cache[key]
                if tolerances and check_shipping_violation(r, tolerances):
                    ng_count += 1
                else:
                    ok_count += 1
            
            rework_count = ReworkRequest.query.filter(
                ReworkRequest.created_at >= month_start,
                ReworkRequest.created_at <= month_end
            ).count()
            
            month_label = month_start.strftime("%Y-%m")
            trends["ncmr_by_month"].append({
                "month": month_label,
                "count": ncmr_count
            })
            trends["shipping_ok_by_month"].append({
                "month": month_label,
                "count": ok_count
            })
            trends["shipping_ng_by_month"].append({
                "month": month_label,
                "count": ng_count
            })
            trends["rework_by_month"].append({
                "month": month_label,
                "count": rework_count
            })
        
        return jsonify(trends)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/inspectors')
def get_inspectors():
    inspectors = Inspector.query.all()
    # ORM objects needs to be serialized manually or use marshmallows later
    return jsonify([{"id": i.id, "name": i.name.strip() if i.name else ""} for i in inspectors])

@admin_bp.route('/api/vendors')
def get_vendors():
    vendors = Vendor.query.all()
    return jsonify([{"id": v.id, "name": v.name.strip() if v.name else ""} for v in vendors])

@admin_bp.route('/api/machines')
def get_machines():
    machines = Machine.query.all()
    return jsonify([{"id": m.id, "name": m.name.strip() if m.name else ""} for m in machines])

@admin_bp.route('/api/operators')
def get_operators():
    operators = Operator.query.all()
    return jsonify([{"id": o.id, "name": o.name.strip() if o.name else ""} for o in operators])

@admin_bp.route('/api/materials')
def get_materials():
    # Temporary raw SQL until ShippingData model is created
    result = db.session.execute(text('SELECT DISTINCT "材質" FROM "出貨檢驗數據" WHERE "材質" IS NOT NULL'))
    materials = [row[0].strip() for row in result]
    return jsonify(materials)

@admin_bp.route('/api/specs')
def get_specs():
    # Temporary raw SQL until ShippingData model is created
    result = db.session.execute(text('SELECT DISTINCT "檢驗規格" FROM "出貨檢驗數據" WHERE "檢驗規格" IS NOT NULL'))
    specs = [row[0].strip() for row in result]
    return jsonify(specs)
