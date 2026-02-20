
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import func, text
from ..extensions import db
from ..models import PatrolMain, PatrolDetail, Machine, Operator, Inspector, Vendor
from ..utils import (
    format_value,
    validate_patrol_data,
    handle_db_error
)

class PatrolService:
    @staticmethod
    def get_options() -> Dict[str, List[Dict[str, Any]]]:
        """獲取下拉選單選項"""
        try:
            machines = [{"id": r.id, "name": r.name.strip()} for r in Machine.query.all()]
            operators = [{"id": r.id, "name": r.name.strip()} for r in Operator.query.all()]
            inspectors = [{"id": r.id, "name": r.name.strip()} for r in Inspector.query.all()]
            customers = [{"id": r.id, "name": r.name.strip()} for r in Vendor.query.all()]
            
            return {
                "machines": machines,
                "operators": operators,
                "inspectors": inspectors,
                "customers": customers
            }
        except Exception as e:
            raise e

    @staticmethod
    def get_spc(args: Dict[str, Any]) -> Dict[str, Any]:
        """獲取巡檢 SPC 統計數據"""
        item = args.get('item', '厚度')
        pos = args.get('pos', '')
        
        query = db.session.query(PatrolMain.date, PatrolDetail.main_id, PatrolDetail.group, PatrolDetail.min_val, PatrolDetail.max_val)\
            .join(PatrolDetail)\
            .filter(PatrolDetail.item == item)

        if pos: 
            query = query.filter(PatrolDetail.position == pos)
        if args.get('s_date'): 
            query = query.filter(PatrolMain.date >= args['s_date'])
        if args.get('e_date'): 
            query = query.filter(PatrolMain.date <= args['e_date'])
        if args.get('m_id'):   
            query = query.filter(PatrolMain.machine_id == args['m_id'])
        if args.get('op_id'):  
            query = query.filter(PatrolMain.operator_id == args['op_id'])
        if args.get('mat'):    
            query = query.filter(PatrolMain.material.like(f"%{args['mat']}%"))
        if args.get('spec'):   
            query = query.filter(PatrolMain.spec.like(f"%{args['spec']}%"))

        query = query.order_by(PatrolMain.id.desc())
        
        rows = query.all()

        if not rows:
            return {"labels": [], "avgs": [], "ranges": []}

        groups: Dict[str, List[float]] = {}
        for r in rows:
            # r is a tuple: (date, main_id, group, min_val, max_val)
            val1 = r[3]
            val2 = r[4]
            if val1 is None or val2 is None:
                continue
            
            # Format date key
            date_str = r[0].strftime('%m/%d') if hasattr(r[0], 'strftime') else str(r[0])
            key = f"{date_str}-#{r[1]}-G{r[2]}"
            
            try:
                groups.setdefault(key, []).extend([float(val1), float(val2)])
            except ValueError:
                continue

        labels = list(groups.keys())
        avgs = [np.mean(groups[k]) for k in labels]
        ranges = [np.ptp(groups[k]) for k in labels]

        A2, D4, D3 = 0.483, 2.004, 0
        if avgs:
            x_cl, r_cl = float(np.mean(avgs)), float(np.mean(ranges))
            x_ucl = x_cl + A2 * r_cl
            x_lcl = x_cl - A2 * r_cl
            r_ucl = D4 * r_cl
            r_lcl = D3 * r_cl
        else:
            x_cl = r_cl = x_ucl = x_lcl = r_ucl = r_lcl = 0.0

        return {
            "labels": labels,
            "avgs": [float(x) for x in avgs],
            "ranges": [float(x) for x in ranges],
            "x_cl": x_cl,
            "x_ucl": x_ucl,
            "x_lcl": x_lcl,
            "r_cl": r_cl,
            "r_ucl": r_ucl,
            "r_lcl": r_lcl
        }

    @staticmethod
    def get_detail(id: int) -> Optional[Dict[str, Any]]:
        """獲取巡檢詳細資料（主檔+子檔）"""
        patrol = PatrolMain.query.get(id)
        if not patrol:
            return None

        # Main data
        main = {
            "識別碼": patrol.id,
            "檢驗日期": format_value(patrol.date),
            "機台": patrol.machine_id,
            "主機手": patrol.operator_id,
            "檢驗人員": patrol.inspector_id,
            "材質": format_value(patrol.material),
            "擠壓規格": format_value(patrol.spec),
            "客戶名稱": patrol.customer_id,
            "原料批號": format_value(patrol.batch_num)
        }

        # Details
        details_list = []
        # Sort details by group, item, position if needed, though list usually follows creation order or DB default
        # Implementing explicit sort just in case
        sorted_details = sorted(patrol.details, key=lambda x: (x.group, x.item, x.position))
        
        for d in sorted_details:
            group_val = str(d.group).strip()
            if group_val.isdigit():
                group_val = f"第{group_val}組"
            
            details_list.append({
                "group": group_val,
                "item": d.item.strip() if d.item else "",
                "pos": d.position.strip() if d.position else "",
                "min": float(d.min_val) if d.min_val else None,
                "max": float(d.max_val) if d.max_val else None
            })

        return {
            "main": main,
            "details": details_list
        }

    @staticmethod
    def _parse_id(val: Any) -> Optional[int]:
        """Convert value to int or None if empty/invalid"""
        if not val and val != 0:
            return None
        if isinstance(val, str) and not val.strip():
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def add_patrol(data: Dict[str, Any]) -> int:
        """新增巡檢資料"""
        errors = validate_patrol_data(data)
        if errors:
            raise ValueError(", ".join(errors))

        try:
            new_patrol = PatrolMain(
                date=data.get('檢驗日期'),
                machine_id=PatrolService._parse_id(data.get('機台')),
                operator_id=PatrolService._parse_id(data.get('主機手')),
                inspector_id=PatrolService._parse_id(data.get('檢驗人員')),
                material=data.get('材質'),
                spec=data.get('擠壓規格'),
                customer_id=PatrolService._parse_id(data.get('客戶名稱')),
                batch_num=data.get('原料批號')
            )
            db.session.add(new_patrol)
            db.session.flush() # Get ID

            for d in data.get('details', []):
                group_raw = str(d.get('group', '')).strip()
                group_val = group_raw.replace('第', '').replace('組', '')
                group_val = int(group_val) if group_val.isdigit() else 1

                min_val = float(d.get('min')) if d.get('min') is not None else None
                max_val = float(d.get('max')) if d.get('max') is not None else None

                new_detail = PatrolDetail(
                    main_id=new_patrol.id,
                    group=group_val,
                    item=d.get('item'),
                    position=d.get('pos'),
                    min_val=min_val,
                    max_val=max_val
                )
                db.session.add(new_detail)

            db.session.commit()
            return new_patrol.id
        except Exception as e:
            try:
                import traceback
                with open('debug_error.log', 'a') as f:
                    f.write(f"[{datetime.now()}] ERROR IN ADD_PATROL: {str(e)}\n")
                    f.write(traceback.format_exc())
                    f.write("\n" + "="*30 + "\n")
            except:
                pass
            db.session.rollback()
            raise e

    @staticmethod
    def update_patrol(data: Dict[str, Any]) -> bool:
        """更新巡檢資料"""
        record_id = data.get('id')
        if not record_id:
            raise ValueError("缺少記錄 ID")

        errors = validate_patrol_data(data)
        if errors:
            raise ValueError(", ".join(errors))

        try:
            patrol = PatrolMain.query.get(record_id)
            if not patrol:
                raise ValueError("找不到該筆資料")

            # Update main fields
            patrol.date = data.get('檢驗日期')
            patrol.machine_id = PatrolService._parse_id(data.get('機台'))
            patrol.operator_id = PatrolService._parse_id(data.get('主機手'))
            patrol.inspector_id = PatrolService._parse_id(data.get('檢驗人員'))
            patrol.material = data.get('材質')
            patrol.spec = data.get('擠壓規格')
            patrol.customer_id = PatrolService._parse_id(data.get('客戶名稱'))
            patrol.batch_num = data.get('原料批號')

            # Update details: Delete all and re-insert
            PatrolDetail.query.filter_by(main_id=record_id).delete()

            for d in data.get('details', []):
                group_raw = str(d.get('group', '')).strip()
                group_val = group_raw.replace('第', '').replace('組', '')
                group_val = int(group_val) if group_val.isdigit() else 1

                min_val = float(d.get('min')) if d.get('min') is not None else None
                max_val = float(d.get('max')) if d.get('max') is not None else None

                new_detail = PatrolDetail(
                    main_id=record_id,
                    group=group_val,
                    item=d.get('item'),
                    position=d.get('pos'),
                    min_val=min_val,
                    max_val=max_val
                )
                db.session.add(new_detail)

            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_patrol(record_id: int) -> bool:
        """刪除巡檢資料"""
        try:
            # Use query to find so we can delete. 
            # Note: Cascade delete on relationship should handle details, 
            # but sometimes implicit delete is safer to be explicit or if cascade not working.
            # I defined cascade="all, delete-orphan" in PatrolMain, so just deleting main is enough.
            patrol = PatrolMain.query.get(record_id)
            if patrol:
                db.session.delete(patrol)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_history(args: Dict[str, Any]) -> Dict[str, Any]:
        """獲取巡檢歷史列表（分頁）"""
        try:
            query = db.session.query(PatrolMain, Machine.name.label('m_name'), Operator.name.label('op_name'))\
                .outerjoin(Machine, PatrolMain.machine_id == Machine.id)\
                .outerjoin(Operator, PatrolMain.operator_id == Operator.id)

            if args.get('s_date'): query = query.filter(PatrolMain.date >= args['s_date'])
            if args.get('e_date'): query = query.filter(PatrolMain.date <= args['e_date'])
            if args.get('m_id'):   query = query.filter(PatrolMain.machine_id == args['m_id'])
            if args.get('op_id'):  query = query.filter(PatrolMain.operator_id == args['op_id'])
            if args.get('mat'):    query = query.filter(PatrolMain.material.like(f"%{args['mat']}%"))
            if args.get('spec'):   query = query.filter(PatrolMain.spec.like(f"%{args['spec']}%"))

            query = query.order_by(PatrolMain.id.desc())

            page = int(args.get('page', 1))
            per_page = int(args.get('per_page', 20))
            
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            data = []
            for item in pagination.items:
                patrol, m_name, op_name = item
                date_str = patrol.date.strftime('%Y-%m-%d') if patrol.date else ''
                data.append({
                    'id': patrol.id,
                    'date': date_str,
                    'm_name': m_name.strip() if m_name else '',
                    'op_name': op_name.strip() if op_name else '',
                    'mat': patrol.material,
                    'spec': patrol.spec
                })

            return {
                "data": data,
                "pages": pagination.pages,
                "total": pagination.total
            }
        except Exception as e:
            raise e

    @staticmethod
    def export_excel(args: Dict[str, Any]) -> BytesIO:
        """匯出巡檢資料 Excel"""
        try:
            # Query Logic
            query = db.session.query(
                PatrolMain, 
                Machine.name.label('m_name'), 
                Operator.name.label('op_name'),
                Inspector.name.label('i_name'),
                Vendor.name.label('v_name')
            )\
            .outerjoin(Machine, PatrolMain.machine_id == Machine.id)\
            .outerjoin(Operator, PatrolMain.operator_id == Operator.id)\
            .outerjoin(Inspector, PatrolMain.inspector_id == Inspector.id)\
            .outerjoin(Vendor, PatrolMain.customer_id == Vendor.id)

            if args.get('s_date'): query = query.filter(PatrolMain.date >= args['s_date'])
            if args.get('e_date'): query = query.filter(PatrolMain.date <= args['e_date'])
            if args.get('m_id'):   query = query.filter(PatrolMain.machine_id == args['m_id'])
            if args.get('op_id'):  query = query.filter(PatrolMain.operator_id == args['op_id'])
            if args.get('mat'):    query = query.filter(PatrolMain.material.like(f"%{args['mat']}%"))
            if args.get('spec'):   query = query.filter(PatrolMain.spec.like(f"%{args['spec']}%"))

            query = query.order_by(PatrolMain.id.desc())
            
            rows = query.all()

            if not rows:
                df = pd.DataFrame(columns=['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員'])
            else:
                export_data = []
                unique_groups = []

                for row in rows:
                    patrol, m_name, op_name, i_name, v_name = row
                    
                    # Get details using relationship
                    # Sort details
                    details = sorted(patrol.details, key=lambda x: (x.group, x.item, x.position))
                    
                    measurements = {}
                    current_groups = []

                    for d in details:
                        group_val = str(d.group)
                        group_name = group_val if "組" in group_val else f"第{group_val}組"
                        
                        item = d.item.strip() if d.item else ""
                        pos = d.position.strip() if d.position else ""
                        
                        min_val = float(d.min_val) if d.min_val else ""
                        max_val = float(d.max_val) if d.max_val else ""

                        key = f"{group_name}_{item}_{pos}"
                        measurements[key] = {"min": min_val, "max": max_val}
                        
                        if group_name not in current_groups:
                            current_groups.append(group_name)

                    for g in current_groups:
                        if g not in unique_groups:
                            unique_groups.append(g)

                    if not current_groups:
                        current_groups = ["第1組"]
                        if "第1組" not in unique_groups:
                            unique_groups.append("第1組")

                    row_dict = {
                        '識別碼': patrol.id,
                        '檢驗日期': patrol.date.strftime('%Y-%m-%d') if patrol.date else '',
                        '擠壓機編號': m_name.strip() if m_name else '',
                        '員工姓名': op_name.strip() if op_name else '',
                        '材質': patrol.material,
                        '擠壓規格': patrol.spec,
                        '廠商名稱': v_name.strip() if v_name else '',
                        '原料批號': patrol.batch_num,
                        '檢驗人員': i_name.strip() if i_name else ''
                    }

                    for group in current_groups:
                        for item in ["外徑", "內徑", "厚度"]:
                            for pos in ["前段", "中段", "後段"]:
                                key = f"{group}_{item}_{pos}"
                                min_val = measurements.get(key, {}).get("min", "")
                                max_val = measurements.get(key, {}).get("max", "")
                                row_dict[f"{group}{item}{pos}最小"] = min_val
                                row_dict[f"{group}{item}{pos}最大"] = max_val
                    
                    export_data.append(row_dict)
                
                df = pd.DataFrame(export_data)

            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return output
        except Exception as e:
            raise e

    @staticmethod
    def import_data(file: Any) -> int:
        """匯入巡檢資料 Excel"""
        try:
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"檔案讀取失敗: {str(e)}")

        success_count = 0
        try:
            # We can use ORM for lookups but bulk insert might be faster if purely adding.
            # However, for consistency and relationship management, let's use ORM session.
            # Speed is usually acceptable for Excel imports of moderate size.
            
            for row_num, row in enumerate(df.iterrows()):
                main_data = row[1].to_dict()
                display_row_num = row_num + 2

                # Lookups
                machine_name = str(main_data.get('擠壓機編號', '')).strip()
                machine = Machine.query.filter_by(name=machine_name).first() if machine_name else None
                if not machine and machine_name:
                    raise ValueError(f"第 {display_row_num} 行: 找不到機台 '{machine_name}'")
                
                operator_name = str(main_data.get('員工姓名', '')).strip()
                operator = Operator.query.filter_by(name=operator_name).first() if operator_name else None
                if not operator and operator_name:
                    raise ValueError(f"第 {display_row_num} 行: 找不到員工 '{operator_name}'")

                customer_name = str(main_data.get('客戶名稱', '')).strip()
                customer = Vendor.query.filter_by(name=customer_name).first() if customer_name else None
                
                inspector_name = str(main_data.get('檢驗人員', '')).strip()
                inspector = Inspector.query.filter_by(name=inspector_name).first() if inspector_name else None
                if not inspector and inspector_name:
                    raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'")

                # Checks required fields
                if not machine: raise ValueError(f"第 {display_row_num} 行: 機台必填")
                if not operator: raise ValueError(f"第 {display_row_num} 行: 員工必填")
                if not inspector: raise ValueError(f"第 {display_row_num} 行: 檢驗人員必填")

                new_patrol = PatrolMain(
                    date=main_data.get('檢驗日期'),
                    machine_id=machine.id,
                    operator_id=operator.id,
                    material=main_data.get('材質'),
                    spec=main_data.get('擠壓規格'),
                    customer_id=customer.id if customer else None,
                    batch_num=main_data.get('原料批號'),
                    inspector_id=inspector.id
                )
                db.session.add(new_patrol)
                db.session.flush()

                # Process details from columns
                measurement_cols = [
                    ("外徑前段最小", "外徑", "前段", "min"), ("外徑前段最大", "外徑", "前段", "max"),
                    ("外徑中段最小", "外徑", "中段", "min"), ("外徑中段最大", "外徑", "中段", "max"),
                    ("外徑後段最小", "外徑", "後段", "min"), ("外徑後段最大", "外徑", "後段", "max"),
                    ("內徑前段最小", "內徑", "前段", "min"), ("內徑前段最大", "內徑", "前段", "max"),
                    ("內徑中段最小", "內徑", "中段", "min"), ("內徑中段最大", "內徑", "中段", "max"),
                    ("內徑後段最小", "內徑", "後段", "min"), ("內徑後段最大", "內徑", "後段", "max"),
                    ("厚度前段最小", "厚度", "前段", "min"), ("厚度前段最大", "厚度", "前段", "max"),
                    ("厚度中段最小", "厚度", "中段", "min"), ("厚度中段最大", "厚度", "中段", "max"),
                    ("厚度後段最小", "厚度", "後段", "min"), ("厚度後段最大", "厚度", "後段", "max")
                ]

                measurements = {}
                for col_name, item, pos, min_max in measurement_cols:
                    val = main_data.get(col_name)
                    if pd.isna(val) == False and str(val).strip() != "":
                        key = f"{item}_{pos}"
                        if key not in measurements:
                            measurements[key] = {"min": "", "max": ""}
                        measurements[key][min_max] = str(val)

                for key, vals in measurements.items():
                    item, pos = key.split("_")
                    min_val = vals["min"]
                    max_val = vals["max"]
                    
                    if min_val == "" and max_val == "":
                        continue

                    new_detail = PatrolDetail(
                        main_id=new_patrol.id,
                        group=1, # Default to group 1 for flattened Excel structure usually
                        item=item,
                        position=pos,
                        min_val=min_val if min_val != "" else None,
                        max_val=max_val if max_val != "" else None
                    )
                    db.session.add(new_detail)

                success_count += 1
            
            db.session.commit()
            return success_count
        except Exception as e:
            db.session.rollback()
            raise e
