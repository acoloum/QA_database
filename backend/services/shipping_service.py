
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import date, datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import or_, text
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from ..extensions import db
from ..models import ShippingData, ShippingMeasurement, Inspector, Vendor, VendorToleranceMain, VendorToleranceDetail, SPCCache
from ..utils import (
    bounded_int,
    format_value,
    validate_inspection_data,
    validate_excel_shape,
    handle_db_error,
    parse_spec_nominals,
    log_audit,
)

from .spc_analysis_service import (
    calculate_control_limits,
    calculate_cpk_trend,
    calculate_distribution_stats,
    calculate_process_capability,
)
from .spc_constants import SPC_CONSTANTS
from .spc_distribution import assess_distribution
from .spc_stability import evaluate_stability
from .shipping_import import build_shipping_measurements_from_row
from .shipping_export import build_shipping_export_columns, build_shipping_export_row
from .shipping_measurement_keys import build_measurement_key, parse_measurement_key

# 形狀公差特性：自然下界為 0，屬單側上限規格（§6.8.2.2、§6.8.1 摺疊分布特性）
SHAPE_UPPER_FIELDS = {"同心度", "真圓度", "真直度"}


class ShippingService:
    @staticmethod
    def _invalidate_spc_cache() -> None:
        """出貨資料異動後清除 SPC 快取，避免統計圖表讀到舊資料。"""
        SPCCache.query.filter(
            or_(
                SPCCache.cache_key.like('spc|%'),
                SPCCache.cache_key.like('spc2|%'),
                SPCCache.cache_key.like('spc2026|shipping|%'),
            )
        ).delete(synchronize_session=False)

    @staticmethod
    def _limits_key_filter(key: Dict[str, str]):
        from ..models import SpcControlLimit
        return SpcControlLimit.query.filter_by(
            source='shipping',
            vendor=key.get('vendor') or '',
            material=key.get('material') or '',
            spec=key.get('spec') or '',
            field=key['field'],
        )

    @staticmethod
    def get_frozen_limits(key: Dict[str, str]) -> Optional[Dict[str, float]]:
        """查詢是否已凍結管制界限（§9.4）；若無則回傳 None。"""
        rec = ShippingService._limits_key_filter(key).first()
        if rec is None:
            return None
        return {
            "x_cl": float(rec.x_cl), "x_ucl": float(rec.x_ucl), "x_lcl": float(rec.x_lcl),
            "r_cl": float(rec.r_cl), "r_ucl": float(rec.r_ucl), "r_lcl": float(rec.r_lcl),
            "avg_n": rec.avg_n, "note": rec.note,
            "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
        }

    @staticmethod
    def freeze_control_limits(key: Dict[str, str], limits: Dict[str, float], note: str = "") -> Dict[str, Any]:
        """凍結目前管制界限（§9.4）：確認後鎖定，避免每次請求都重新計算。"""
        from ..models import SpcControlLimit
        rec = ShippingService._limits_key_filter(key).first()
        if rec is None:
            rec = SpcControlLimit(
                source='shipping',
                vendor=key.get('vendor') or '', material=key.get('material') or '',
                spec=key.get('spec') or '', field=key['field'],
            )
            db.session.add(rec)
        rec.x_cl, rec.x_ucl, rec.x_lcl = limits["x_cl"], limits["x_ucl"], limits["x_lcl"]
        rec.r_cl, rec.r_ucl, rec.r_lcl = limits["r_cl"], limits["r_ucl"], limits.get("r_lcl", 0)
        rec.avg_n = limits.get("avg_n", 5)
        rec.note = note
        db.session.commit()
        ShippingService._invalidate_spc_cache()
        db.session.commit()
        return {"X中心線": float(rec.x_cl), "識別碼": rec.id}

    @staticmethod
    def unfreeze_control_limits(key: Dict[str, str]) -> None:
        """解除管制界限凍結（§9.4）：恢復每次請求自動重新計算。"""
        ShippingService._limits_key_filter(key).delete()
        db.session.commit()
        ShippingService._invalidate_spc_cache()
        db.session.commit()

    @staticmethod
    def _coerce_date(value: Any) -> Any:
        """將前端 JSON 日期字串轉成 date，保留既有 date 物件與空值。"""
        if not value or isinstance(value, date):
            return value
        if isinstance(value, str):
            return datetime.strptime(value, '%Y-%m-%d').date()
        return value

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

        # 量測值一律以巢狀 measurements 提供（供前端編輯載入、列表違規偵測、匯出使用）
        meas_map: Dict[str, Any] = {}
        for m in item.measurements:
            g = str(m.group_num)
            meas_map.setdefault(g, {})[build_measurement_key(m.item, m.position)] = {
                'lower_limit':  float(m.lower_limit)  if m.lower_limit  is not None else None,
                'upper_limit':  float(m.upper_limit)  if m.upper_limit  is not None else None,
                'value_min':    float(m.value_min)    if m.value_min    is not None else None,
                'value_max':    float(m.value_max)    if m.value_max    is not None else None,
                'value_single': float(m.value_single) if m.value_single is not None else None,
                'is_ng':        m.is_ng,
            }
        res["measurements"] = meas_map

        return res

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
                selectinload(ShippingData.measurements),
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
            page = bounded_int(args.get('page'), 1, 1, 1000000)
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
            item = ShippingData.query.options(
                joinedload(ShippingData.inspector),
                joinedload(ShippingData.vendor),
                selectinload(ShippingData.measurements),
            ).filter_by(id=data_id).first()
            if not item:
                return None
            return ShippingService._map_row_to_dict(item)
        except Exception as e:
            raise e

    @staticmethod
    def get_stats(args: Dict[str, Any], skip_frozen_limits: bool = False) -> Dict[str, Any]:
        """使用 2026 共用 SPC 引擎產生即時預覽；舊凍結界限不再覆蓋計算。"""
        from .spc_study_service import SpcStudyService

        return SpcStudyService.preview("shipping", args)

    @staticmethod
    def _get_stats_legacy(args: Dict[str, Any], skip_frozen_limits: bool = False) -> Dict[str, Any]:
        """獲取出貨檢驗的 SPC 統計數據（含公差界限）

        skip_frozen_limits: 內部專用（凍結路由呼叫時使用），略過凍結界限套用，
        確保取得的是依目前資料即時重新計算的數值，不受既有凍結值影響（§9.4：
        重新計算須反映當下資料，而非讀回舊的凍結值）。不對外部 API 參數開放。
        """
        field = args.get('field', '外徑') # Example: "外徑"
        vendor = args.get('vendor')
        material = args.get('material')
        spec = args.get('spec')
        start_date = args.get('start_date')
        end_date = args.get('end_date')

        # ── SPCCache 快取讀取 ──────────────────────────────────────────────
        # 快取鍵未區分 skip_frozen_limits，若在此仍讀寫快取，會與一般查詢互相
        # 污染（skip 呼叫可能讀到一般查詢快取的凍結覆蓋結果，或把未套用凍結
        # 覆蓋的結果寫入快取讓一般查詢誤讀）。skip_frozen_limits=True 一律略
        # 過快取，確保每次都拿到即時重新計算的數值。
        from datetime import timedelta
        from ..models import SPCCache

        _cache_key = (
            f"spc2|{field}|{vendor or ''}|{material or ''}|"
            f"{spec or ''}|{start_date or ''}|{end_date or ''}"
        )
        _cached = None
        if not skip_frozen_limits:
            try:
                _cached = SPCCache.query.filter_by(cache_key=_cache_key).first()
                if _cached and _cached.expires_at > datetime.now(timezone.utc):
                    return _cached.result
            except Exception:
                # 快取讀取失敗不阻斷主流程
                _cached = None
        # ───────────────────────────────────────────────────────────────────

        try:
            # 1. Tolerance Lookup — reuse the same logic as the form
            from ..services.tolerance_service import ToleranceService
            tolerance_limits = {"USL": None, "LSL": None, "found": False}
            char_class = "其他"
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
                    nominal_from_spec = parse_spec_nominals(spec)

                    # 欄位別名：公差明細可能用不同名稱儲存同一量測項目
                    FIELD_ALIASES = {
                        '硬度': {'硬度', '洛氏硬度'},
                        '韋伯氏硬度': {'韋伯氏硬度', '維氏硬度'},
                    }
                    field_match_set = FIELD_ALIASES.get(field, {field})

                    # Find the matching detail for the current field
                    for t in tol_result.get('tolerances', []):
                        if t.get('項目') in field_match_set:
                            char_class = t.get('特性重要度') or "其他"

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
                                # 單側上限尺寸規格（同心度、真圓度等）：自然下界 0
                                tolerance_limits["LSL"] = 0
                                tolerance_limits["USL"] = dim_max
                                if field in SHAPE_UPPER_FIELDS:
                                    tolerance_limits["one_sided"] = "upper"
                            elif dim_min is not None and dim_max is None:
                                tolerance_limits["LSL"] = dim_min
                                tolerance_limits["one_sided"] = "lower"
                            else:
                                tol_min = t.get('公差下限')
                                tol_max = t.get('公差上限')
                                std = t.get('標準值')
                                if std is None and field in nominal_from_spec:
                                    std = nominal_from_spec[field]
                                if tol_min is not None and tol_max is not None and std is not None:
                                    tolerance_limits["LSL"] = std - abs(tol_min)
                                    tolerance_limits["USL"] = std + abs(tol_max)
                                elif tol_min is None and tol_max is not None:
                                    tolerance_limits["LSL"] = 0
                                    tolerance_limits["USL"] = abs(tol_max)
                                    if field in SHAPE_UPPER_FIELDS:
                                        tolerance_limits["one_sided"] = "upper"
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

            # 改讀子表：先取符合條件的記錄（不再取扁平欄位），再批次撈該量測項目的明細
            query = db.session.query(
                ShippingData.id, ShippingData.date, ShippingData.order_num, ShippingData.group_count
            ).outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)

            if vendor:   query = query.filter(Vendor.name.like(f"%{vendor}%"))
            if material: query = query.filter(ShippingData.material.like(f"%{material}%"))
            if spec:     query = query.filter(ShippingData.spec.like(f"%{spec}%"))
            if start_date: query = query.filter(ShippingData.date >= start_date)
            if end_date:   query = query.filter(ShippingData.date <= end_date)

            query = query.order_by(ShippingData.date.asc())

            rows = query.all()  # tuple: (id, date, order_num, group_count)

            # 批次撈取這些記錄、此量測項目的子表明細 → {record_id: {group_num: [各段量測]}}
            # 分段量測（前/中/後段）同一組別會有多筆，一律以 list 收集
            record_ids = [r[0] for r in rows]
            meas_by_record = defaultdict(dict)
            if record_ids:
                meas_rows = ShippingMeasurement.query.filter(
                    ShippingMeasurement.shipping_id.in_(record_ids),
                    ShippingMeasurement.item == field,
                ).all()
                for m in meas_rows:
                    meas_by_record[m.shipping_id].setdefault(m.group_num, []).append(m)

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
            excluded_count = 0

            for idx, r in enumerate(rows):
                vals: List[float] = []
                valid_groups = 0
                row_group_count = r[3] or 5  # group_count, default 5
                group_meas = meas_by_record.get(r[0], {})

                for i in range(1, 11):
                    # 只處理記錄組數範圍內的組
                    if i > row_group_count:
                        continue
                    for m in group_meas.get(i) or []:
                        if m.excluded:
                            excluded_count += 1
                            continue
                        try:
                            if is_minmax:
                                # minmax 項目需 min/max 皆有值才計入（與舊版扁平邏輯一致）
                                if m.value_min is not None and m.value_max is not None:
                                    v1 = float(m.value_min)
                                    v2 = float(m.value_max)
                                    val = (v1 + v2) / 2
                                    vals.append(val)
                                    all_values.extend([v1, v2])
                                    valid_groups += 1
                            else:
                                if m.value_single is not None:
                                    v = float(m.value_single)
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

            # --- SPC 統計計算 ---
            control_limits = calculate_control_limits(avgs, ranges, subgroup_sizes)
            usl = tolerance_limits.get("USL")
            lsl = tolerance_limits.get("LSL")

            # 管制界限凍結（§9.4）：若已凍結，套用凍結值取代重新計算的結果
            # skip_frozen_limits 供凍結路由內部呼叫時使用，確保取得的是依目前
            # 資料即時重新計算的數值，不被既有凍結值覆蓋（否則「重新凍結」會
            # 只讀回舊值，無法反映流程變更後的最新資料）。
            limits_frozen = False
            if not skip_frozen_limits:
                frozen = ShippingService.get_frozen_limits({
                    "vendor": vendor, "material": material, "spec": spec, "field": field,
                })
                limits_frozen = frozen is not None
                if limits_frozen:
                    control_limits.update({k: frozen[k] for k in
                        ("x_cl", "x_ucl", "x_lcl", "r_cl", "r_ucl", "r_lcl", "avg_n")})
                    # d2 須對應凍結當下的子組大小，避免 sigma_within = r_cl/d2
                    # 混用「凍結的 r_cl」與「目前資料的 avg_n 所查到的 d2」
                    frozen_avg_n = max(2, min(10, int(frozen["avg_n"])))
                    control_limits["d2"] = SPC_CONSTANTS[frozen_avg_n][3]

            # 穩定性判定（§9.2.2）— 決定回報能力(C)或績效(P)指數
            stability = evaluate_stability(
                avgs,
                control_limits["x_cl"],
                control_limits["x_ucl"],
                control_limits["x_lcl"],
            )
            # 分布評估僅算一次（MLE 擬合成本高），供能力計算與分布統計共用
            dist = assess_distribution(all_values, field=field)
            process_capability = calculate_process_capability(
                avgs,
                all_values,
                control_limits["r_cl"],
                control_limits["d2"],
                tolerance_limits,
                stability=stability,
                characteristic_class=char_class,
                field=field,
                dist=dist,
            )
            distribution_stats = calculate_distribution_stats(all_values, field=field, dist=dist)
            cpk_trend = calculate_cpk_trend(all_values, dates_valid, subgroup_sizes, usl, lsl, is_minmax=is_minmax)

            _result = {
                "labels": labels_valid,
                "ids": ids_valid,
                "dates": dates_valid,
                "avgs": avgs,
                "ranges": ranges,
                "subgroup_sizes": subgroup_sizes,
                "all_values": [round(v, 4) for v in all_values],
                "x_cl": control_limits["x_cl"],
                "x_ucl": control_limits["x_ucl"],
                "x_lcl": control_limits["x_lcl"],
                "r_cl": control_limits["r_cl"],
                "r_ucl": control_limits["r_ucl"],
                "r_lcl": control_limits["r_lcl"],
                "avg_subgroup_size": control_limits["avg_n"] if len(avgs) >= 5 else 5,
                "baseline_count": control_limits["baseline_count"],
                "insufficient_data": insufficient_data,
                "total_rows": len(rows),
                "valid_count": len(avgs),
                "tolerance": tolerance_limits,
                "process_capability": process_capability,
                "distribution_stats": distribution_stats,
                "cpk_trend": cpk_trend,
                "stability": stability,
                "characteristic_class": char_class,
                "excluded_count": excluded_count,
                "limits_frozen": limits_frozen,
            }

            # ── SPCCache 快取寫入（1 小時過期）─────────────────────────────
            # skip_frozen_limits=True 的結果未套用凍結覆蓋，不寫入快取，避免
            # 之後一般查詢誤讀到未套用凍結覆蓋的結果（見上方快取讀取處說明）。
            if not skip_frozen_limits:
                try:
                    _now = datetime.now(timezone.utc)
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
            shipping_data.date = ShippingService._coerce_date(data.get('檢驗日期'))
            shipping_data.inspector_id = inspector.id
            shipping_data.vendor_id = vendor.id
            shipping_data.spec = data.get('檢驗規格')
            shipping_data.material = data.get('材質')
            shipping_data.order_num = data.get('訂單號碼')
            shipping_data.group_count = int(data.get('組數', 5))

            # 合法量測項目（前端只送巢狀 measurements；資料只寫子表）
            VALID_ITEMS = {'外徑', '內徑', '厚度', '同心度', '長度',
                           '硬度', '韋伯氏硬度', '真直度', '真圓度'}

            measurements = data.get('measurements') or {}

            # 重建子表明細（出貨巡檢量測明細）。更新時先清空並 flush，避免後續
            # autoflush 先 INSERT 新列、再 DELETE 舊列而違反唯一鍵。
            if is_update and shipping_data.measurements:
                shipping_data.measurements = []
                db.session.flush()

            for g_str, items in measurements.items():
                try:
                    g = int(g_str)
                except (ValueError, TypeError):
                    continue
                if not (1 <= g <= 10):
                    continue
                for item_key, vals in (items or {}).items():
                    # 複合鍵「項目@位置」拆解；位置不合法（None）時略過
                    item_name, position = parse_measurement_key(item_key)
                    if item_name not in VALID_ITEMS or position is None:
                        continue
                    v_min    = vals.get('value_min')
                    v_max    = vals.get('value_max')
                    v_single = vals.get('value_single')
                    # 僅在有任一量測值時才建立子表明細
                    if v_min is not None or v_max is not None or v_single is not None:
                        shipping_data.measurements.append(ShippingMeasurement(
                            group_num=g,
                            item=item_name,
                            position=position,
                            lower_limit=vals.get('lower_limit'),
                            upper_limit=vals.get('upper_limit'),
                            value_min=v_min,
                            value_max=v_max,
                            value_single=v_single,
                            is_ng=bool(vals.get('is_ng', False)),
                        ))

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
            
            ShippingService._invalidate_spc_cache()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def set_measurement_exclusion(
        measurement_id: int,
        excluded: bool,
        reason: Optional[str],
        actor_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """標示/解除量測值離群排除（§6.6：不刪除、保留追溯、排除統計）"""
        m = db.session.get(ShippingMeasurement, measurement_id)
        if m is None:
            raise ValueError("量測明細不存在")
        normalized_reason = (reason or "").strip()
        if not normalized_reason:
            action = "標示離群" if excluded else "恢復統計"
            raise ValueError(f"{action}必須填寫原因（§6.6）")
        old_value = {
            "excluded": bool(m.excluded),
            "reason": m.exclusion_reason,
            "actor_id": m.exclusion_user_id,
            "at": m.excluded_at.isoformat() if m.excluded_at else None,
        }
        m.excluded = excluded
        m.exclusion_reason = normalized_reason if excluded else None
        m.exclusion_user_id = actor_id if excluded else None
        m.excluded_at = datetime.now(timezone.utc) if excluded else None
        new_value = {
            "excluded": bool(m.excluded),
            "reason": m.exclusion_reason,
            "actor_id": m.exclusion_user_id,
            "at": m.excluded_at.isoformat() if m.excluded_at else None,
            "action_reason": normalized_reason,
        }
        log_audit(
            actor_id,
            "exclude" if excluded else "restore",
            "shipping_measurement",
            m.id,
            old_val=old_value,
            new_val=new_value,
        )
        ShippingService._invalidate_spc_cache()
        db.session.commit()
        return {
            "id": m.id, "排除統計": m.excluded, "排除原因": m.exclusion_reason,
            "排除者ID": m.exclusion_user_id,
            "排除時間": m.excluded_at.isoformat() if m.excluded_at else None,
        }

    @staticmethod
    def get_measurements(shipping_id: int) -> List[Dict[str, Any]]:
        """取得單筆出貨記錄的全部量測明細（供離群值管理 UI）"""
        rows = ShippingMeasurement.query.filter_by(shipping_id=shipping_id).order_by(
            ShippingMeasurement.item, ShippingMeasurement.group_num, ShippingMeasurement.position
        ).all()
        return [{
            "識別碼": m.id, "組別": m.group_num, "量測項目": m.item, "測量位置": m.position,
            "量測值": float(m.value_single) if m.value_single is not None else None,
            "量測最小值": float(m.value_min) if m.value_min is not None else None,
            "量測最大值": float(m.value_max) if m.value_max is not None else None,
            "排除統計": m.excluded, "排除原因": m.exclusion_reason,
            "排除者ID": m.exclusion_user_id,
            "排除時間": m.excluded_at.isoformat() if m.excluded_at else None,
        } for m in rows]

    @staticmethod
    def delete_data(record_id: int) -> bool:
        """刪除出貨檢驗資料"""
        try:
            item = db.session.get(ShippingData, record_id)
            if item:
                db.session.delete(item)
                ShippingService._invalidate_spc_cache()
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
        validate_excel_shape(df)

        from .tolerance_service import ToleranceService

        # 同批匯入常有重複的人員/廠商/規格，以快取避免逐列重複查詢
        inspector_cache: Dict[str, Any] = {}
        vendor_cache: Dict[str, Any] = {}
        tol_cache: Dict[tuple, Any] = {}

        success_count = 0
        try:
            for row_num, row in enumerate(df.iterrows()):
                main_data = row[1].to_dict()

                # Cleanup NaNs
                for k, v in main_data.items():
                    if pd.isna(v): main_data[k] = None

                display_row_num = row_num + 2

                # 人員 / 廠商查詢（快取）
                inspector_name = str(main_data.get('檢驗人員', '')).strip()
                if inspector_name not in inspector_cache:
                    inspector_cache[inspector_name] = Inspector.query.filter_by(name=inspector_name).first()
                inspector = inspector_cache[inspector_name]
                if not inspector:
                    raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'")

                vendor_name = str(main_data.get('廠商名稱', '')).strip()
                if vendor_name not in vendor_cache:
                    vendor_cache[vendor_name] = Vendor.query.filter_by(name=vendor_name).first()
                vendor = vendor_cache[vendor_name]
                if not vendor:
                    raise ValueError(f"第 {display_row_num} 行: 廠商不存在")

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

                # 由 Excel 平鋪欄位建立子表明細（量測值只寫子表 ShippingMeasurement）
                for measurement in build_shipping_measurements_from_row(main_data):
                    shipping_data.measurements.append(ShippingMeasurement(**measurement, is_ng=False))

                # 公差查詢（快取）並計算 is_ng
                tol_key = (shipping_data.material, shipping_data.spec, shipping_data.vendor_id)
                if tol_key not in tol_cache:
                    tol_cache[tol_key] = ToleranceService.check_tolerance({
                        'material': shipping_data.material,
                        'spec': shipping_data.spec,
                        'vendor_id': shipping_data.vendor_id
                    })
                tol_res = tol_cache[tol_key]
                shipping_data.is_ng = (
                    shipping_data.compute_is_ng(tol_res.get('tolerances', []))
                    if tol_res.get('found') else False
                )

                db.session.add(shipping_data)
                success_count += 1

            ShippingService._invalidate_spc_cache()
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

            # eager load 避免 _map_row_to_dict 逐列存取 measurements/inspector/vendor 造成 N+1
            query = query.options(
                contains_eager(ShippingData.vendor),
                joinedload(ShippingData.inspector),
                selectinload(ShippingData.measurements),
            )

            if args.get('vendor'):   query = query.filter(Vendor.name.like(f"%{args['vendor']}%"))
            if args.get('material'): query = query.filter(ShippingData.material.like(f"%{args['material']}%"))
            if args.get('spec'):     query = query.filter(ShippingData.spec.like(f"%{args['spec']}%"))
            if args.get('start_date'): query = query.filter(ShippingData.date >= args['start_date'])
            if args.get('end_date'):   query = query.filter(ShippingData.date <= args['end_date'])

            query = query.order_by(ShippingData.date.asc())

            items = query.all()
            
            if not items:
                df = pd.DataFrame(columns=build_shipping_export_columns())
            else:
                export_data = [
                    build_shipping_export_row(ShippingService._map_row_to_dict(item))
                    for item in items
                ]
                
                df = pd.DataFrame(export_data)

            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return output
        except Exception as e:
            raise e
