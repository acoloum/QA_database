
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import or_, text
from sqlalchemy.orm import contains_eager, joinedload
from scipy import stats as scipy_stats
from ..extensions import db
from ..models import ShippingData, ShippingMeasurement, Inspector, Vendor, VendorToleranceMain, VendorToleranceDetail
from ..utils import (
    format_value,
    validate_inspection_data,
    handle_db_error,
    parse_spec_nominals
)

from .spc_constants import SPC_CONSTANTS


class ShippingService:
    @staticmethod
    def _map_row_to_dict(item: ShippingData) -> Dict[str, Any]:
        """Helper to map ShippingData model to the legacy dictionary format with Chinese keys"""
        inspector_name = item.inspector.name if item.inspector else ""
        vendor_name = item.vendor.name if item.vendor else ""
        
        # Handle date formatting
        date_str = item.date.strftime('%Y-%m-%d') if item.date else ""

        res = {
            "識別碼": item.id,
            "檢驗日期": date_str,
            "材質": format_value(item.material),
            "檢驗規格": format_value(item.spec),
            "訂單號碼": format_value(item.order_num),
            "檢驗人員": inspector_name.strip(),
            "廠商中文名稱": vendor_name.strip(), # legacy key
            "廠商名稱": vendor_name.strip(),      # legacy key
            "組數": item.group_count or 5
        }

        # Map dynamic columns (groups 1-10)
        for i in range(1, 11):
            # Min/Max items
            res[f"外徑{i}-min"] = format_value(getattr(item, f"od{i}_min"))
            res[f"外徑{i}-max"] = format_value(getattr(item, f"od{i}_max"))
            res[f"內徑{i}-min"] = format_value(getattr(item, f"id{i}_min"))
            res[f"內徑{i}-max"] = format_value(getattr(item, f"id{i}_max"))
            res[f"真圓度{i}"] = format_value(getattr(item, f"roundness{i}"))
            res[f"厚度{i}-min"] = format_value(getattr(item, f"th{i}_min"))
            res[f"厚度{i}-max"] = format_value(getattr(item, f"th{i}_max"))
             
            # Single value items
            res[f"同心度{i}"] = format_value(getattr(item, f"concentricity{i}"))
            res[f"長度{i}"] = format_value(getattr(item, f"length{i}"))
            res[f"硬度{i}"] = format_value(getattr(item, f"hardness{i}"))
            res[f"韋伯氏硬度{i}"] = format_value(getattr(item, f"vickers{i}"))
            res[f"真直度{i}"] = format_value(getattr(item, f"straightness{i}"))

        return res

    @staticmethod
    def _to_dict(rec: ShippingData) -> Dict[str, Any]:
        """將 ShippingData 序列化為巢狀格式，量測值從 ShippingMeasurement 子表讀取"""
        meas_map: Dict[str, Any] = {}
        for m in rec.measurements:
            g = str(m.group_num)
            if g not in meas_map:
                meas_map[g] = {}
            meas_map[g][m.item] = {
                'lower_limit':  float(m.lower_limit)  if m.lower_limit  is not None else None,
                'upper_limit':  float(m.upper_limit)  if m.upper_limit  is not None else None,
                'value_min':    float(m.value_min)    if m.value_min    is not None else None,
                'value_max':    float(m.value_max)    if m.value_max    is not None else None,
                'value_single': float(m.value_single) if m.value_single is not None else None,
                'is_ng':        m.is_ng,
            }

        return {
            'id':             rec.id,
            'date':           rec.date.isoformat() if rec.date else None,
            'material':       rec.material,
            'spec':           rec.spec,
            'order_num':      rec.order_num,
            'group_count':    rec.group_count,
            'inspector_id':   rec.inspector_id,
            'inspector_name': rec.inspector.name if rec.inspector else None,
            'vendor_id':      rec.vendor_id,
            'vendor_name':    rec.vendor.name if rec.vendor else None,
            'is_ng':          rec.is_ng,
            'measurements':   meas_map,
        }

    @staticmethod
    def create(data: Dict[str, Any]) -> Dict[str, Any]:
        """新增出貨檢驗主檔及量測明細（使用 ShippingMeasurement 子表）"""
        inspector = Inspector.query.filter_by(name=data.get('inspector_name')).first()
        if not inspector:
            raise ValueError(f"找不到檢驗人員: {data.get('inspector_name')}")

        vendor = Vendor.query.filter_by(name=data.get('vendor_name')).first()
        if not vendor:
            raise ValueError(f"找不到廠商: {data.get('vendor_name')}")

        try:
            rec = ShippingData(
                date=data.get('date'),
                inspector_id=inspector.id,
                vendor_id=vendor.id,
                spec=data.get('spec'),
                material=data.get('material'),
                order_num=data.get('order_num'),
                group_count=int(data.get('group_count', 5)),
            )
            db.session.add(rec)
            db.session.flush()  # 取得 rec.id

            any_ng = False
            for g_str, items in (data.get('measurements') or {}).items():
                for item_name, vals in items.items():
                    lower    = vals.get('lower_limit')
                    upper    = vals.get('upper_limit')
                    v_min    = vals.get('value_min')
                    v_max    = vals.get('value_max')
                    v_single = vals.get('value_single')

                    item_ng = False
                    if lower is not None and upper is not None:
                        for v in filter(lambda x: x is not None, [v_min, v_max, v_single]):
                            if float(v) < float(lower) or float(v) > float(upper):
                                item_ng = True
                    if item_ng:
                        any_ng = True

                    db.session.add(ShippingMeasurement(
                        shipping_id=rec.id,
                        group_num=int(g_str),
                        item=item_name,
                        lower_limit=lower,
                        upper_limit=upper,
                        value_min=v_min,
                        value_max=v_max,
                        value_single=v_single,
                        is_ng=item_ng,
                    ))

            rec.is_ng = any_ng
            db.session.commit()
            db.session.refresh(rec)
            return ShippingService._to_dict(rec)
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update(record_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新出貨檢驗主檔；若 data 含 measurements 則刪除舊明細並重建"""
        rec = db.session.get(ShippingData, record_id)
        if not rec:
            raise ValueError(f"找不到 ID {record_id} 的資料")

        try:
            # 更新基本欄位（有提供才覆蓋）
            if 'date' in data:
                rec.date = data['date']
            if 'material' in data:
                rec.material = data['material']
            if 'spec' in data:
                rec.spec = data['spec']
            if 'order_num' in data:
                rec.order_num = data['order_num']
            if 'group_count' in data:
                rec.group_count = int(data['group_count'])
            if 'inspector_name' in data:
                inspector = Inspector.query.filter_by(name=data['inspector_name']).first()
                if not inspector:
                    raise ValueError(f"找不到檢驗人員: {data['inspector_name']}")
                rec.inspector_id = inspector.id
            if 'vendor_name' in data:
                vendor = Vendor.query.filter_by(name=data['vendor_name']).first()
                if not vendor:
                    raise ValueError(f"找不到廠商: {data['vendor_name']}")
                rec.vendor_id = vendor.id

            if 'measurements' in data:
                # 刪除舊量測明細再重建
                ShippingMeasurement.query.filter_by(shipping_id=rec.id).delete()

                any_ng = False
                for g_str, items in (data.get('measurements') or {}).items():
                    for item_name, vals in items.items():
                        lower    = vals.get('lower_limit')
                        upper    = vals.get('upper_limit')
                        v_min    = vals.get('value_min')
                        v_max    = vals.get('value_max')
                        v_single = vals.get('value_single')

                        item_ng = False
                        if lower is not None and upper is not None:
                            for v in filter(lambda x: x is not None, [v_min, v_max, v_single]):
                                if float(v) < float(lower) or float(v) > float(upper):
                                    item_ng = True
                        if item_ng:
                            any_ng = True

                        db.session.add(ShippingMeasurement(
                            shipping_id=rec.id,
                            group_num=int(g_str),
                            item=item_name,
                            lower_limit=lower,
                            upper_limit=upper,
                            value_min=v_min,
                            value_max=v_max,
                            value_single=v_single,
                            is_ng=item_ng,
                        ))

                rec.is_ng = any_ng

            db.session.commit()
            db.session.refresh(rec)
            return ShippingService._to_dict(rec)
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_list(args: Dict[str, Any]) -> Dict[str, Any]:
        """獲取出貨檢驗數據列表"""
        try:
            query = ShippingData.query

            # Joins for filtering/display
            query = query.outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)
            query = query.outerjoin(Inspector, ShippingData.inspector_id == Inspector.id)

            # Use contains_eager to reuse the JOINs above for eager loading
            query = query.options(
                contains_eager(ShippingData.inspector),
                contains_eager(ShippingData.vendor),
                joinedload(ShippingData.measurements),
            )

            if args.get('id'):
                query = query.filter(ShippingData.id == args['id'])
            else:
                if args.get('vendor'):   query = query.filter(Vendor.name.like(f"%{args['vendor']}%"))
                if args.get('material'): query = query.filter(ShippingData.material.like(f"%{args['material']}%"))
                if args.get('spec'):     query = query.filter(ShippingData.spec.like(f"%{args['spec']}%"))
                if args.get('start_date'): query = query.filter(ShippingData.date >= args['start_date'])
                if args.get('end_date'):   query = query.filter(ShippingData.date <= args['end_date'])

            query = query.order_by(ShippingData.id.desc())

            # Pagination
            page = int(args.get('page', 1))
            per_page = 10
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)

            all_data = [ShippingService._map_row_to_dict(item) for item in pagination.items]
            
            return {
                "data": all_data,
                "total": pagination.total,
                "total_pages": pagination.pages
            }
        except Exception as e:
            raise e

    @staticmethod
    def get_by_id(data_id: int) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取單筆出貨檢驗資料"""
        try:
            item = db.session.get(ShippingData, data_id)
            if not item:
                return None
            return ShippingService._map_row_to_dict(item)
        except Exception as e:
            raise e

    @staticmethod
    def get_stats(args: Dict[str, Any]) -> Dict[str, Any]:
        """獲取出貨檢驗的 SPC 統計數據（含公差界限）"""
        field = args.get('field', '外徑') # Example: "外徑"
        vendor = args.get('vendor')
        material = args.get('material')
        spec = args.get('spec')
        start_date = args.get('start_date')
        end_date = args.get('end_date')

        # ── SPCCache 快取讀取 ──────────────────────────────────────────────
        from datetime import timedelta
        from ..models import SPCCache

        _cache_key = (
            f"spc|{field}|{vendor or ''}|{material or ''}|"
            f"{spec or ''}|{start_date or ''}|{end_date or ''}"
        )
        try:
            _cached = SPCCache.query.filter_by(cache_key=_cache_key).first()
            if _cached and _cached.expires_at > datetime.utcnow():
                return _cached.result
        except Exception:
            # 快取讀取失敗不阻斷主流程
            _cached = None
        # ───────────────────────────────────────────────────────────────────

        try:
            # 1. Tolerance Lookup — reuse the same logic as the form
            from ..services.tolerance_service import ToleranceService
            tolerance_limits = {"USL": None, "LSL": None, "found": False}
            if material:
                # Resolve vendor_id from name for tolerance matching
                vendor_id = None
                if vendor:
                    v = Vendor.query.filter(Vendor.name.like(f"%{vendor}%")).first()
                    if v:
                        vendor_id = v.id

                tol_result = ToleranceService.check_tolerance({
                    'material': material,
                    'spec': spec or '',
                    'vendor_id': str(vendor_id) if vendor_id else ''
                })


                if tol_result.get('found'):
                    tolerance_limits["found"] = True
                    # Parse nominal values from spec (e.g. '31.9*2.2*589' → 外徑=31.9)
                    nominal_from_spec = {}
                    if spec:
                        s = str(spec).strip().replace('×', '*').replace('x', '*').replace('X', '*')
                        while '**' in s: s = s.replace('**', '*')
                        parts = s.split('*')
                        try:
                            nums = [float(p.strip()) for p in parts if p.strip()]
                            if len(nums) >= 2:
                                nominal_from_spec['外徑'] = nums[0]
                                val2 = nums[1]
                                if val2 < (nums[0] / 2):
                                    nominal_from_spec['厚度'] = val2
                                    nominal_from_spec['內徑'] = nums[0] - (val2 * 2)
                                else:
                                    nominal_from_spec['內徑'] = val2
                                    nominal_from_spec['厚度'] = (nums[0] - val2) / 2
                                if len(nums) >= 3:
                                    nominal_from_spec['長度'] = nums[2]
                            elif len(nums) == 1:
                                nominal_from_spec['外徑'] = nums[0]
                        except (ValueError, TypeError):
                            pass

                    # 欄位別名：公差明細可能用不同名稱儲存同一量測項目
                    FIELD_ALIASES = {
                        '硬度': {'硬度', '洛氏硬度'},
                        '韋伯氏硬度': {'韋伯氏硬度', '維氏硬度'},
                    }
                    field_match_set = FIELD_ALIASES.get(field, {field})

                    # Find the matching detail for the current field
                    for t in tol_result.get('tolerances', []):
                        if t.get('項目') in field_match_set:

                            tolerance_limits["公差下限"] = t.get('公差下限')
                            tolerance_limits["公差上限"] = t.get('公差上限')
                            tolerance_limits["尺寸下限"] = t.get('尺寸下限')
                            tolerance_limits["尺寸上限"] = t.get('尺寸上限')

                            dim_min = t.get('尺寸下限')
                            dim_max = t.get('尺寸上限')
                            if dim_min is not None and dim_max is not None:
                                tolerance_limits["LSL"] = dim_min
                                tolerance_limits["USL"] = dim_max
                            elif dim_min is None and dim_max is not None:
                                # 單側上限尺寸規格（同心度、真圓度等），下限視為 0
                                tolerance_limits["LSL"] = 0
                                tolerance_limits["USL"] = dim_max
                            elif dim_min is not None and dim_max is None:
                                # 單側下限規格（硬度等），記錄 LSL，USL 留空
                                # Cp/Cpk 需雙側才能計算，此情形 available 不開啟
                                tolerance_limits["LSL"] = dim_min
                                tolerance_limits["one_sided"] = "lower"
                            else:
                                tol_min = t.get('公差下限')
                                tol_max = t.get('公差上限')
                                # Try std_val first, then fall back to nominal from spec
                                std = t.get('標準值')
                                if std is None and field in nominal_from_spec:
                                    std = nominal_from_spec[field]
                                if tol_min is not None and tol_max is not None and std is not None:
                                    tolerance_limits["LSL"] = std - abs(tol_min)
                                    tolerance_limits["USL"] = std + abs(tol_max)
                                elif tol_min is None and tol_max is not None:
                                    # 單側上限規格（同心度、真圓度、真直度等不可為負的項目）
                                    # LSL 視為 0，USL 為公差上限絕對值
                                    tolerance_limits["LSL"] = 0
                                    tolerance_limits["USL"] = abs(tol_max)
                            break

            # 2. Data Query (ORM)
            # Map field name to model attribute prefix
            field_map = {
                '外徑': 'od',
                '內徑': 'id', # id{i}_min
                '厚度': 'th',
                '同心度': 'concentricity',
                '長度': 'length',
                '硬度': 'hardness',
                '韋伯氏硬度': 'vickers',
                '真直度': 'straightness',
                '真圓度': 'roundness'
            }
            attr_prefix = field_map.get(field)
            if not attr_prefix:
                return {"labels": [], "avgs": [], "ranges": []}

            is_minmax = field in ['外徑', '內徑', '厚度']

            # Dynamic query selection
            # Select ID, Date, OrderNum, GroupCount, and the relevant 10 groups columns
            entities = [ShippingData.id, ShippingData.date, ShippingData.order_num, ShippingData.group_count]
            for i in range(1, 11):
                if is_minmax:
                    entities.append(getattr(ShippingData, f"{attr_prefix}{i}_min"))
                    entities.append(getattr(ShippingData, f"{attr_prefix}{i}_max"))
                else:
                    entities.append(getattr(ShippingData, f"{attr_prefix}{i}"))

            query = db.session.query(*entities).outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)

            if vendor:   query = query.filter(Vendor.name.like(f"%{vendor}%"))
            if material: query = query.filter(ShippingData.material.like(f"%{material}%"))
            if spec:     query = query.filter(ShippingData.spec.like(f"%{spec}%"))
            if start_date: query = query.filter(ShippingData.date >= start_date)
            if end_date:   query = query.filter(ShippingData.date <= end_date)
            
            query = query.order_by(ShippingData.date.asc())
            
            rows = query.all() # These are tuples now

            if not rows:
                return {"labels": [], "avgs": [], "ranges": [], "x_cl":0, "x_ucl":0, "x_lcl":0, "r_cl":0, "r_ucl":0}

            # Processing Logic (Same as before but accessing tuple indices)
            # Tuple structure:
            # 0: id, 1: date, 2: order_num, 3: group_count
            # 4...: measurements
            
            avgs = []
            ranges = []
            subgroup_sizes = []  # Track actual subgroup size per row
            all_values = []  # All individual measurements for histogram
            ids_valid = []
            dates_valid = []
            labels_valid = []
            insufficient_data = []

            for idx, r in enumerate(rows):
                vals: List[float] = []
                valid_groups = 0
                row_group_count = r[3] or 5  # group_count, default 5
                
                current_col_idx = 4
                
                for i in range(1, 11):
                    try:
                        if is_minmax:
                            v1_str = r[current_col_idx]
                            v2_str = r[current_col_idx+1]
                            current_col_idx += 2
                            
                            # Only process groups within the record's group_count
                            if i <= row_group_count and v1_str and v2_str:
                                v1 = float(v1_str)
                                v2 = float(v2_str)
                                val = (v1 + v2) / 2
                                vals.append(val)
                                all_values.extend([v1, v2])
                                valid_groups += 1
                        else:
                            v_str = r[current_col_idx]
                            current_col_idx += 1
                            # Only process groups within the record's group_count
                            if i <= row_group_count and v_str:
                                v = float(v_str)
                                vals.append(v)
                                all_values.append(v)
                                valid_groups += 1
                    except (ValueError, TypeError):
                         pass

                original_idx = len(rows) - 1 - idx
                
                if valid_groups >= 2 and vals:
                    vals_np = np.array(vals, dtype=float)
                    avgs.append(float(np.mean(vals_np)))
                    ranges.append(float(np.ptp(vals_np)))
                    subgroup_sizes.append(valid_groups)
                    ids_valid.append(str(r[0]))
                    d_val = r[1]
                    d_str = d_val.strftime('%Y-%m-%d') if hasattr(d_val, 'strftime') else str(d_val) if d_val else ''
                    dates_valid.append(d_str)
                    
                    label_val = r[2]
                    labels_valid.append(str(label_val) if label_val else str(r[0]))
                else:
                    insufficient_data.append({
                         "id": str(r[0]),
                         "date": str(r[1]) if r[1] else '',
                         "valid_groups": valid_groups,
                         "original_idx": original_idx
                    })

            # Control Limit Calculation with dynamic subgroup-size constants
            BASELINE_COUNT = 25
            if len(avgs) >= 5:
                baseline_count = min(BASELINE_COUNT, len(avgs))
                base_avgs = avgs[:baseline_count]
                base_ranges = ranges[:baseline_count]
                base_ns = subgroup_sizes[:baseline_count]

                # Use average subgroup size to look up constants
                avg_n = round(float(np.mean(base_ns)))
                avg_n = max(2, min(10, avg_n))  # Clamp to table range
                A2, D3, D4, d2 = SPC_CONSTANTS[avg_n]

                x_cl = float(np.mean(base_avgs))
                r_cl = float(np.mean(base_ranges))
                x_ucl = x_cl + A2 * r_cl
                x_lcl = x_cl - A2 * r_cl
                r_ucl = D4 * r_cl
                r_lcl = D3 * r_cl
                x_lcl = max(x_lcl, 0)
            else:
                x_cl = x_ucl = x_lcl = r_cl = r_ucl = r_lcl = 0.0
                d2 = 2.326
                avg_n = 5
                baseline_count = 0

            # --- Process Capability Indices (Cp/Cpk/Pp/Ppk) ---
            process_capability = {"available": False, "reason": "no_tolerance"}
            usl = tolerance_limits.get("USL")
            lsl = tolerance_limits.get("LSL")

            if usl is not None and lsl is not None and len(avgs) < 5:
                process_capability["reason"] = "insufficient_data"
                process_capability["valid_count"] = len(avgs)

            # 單側下限規格（如硬度）：計算 CPL / PPL
            if tolerance_limits.get("one_sided") == "lower" and lsl is not None and len(avgs) >= 5:
                x_bar = float(np.mean(avgs))
                sigma_within = r_cl / d2 if r_cl > 0 else 0
                sigma_overall = float(np.std(all_values, ddof=1)) if len(all_values) >= 2 else 0
                process_capability["available"] = True
                process_capability["one_sided"] = "lower"
                process_capability["lsl"] = float(lsl)
                process_capability["usl"] = None
                if sigma_within > 0:
                    cpl = (x_bar - float(lsl)) / (3 * sigma_within)
                    process_capability.update({"cp": None, "cpk": round(cpl, 3), "cpu": None, "cpl": round(cpl, 3)})
                else:
                    process_capability.update({"cp": None, "cpk": None, "cpu": None, "cpl": None})
                if sigma_overall > 0:
                    ppl = (x_bar - float(lsl)) / (3 * sigma_overall)
                    process_capability.update({"pp": None, "ppk": round(ppl, 3), "ppu": None, "ppl": round(ppl, 3)})
                else:
                    process_capability.update({"pp": None, "ppk": None, "ppu": None, "ppl": None})
                process_capability["sigma_within"] = round(sigma_within, 6)
                process_capability["sigma_overall"] = round(sigma_overall, 6)

            if usl is not None and lsl is not None and len(avgs) >= 5:
                x_bar = float(np.mean(avgs))
                # Within-group sigma: estimated from R-bar / d2 (dynamic)
                sigma_within = r_cl / d2 if r_cl > 0 else 0

                # Overall sigma: standard deviation of all individual values
                if len(all_values) >= 2:
                    sigma_overall = float(np.std(all_values, ddof=1))
                else:
                    sigma_overall = 0

                process_capability["available"] = True
                process_capability["usl"] = float(usl)
                process_capability["lsl"] = float(lsl)

                if sigma_within > 0:
                    cp = (float(usl) - float(lsl)) / (6 * sigma_within)
                    cpu = (float(usl) - x_bar) / (3 * sigma_within)
                    cpl = (x_bar - float(lsl)) / (3 * sigma_within)
                    cpk = min(cpu, cpl)
                    process_capability.update({"cp": round(cp, 3), "cpk": round(cpk, 3),
                                               "cpu": round(cpu, 3), "cpl": round(cpl, 3)})
                else:
                    process_capability.update({"cp": None, "cpk": None, "cpu": None, "cpl": None})

                if sigma_overall > 0:
                    pp = (float(usl) - float(lsl)) / (6 * sigma_overall)
                    ppu = (float(usl) - x_bar) / (3 * sigma_overall)
                    ppl = (x_bar - float(lsl)) / (3 * sigma_overall)
                    ppk = min(ppu, ppl)
                    process_capability.update({"pp": round(pp, 3), "ppk": round(ppk, 3),
                                               "ppu": round(ppu, 3), "ppl": round(ppl, 3)})
                else:
                    process_capability.update({"pp": None, "ppk": None, "ppu": None, "ppl": None})

                process_capability["sigma_within"] = round(sigma_within, 6)
                process_capability["sigma_overall"] = round(sigma_overall, 6)

                # --- PPM estimation (normal distribution assumption) ---
                if sigma_overall > 0:
                    z_upper = (float(usl) - x_bar) / sigma_overall
                    z_lower = (x_bar - float(lsl)) / sigma_overall
                    ppm_upper = round(float(scipy_stats.norm.sf(z_upper) * 1_000_000), 1)
                    ppm_lower = round(float(scipy_stats.norm.sf(z_lower) * 1_000_000), 1)
                    ppm_total = round(ppm_upper + ppm_lower, 1)
                    process_capability["ppm"] = {"upper": ppm_upper, "lower": ppm_lower, "total": ppm_total}
                else:
                    process_capability["ppm"] = {"upper": 0, "lower": 0, "total": 0}

            # --- Skewness & Kurtosis ---
            distribution_stats = {}
            if len(all_values) >= 4:
                arr = np.array(all_values, dtype=float)
                distribution_stats["skewness"] = round(float(scipy_stats.skew(arr)), 3)
                distribution_stats["kurtosis"] = round(float(scipy_stats.kurtosis(arr)), 3)
                # Normality assessment
                sk = abs(distribution_stats["skewness"])
                ku = abs(distribution_stats["kurtosis"])
                if sk < 0.5 and ku < 1.0:
                    distribution_stats["normality"] = "good"
                    distribution_stats["normality_label"] = "分佈接近常態"
                elif sk < 1.0 and ku < 2.0:
                    distribution_stats["normality"] = "moderate"
                    distribution_stats["normality_label"] = "分佈略偏，Cpk 僅供參考"
                else:
                    distribution_stats["normality"] = "poor"
                    distribution_stats["normality_label"] = "分佈明顯非常態，Cpk 可能不準確"

            # --- Monthly Cpk Trend ---
            cpk_trend = []
            if usl is not None and lsl is not None and len(avgs) >= 5:
                # Group data by month
                monthly_data = defaultdict(list)
                for i, date_str in enumerate(dates_valid):
                    if date_str:
                        month_key = date_str[:7]  # 'YYYY-MM'
                        monthly_data[month_key].append(all_values[i] if i < len(all_values) else avgs[i])

                # Collect individual values by month more accurately
                monthly_values = defaultdict(list)
                val_idx = 0
                for i in range(len(avgs)):
                    month_key = dates_valid[i][:7] if dates_valid[i] else 'unknown'
                    n_vals = subgroup_sizes[i] if i < len(subgroup_sizes) else 5
                    if is_minmax:
                        n_raw = n_vals * 2  # Each group has min+max
                    else:
                        n_raw = n_vals
                    for j in range(n_raw):
                        if val_idx < len(all_values):
                            monthly_values[month_key].append(all_values[val_idx])
                            val_idx += 1

                for month_key in sorted(monthly_values.keys()):
                    vals = monthly_values[month_key]
                    if len(vals) >= 5:
                        m_mean = float(np.mean(vals))
                        m_std = float(np.std(vals, ddof=1))
                        if m_std > 0:
                            m_cpu = (float(usl) - m_mean) / (3 * m_std)
                            m_cpl = (m_mean - float(lsl)) / (3 * m_std)
                            m_cpk = round(min(m_cpu, m_cpl), 3)
                            cpk_trend.append({"month": month_key, "cpk": m_cpk, "count": len(vals)})

            _result = {
                "labels": labels_valid,
                "ids": ids_valid,
                "dates": dates_valid,
                "avgs": avgs,
                "ranges": ranges,
                "subgroup_sizes": subgroup_sizes,
                "all_values": [round(v, 4) for v in all_values],
                "x_cl": x_cl,
                "x_ucl": x_ucl,
                "x_lcl": x_lcl,
                "r_cl": r_cl,
                "r_ucl": r_ucl,
                "r_lcl": r_lcl,
                "avg_subgroup_size": avg_n if len(avgs) >= 5 else 5,
                "baseline_count": baseline_count,
                "insufficient_data": insufficient_data,
                "total_rows": len(rows),
                "valid_count": len(avgs),
                "tolerance": tolerance_limits,
                "process_capability": process_capability,
                "distribution_stats": distribution_stats,
                "cpk_trend": cpk_trend
            }

            # ── SPCCache 快取寫入（1 小時過期）─────────────────────────────
            try:
                _now = datetime.utcnow()
                _expires = _now + timedelta(hours=1)
                if _cached:
                    _cached.result = _result
                    _cached.created_at = _now
                    _cached.expires_at = _expires
                else:
                    db.session.add(SPCCache(
                        cache_key=_cache_key,
                        result=_result,
                        expires_at=_expires,
                    ))
                db.session.commit()
            except Exception:
                # 快取寫入失敗不影響回傳結果
                db.session.rollback()
            # ───────────────────────────────────────────────────────────────

            return _result
        except Exception as e:
            raise e

    @staticmethod
    def save_data(data: Dict[str, Any], is_update: bool = False) -> bool:
        """新增或更新出貨檢驗資料"""
        errors = validate_inspection_data(data)
        if errors:
            raise ValueError(", ".join(errors))

        try:
            # Lookups
            inspector = Inspector.query.filter_by(name=data.get('檢驗人員姓名')).first()
            if not inspector:
                raise ValueError(f"找不到檢驗人員: {data.get('檢驗人員姓名')}")

            vendor = Vendor.query.filter_by(name=data.get('廠商中文名稱')).first()
            if not vendor:
                raise ValueError(f"找不到廠商: {data.get('廠商中文名稱')}")

            if is_update:
                record_id = data.get('識別碼')
                shipping_data = db.session.get(ShippingData, record_id)
                if not shipping_data:
                    raise ValueError(f"找不到 ID {record_id} 的資料")
            else:
                shipping_data = ShippingData()

            # Set basic fields
            shipping_data.date = data.get('檢驗日期')
            shipping_data.inspector_id = inspector.id
            shipping_data.vendor_id = vendor.id
            shipping_data.spec = data.get('檢驗規格')
            shipping_data.material = data.get('材質')
            shipping_data.order_num = data.get('訂單號碼')
            shipping_data.group_count = int(data.get('組數', 5))

            # Set dynamic columns (groups 1-10)
            def get_val(k):
                val = data.get(k)
                if val is None or val == "":
                    return None
                return str(val)

            for i in range(1, 11):
                setattr(shipping_data, f"od{i}_min", get_val(f'外徑{i}-min'))
                setattr(shipping_data, f"od{i}_max", get_val(f'外徑{i}-max'))
                setattr(shipping_data, f"id{i}_min", get_val(f'內徑{i}-min'))
                setattr(shipping_data, f"id{i}_max", get_val(f'內徑{i}-max'))
                setattr(shipping_data, f"th{i}_min", get_val(f'厚度{i}-min'))
                setattr(shipping_data, f"th{i}_max", get_val(f'厚度{i}-max'))
                
                setattr(shipping_data, f"concentricity{i}", get_val(f'同心度{i}'))
                setattr(shipping_data, f"length{i}", get_val(f'長度{i}'))
                setattr(shipping_data, f"hardness{i}", get_val(f'硬度{i}'))
                setattr(shipping_data, f"vickers{i}", get_val(f'韋伯氏硬度{i}'))
                setattr(shipping_data, f"straightness{i}", get_val(f'真直度{i}'))
                setattr(shipping_data, f"roundness{i}", get_val(f'真圓度{i}'))

            # Compute is_ng
            from .tolerance_service import ToleranceService
            tol_res = ToleranceService.check_tolerance({
                'material': shipping_data.material,
                'spec': shipping_data.spec,
                'vendor_id': shipping_data.vendor_id
            })
            if tol_res.get('found'):
                shipping_data.is_ng = shipping_data.compute_is_ng(tol_res.get('tolerances', []))
            else:
                shipping_data.is_ng = False

            if not is_update:
                db.session.add(shipping_data)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_data(record_id: int) -> bool:
        """刪除出貨檢驗資料"""
        try:
            item = db.session.get(ShippingData, record_id)
            if item:
                db.session.delete(item)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def import_data(file: Any) -> int:
        """匯入 Excel 資料"""
        try:
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"檔案讀取失敗: {str(e)}")

        success_count = 0
        try:
            for row_num, row in enumerate(df.iterrows()):
                main_data = row[1].to_dict()
                
                # Cleanup NaNs
                for k, v in main_data.items():
                    if pd.isna(v): main_data[k] = None

                display_row_num = row_num + 2

                # Lookups
                inspector_name = str(main_data.get('檢驗人員', '')).strip()
                inspector = Inspector.query.filter_by(name=inspector_name).first()
                if not inspector and inspector_name:
                    # Optional: detailed error with list of available inspectors
                    raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'")
                
                vendor_name = str(main_data.get('廠商名稱', '')).strip()
                vendor = Vendor.query.filter_by(name=vendor_name).first()
                
                if not inspector or not vendor:
                    # Legacy behavior raised error if missing
                     if not inspector: raise ValueError(f"第 {display_row_num} 行: 檢驗人員不存在")
                     if not vendor: raise ValueError(f"第 {display_row_num} 行: 廠商不存在")

                # Determine group count from data (default 5)
                gc_val = main_data.get('組數')
                group_count_val = int(gc_val) if gc_val and not pd.isna(gc_val) else 5

                shipping_data = ShippingData(
                    date=main_data.get('檢驗日期'),
                    inspector_id=inspector.id,
                    vendor_id=vendor.id,
                    spec=main_data.get('檢驗規格'),
                    material=main_data.get('材質'),
                    order_num=main_data.get('訂單號碼'),
                    group_count=group_count_val
                )

                # Map columns
                def get_val(k):
                    val = main_data.get(k)
                    if pd.isna(val) or val is None or str(val).strip() == "":
                        return None
                    return str(val)
                
                for i in range(1, 11):
                    setattr(shipping_data, f"od{i}_min", get_val(f'外徑{i}-min'))
                    setattr(shipping_data, f"od{i}_max", get_val(f'外徑{i}-max'))
                    setattr(shipping_data, f"id{i}_min", get_val(f'內徑{i}-min'))
                    setattr(shipping_data, f"id{i}_max", get_val(f'內徑{i}-max'))
                    setattr(shipping_data, f"th{i}_min", get_val(f'厚度{i}-min'))
                    setattr(shipping_data, f"th{i}_max", get_val(f'厚度{i}-max'))
                    
                    setattr(shipping_data, f"concentricity{i}", get_val(f'同心度{i}'))
                    setattr(shipping_data, f"length{i}", get_val(f'長度{i}'))
                    setattr(shipping_data, f"hardness{i}", get_val(f'硬度{i}'))
                    setattr(shipping_data, f"straightness{i}", get_val(f'真直度{i}'))
                    setattr(shipping_data, f"roundness{i}", get_val(f'真圓度{i}'))

                from .tolerance_service import ToleranceService
                tol_res = ToleranceService.check_tolerance({
                    'material': shipping_data.material,
                    'spec': shipping_data.spec,
                    'vendor_id': shipping_data.vendor_id
                })
                if tol_res.get('found'):
                    shipping_data.is_ng = shipping_data.compute_is_ng(tol_res.get('tolerances', []))
                else:
                    shipping_data.is_ng = False

                db.session.add(shipping_data)
                success_count += 1
            
            db.session.commit()
            return success_count
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def export_excel(args: Dict[str, Any]) -> BytesIO:
        """匯出 Excel"""
        try:
            query = ShippingData.query.outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)
            
            if args.get('vendor'):   query = query.filter(Vendor.name.like(f"%{args['vendor']}%"))
            if args.get('material'): query = query.filter(ShippingData.material.like(f"%{args['material']}%"))
            if args.get('spec'):     query = query.filter(ShippingData.spec.like(f"%{args['spec']}%"))
            if args.get('start_date'): query = query.filter(ShippingData.date >= args['start_date'])
            if args.get('end_date'):   query = query.filter(ShippingData.date <= args['end_date'])

            query = query.order_by(ShippingData.date.asc())
            
            items = query.all()
            
            if not items:
                # Empty DF with columns
                cols = ['識別碼', '檢驗日期', '材質', '檢驗規格', '訂單號碼', '檢驗人員', '廠商名稱', '組數']
                for i in range(1, 11):
                    cols.extend([f'外徑{i}-最小', f'外徑{i}-最大', f'內徑{i}-最小', f'內徑{i}-最大', f'真圓度{i}', f'厚度{i}-最小', f'厚度{i}-最大'])
                    cols.extend([f'同心度{i}', f'長度{i}', f'硬度{i}', f'真直度{i}'])
                df = pd.DataFrame(columns=cols)
            else:
                export_data = []
                for item in items:
                    row = ShippingService._map_row_to_dict(item)
                    # Convert keys to export headers (Legacy export used '最小'/'最大', dict uses 'min'/'max')
                    export_row = {
                        '識別碼': row['識別碼'],
                        '檢驗日期': row['檢驗日期'],
                        '材質': row['材質'],
                        '檢驗規格': row['檢驗規格'],
                        '訂單號碼': row['訂單號碼'],
                        '檢驗人員': row['檢驗人員'],
                        '廠商名稱': row['廠商中文名稱'],
                        '組數': row.get('組數', 5)
                    }
                    for i in range(1, 11):
                        export_row[f'外徑{i}-最小'] = row.get(f'外徑{i}-min', '')
                        export_row[f'外徑{i}-最大'] = row.get(f'外徑{i}-max', '')
                        export_row[f'內徑{i}-最小'] = row.get(f'內徑{i}-min', '')
                        export_row[f'內徑{i}-最大'] = row.get(f'內徑{i}-max', '')
                        export_row[f'真圓度{i}'] = row.get(f'真圓度{i}', '')
                        export_row[f'厚度{i}-最小'] = row.get(f'厚度{i}-min', '')
                        export_row[f'厚度{i}-最大'] = row.get(f'厚度{i}-max', '')
                        export_row[f'同心度{i}'] = row.get(f'同心度{i}', '')
                        export_row[f'長度{i}'] = row.get(f'長度{i}', '')
                        export_row[f'硬度{i}'] = row.get(f'硬度{i}', '')
                        export_row[f'真直度{i}'] = row.get(f'真直度{i}', '')
                    
                    export_data.append(export_row)
                
                df = pd.DataFrame(export_data)

            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return output
        except Exception as e:
            raise e
