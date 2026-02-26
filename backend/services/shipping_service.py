
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import or_, text
from ..extensions import db
from ..models import ShippingData, Inspector, Vendor, VendorToleranceMain, VendorToleranceDetail
from ..utils import (
    format_value,
    validate_inspection_data,
    handle_db_error
)

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
            "廠商名稱": vendor_name.strip()      # legacy key
        }

        # Map dynamic columns
        for i in range(1, 6):
            # Min/Max items
            res[f"外徑{i}-min"] = format_value(getattr(item, f"od{i}_min"))
            res[f"外徑{i}-max"] = format_value(getattr(item, f"od{i}_max"))
            res[f"內徑{i}-min"] = format_value(getattr(item, f"id{i}_min"))
            res[f"內徑{i}-max"] = format_value(getattr(item, f"id{i}_max"))
            res[f"厚度{i}-min"] = format_value(getattr(item, f"th{i}_min"))
            res[f"厚度{i}-max"] = format_value(getattr(item, f"th{i}_max"))
             
            # Single value items
            res[f"同心度{i}"] = format_value(getattr(item, f"concentricity{i}"))
            res[f"長度{i}"] = format_value(getattr(item, f"length{i}"))
            res[f"硬度{i}"] = format_value(getattr(item, f"hardness{i}"))
            res[f"真直度{i}"] = format_value(getattr(item, f"straightness{i}"))

        return res

    @staticmethod
    def get_list(args: Dict[str, Any]) -> Dict[str, Any]:
        """獲取出貨檢驗數據列表"""
        try:
            query = ShippingData.query
            
            # Joins for filtering/display
            query = query.outerjoin(Vendor, ShippingData.vendor_id == Vendor.id)
            query = query.outerjoin(Inspector, ShippingData.inspector_id == Inspector.id)

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
            item = ShippingData.query.get(data_id)
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

        try:
            # 1. Tolerance Lookup (ORM)
            tolerance_limits = {"USL": None, "LSL": None, "found": False}
            if material:
                tol_main = VendorToleranceMain.query.filter_by(material=material)\
                    .order_by(VendorToleranceMain.vendor_id.desc().nullslast(), VendorToleranceMain.spec.desc().nullslast())\
                    .first()
                
                if tol_main:
                    tol_detail = VendorToleranceDetail.query.filter_by(main_id=tol_main.id, item=field).first()
                    if tol_detail:
                        tolerance_limits["found"] = True
                        tolerance_limits["公差下限"] = tol_detail.tolerance_min
                        tolerance_limits["公差上限"] = tol_detail.tolerance_max
                        tolerance_limits["尺寸下限"] = tol_detail.dim_min
                        tolerance_limits["尺寸上限"] = tol_detail.dim_max
                        
                        if tol_detail.dim_min is not None and tol_detail.dim_max is not None:
                            tolerance_limits["LSL"] = tol_detail.dim_min
                            tolerance_limits["USL"] = tol_detail.dim_max
                        elif tol_detail.tolerance_min is not None and tol_detail.tolerance_max is not None:
                            # Try to get standard value if dims missing
                             # For simplicity, if standard value was needed we query it. 
                             # The model has dim_min/max, tol_min/max, and std_val?
                             # In model definition: std_val = db.Column('標準值', db.Float)
                             
                             std = tol_detail.std_val
                             if std is not None:
                                 tolerance_limits["LSL"] = std - tol_detail.tolerance_min
                                 tolerance_limits["USL"] = std + tol_detail.tolerance_max

            # 2. Data Query (ORM)
            # Map field name to model attribute prefix
            field_map = {
                '外徑': 'od',
                '內徑': 'id', # id{i}_min
                '厚度': 'th',
                '同心度': 'concentricity',
                '長度': 'length',
                '硬度': 'hardness',
                '真直度': 'straightness'
            }
            attr_prefix = field_map.get(field)
            if not attr_prefix:
                return {"labels": [], "avgs": [], "ranges": []}

            is_minmax = field in ['外徑', '內徑', '厚度']

            # Dynamic query selection
            # Select ID, Date, OrderNum and the relevant 5 groups columns
            entities = [ShippingData.id, ShippingData.date, ShippingData.order_num]
            for i in range(1, 6):
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
            # 0: id, 1: date, 2: order_num
            # 3...: measurements
            
            avgs = []
            ranges = []
            ids_valid = []
            dates_valid = []
            labels_valid = []
            insufficient_data = []

            for idx, r in enumerate(rows):
                vals: List[float] = []
                valid_groups = 0
                
                # Iterate logic depends on how many columns we fetched
                # If minmax: 3,4 (Group1), 5,6 (Group2)...
                # If single: 3 (Group1), 4 (Group2)...
                
                current_col_idx = 3
                
                for i in range(1, 6):
                    try:
                        if is_minmax:
                            v1_str = r[current_col_idx]
                            v2_str = r[current_col_idx+1]
                            current_col_idx += 2
                            
                            if v1_str and v2_str: # checking not None and not empty string
                                val = (float(v1_str) + float(v2_str)) / 2
                                vals.append(val)
                                valid_groups += 1
                        else:
                            v_str = r[current_col_idx]
                            current_col_idx += 1
                            if v_str:
                                vals.append(float(v_str))
                                valid_groups += 1
                    except (ValueError, TypeError):
                         pass # Skip invalid numbers

                original_idx = len(rows) - 1 - idx
                
                if valid_groups >= 3 and vals:
                    vals_np = np.array(vals, dtype=float)
                    avgs.append(float(np.mean(vals_np)))
                    ranges.append(float(np.ptp(vals_np)))
                    ids_valid.append(str(r[0]))
                    # Date formatting
                    d_val = r[1]
                    d_str = d_val.strftime('%Y-%m-%d') if hasattr(d_val, 'strftime') else str(d_val) if d_val else ''
                    dates_valid.append(d_str)
                    
                    label_val = r[2] # Order number
                    labels_valid.append(str(label_val) if label_val else str(r[0]))
                else:
                    insufficient_data.append({
                         "id": str(r[0]),
                         "date": str(r[1]) if r[1] else '',
                         "valid_groups": valid_groups,
                         "original_idx": original_idx
                    })

            # Control Limit Calculation (Same as before)
            BASELINE_COUNT = 25
            if len(avgs) >= 5:
                baseline_count = min(BASELINE_COUNT, len(avgs))
                base_avgs = avgs[:baseline_count]
                base_ranges = ranges[:baseline_count]
                x_cl = float(np.mean(base_avgs))
                r_cl = float(np.mean(base_ranges))
                x_ucl = x_cl + 0.577 * r_cl
                x_lcl = x_cl - 0.577 * r_cl
                r_ucl = 2.114 * r_cl
                x_lcl = max(x_lcl, 0)
            else:
                x_cl = x_ucl = x_lcl = r_cl = r_ucl = 0.0
                baseline_count = 0

            return {
                "labels": labels_valid,
                "ids": ids_valid,
                "dates": dates_valid,
                "avgs": avgs,
                "ranges": ranges,
                "x_cl": x_cl,
                "x_ucl": x_ucl,
                "x_lcl": x_lcl,
                "r_cl": r_cl,
                "r_ucl": r_ucl,
                "baseline_count": baseline_count,
                "insufficient_data": insufficient_data,
                "total_rows": len(rows),
                "valid_count": len(avgs),
                "tolerance": tolerance_limits
            }
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
                shipping_data = ShippingData.query.get(record_id)
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

            # Set dynamic columns
            def get_val(k):
                val = data.get(k)
                if val is None or val == "":
                    return None
                return str(val)

            for i in range(1, 6):
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
            item = ShippingData.query.get(record_id)
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

                shipping_data = ShippingData(
                    date=main_data.get('檢驗日期'),
                    inspector_id=inspector.id,
                    vendor_id=vendor.id,
                    spec=main_data.get('檢驗規格'),
                    material=main_data.get('材質'),
                    order_num=main_data.get('訂單號碼')
                )

                # Map columns
                def get_val(k):
                    val = main_data.get(k)
                    if pd.isna(val) or val is None or str(val).strip() == "":
                        return None
                    return str(val)
                
                for i in range(1, 6):
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
                cols = ['識別碼', '檢驗日期', '材質', '檢驗規格', '訂單號碼', '檢驗人員', '廠商名稱']
                for i in range(1, 6):
                    cols.extend([f'外徑{i}-最小', f'外徑{i}-最大', f'內徑{i}-最小', f'內徑{i}-最大', f'厚度{i}-最小', f'厚度{i}-最大'])
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
                        '廠商名稱': row['廠商中文名稱']
                    }
                    for i in range(1, 6):
                        export_row[f'外徑{i}-最小'] = row.get(f'外徑{i}-min', '')
                        export_row[f'外徑{i}-最大'] = row.get(f'外徑{i}-max', '')
                        export_row[f'內徑{i}-最小'] = row.get(f'內徑{i}-min', '')
                        export_row[f'內徑{i}-最大'] = row.get(f'內徑{i}-max', '')
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
