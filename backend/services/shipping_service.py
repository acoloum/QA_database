
import pandas as pd
from io import BytesIO
from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import or_, text
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from ..extensions import db
from ..models import ShippingData, ShippingMeasurement, Inspector, Vendor, SPCCache
from ..utils import (
    bounded_int,
    format_value,
    validate_inspection_data,
    validate_excel_shape,
    handle_db_error,
    parse_spec_nominals,
    log_audit,
)

from .shipping_import import build_shipping_measurements_from_row
from .shipping_export import build_shipping_export_columns, build_shipping_export_row
from .shipping_measurement_keys import build_measurement_key, parse_measurement_key

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
            if args.get('vendor'):   query = query.filter(Vendor.name.ilike(f"%{args['vendor']}%"))
            if args.get('material'): query = query.filter(ShippingData.material.ilike(f"%{args['material']}%"))
            if args.get('spec'):     query = query.filter(ShippingData.spec.ilike(f"%{args['spec']}%"))
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

    @staticmethod
    def get_by_id(data_id: int) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取單筆出貨檢驗資料"""
        item = ShippingData.query.options(
            joinedload(ShippingData.inspector),
            joinedload(ShippingData.vendor),
            selectinload(ShippingData.measurements),
        ).filter_by(id=data_id).first()
        if not item:
            return None
        return ShippingService._map_row_to_dict(item)

    @staticmethod
    def get_stats(args: Dict[str, Any], skip_frozen_limits: bool = False) -> Dict[str, Any]:
        """使用 2026 共用 SPC 引擎產生即時預覽；舊凍結界限不再覆蓋計算。"""
        from .spc_study_service import SpcStudyService

        return SpcStudyService.preview("shipping", args)

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
            raise

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
            raise

    @staticmethod
    def import_data(file: Any) -> int:
        """匯入 Excel 資料"""
        try:
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"檔案讀取失敗: {str(e)}")
        validate_excel_shape(df)

        from .tolerance_service import ToleranceService

        # 預先載入全部檢驗人員/廠商對照表，避免逐列查詢資料庫（N+1）
        # 同名紀錄以最後一筆覆蓋（與 .first() 的任意順序差異極小，可忽略）
        inspector_cache: Dict[str, Any] = {i.name.strip(): i for i in Inspector.query.all()}
        vendor_cache: Dict[str, Any] = {v.name.strip(): v for v in Vendor.query.all()}
        tol_cache: Dict[tuple, Any] = {}

        success_count = 0
        try:
            for row_num, row in enumerate(df.iterrows()):
                main_data = row[1].to_dict()

                # Cleanup NaNs
                for k, v in main_data.items():
                    if pd.isna(v): main_data[k] = None

                display_row_num = row_num + 2

                # 人員 / 廠商查詢（記憶體對照表）
                inspector_name = str(main_data.get('檢驗人員', '')).strip()
                inspector = inspector_cache.get(inspector_name) if inspector_name else None
                if not inspector:
                    raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'")

                vendor_name = str(main_data.get('廠商名稱', '')).strip()
                vendor = vendor_cache.get(vendor_name) if vendor_name else None
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
            raise

    @staticmethod
    def export_excel(args: Dict[str, Any]) -> BytesIO:
        """匯出 Excel"""
        query = ShippingData.query.outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)

        # eager load 避免 _map_row_to_dict 逐列存取 measurements/inspector/vendor 造成 N+1
        query = query.options(
            contains_eager(ShippingData.vendor),
            joinedload(ShippingData.inspector),
            selectinload(ShippingData.measurements),
        )

        if args.get('vendor'):   query = query.filter(Vendor.name.ilike(f"%{args['vendor']}%"))
        if args.get('material'): query = query.filter(ShippingData.material.ilike(f"%{args['material']}%"))
        if args.get('spec'):     query = query.filter(ShippingData.spec.ilike(f"%{args['spec']}%"))
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
