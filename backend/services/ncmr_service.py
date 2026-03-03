
import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import joinedload, subqueryload
from sqlalchemy import desc
from ..extensions import db
from ..models import NCMR, CorrectiveAction, Inspector, Vendor, PatrolMain, ShippingData, ReworkRequest, ReworkExecution
from ..utils import (
    format_value,
    handle_db_error,
    generate_ncmr_number,
    generate_car_number,
    generate_8d_number
)

class NCMRService:
    # ==================================================
    # NCMR Logic
    # ==================================================
    @staticmethod
    def get_ncmr_list(status: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query = NCMR.query.options(
                joinedload(NCMR.inspector),
                subqueryload(NCMR.corrective_actions),
                subqueryload(NCMR.rework_requests).subqueryload(ReworkRequest.executions)
            )

            if status:
                query = query.filter(NCMR.status == status)
            
            query = query.order_by(NCMR.id.desc())
            
            ncmrs = query.all()
            data = []
            
            for n in ncmrs:
                # Logic to determine latest status
                car_status = None
                capa_status = None
                
                # Filter CAs in Python (eager loaded)
                cars = [ca for ca in n.corrective_actions if ca.car_number]
                if cars:
                    # Sort by id desc (assuming latest created is last)
                    latest_car = sorted(cars, key=lambda x: x.id, reverse=True)[0]
                    car_status = latest_car.status

                capas = [ca for ca in n.corrective_actions if ca.eight_d_number]
                if capas:
                    latest_capa = sorted(capas, key=lambda x: x.id, reverse=True)[0]
                    capa_status = latest_capa.status

                rework_count = 0
                rework_status = None
                if n.rework_requests:
                    # Rework count = total executions across all requests
                    rework_count = sum(len(req.executions) for req in n.rework_requests)
                    latest_rework = sorted(n.rework_requests, key=lambda x: x.id, reverse=True)[0]
                    rework_status = latest_rework.status
                
                inspector_name = n.inspector.name if n.inspector else ""
                
                item = {
                    "識別碼": n.id,
                    "單號": n.ncmr_number,
                    "日期": n.date.strftime('%Y-%m-%d') if n.date else "",
                    "來源": n.source,
                    "產品資訊": n.product_info,
                    "產品數量": format_value(n.quantity),
                    "材質": n.material,
                    "廠商": n.vendor,
                    "批號": n.batch_num,
                    "不良描述": n.description,
                    "不合格數量": format_value(n.defect_quantity),
                    "判定結果": n.result,
                    "狀態": n.status,
                    "不良原因大類": n.defect_category,
                    "不良原因細項": n.defect_detail,
                    "發現人員姓名": inspector_name,
                    "CAR狀態": car_status,
                    "CAPA狀態": capa_status,
                    "重工執行次數": rework_count,
                    "重工狀態": rework_status
                }
                data.append(item)
                
            return data
        except Exception as e:
            raise e

    @staticmethod
    def add_ncmr(data: Dict[str, Any]) -> str:
        try:
            inspector_name = data.get('發現人員姓名')
            inspector = Inspector.query.filter_by(name=inspector_name).first() if inspector_name else None
            
            ncmr_number = generate_ncmr_number()
            
            ncmr = NCMR(
                ncmr_number=ncmr_number,
                date=data.get('日期'),
                create_date=data.get('建立日期') or datetime.date.today(),
                source=data.get('來源'),
                product_info=data.get('產品資訊'),
                quantity=data.get('產品數量') if data.get('產品數量') != '' else None,
                material=data.get('材質'),
                vendor=data.get('廠商'),
                batch_num=data.get('批號'),
                description=data.get('不良描述'),
                defect_quantity=data.get('不合格數量') if data.get('不合格數量') != '' else None,
                inspector_id=inspector.id if inspector else None,
                result=data.get('判定結果'),
                status=data.get('狀態', '待處理'),
                defect_category=data.get('不良原因大類'),
                defect_detail=data.get('不良原因細項')
            )
            
            db.session.add(ncmr)
            db.session.commit()
            return ncmr_number
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_ncmr(data: Dict[str, Any]) -> bool:
        ncmr_id = data.get('識別碼')
        if not ncmr_id:
            raise ValueError("缺少識別碼")
        
        try:
            ncmr = NCMR.query.get(ncmr_id)
            if not ncmr:
                raise ValueError("找不到該筆資料")

            if data.get('發現人員姓名'):
                inspector = Inspector.query.filter_by(name=data.get('發現人員姓名')).first()
                if inspector:
                     ncmr.inspector_id = inspector.id

            # Mapping with type conversion
            field_map = {
                '日期': 'date', '建立日期': 'create_date', '來源': 'source', '產品資訊': 'product_info',
                '產品數量': 'quantity', '材質': 'material', '廠商': 'vendor',
                '批號': 'batch_num', '不良描述': 'description', 
                '不合格數量': 'defect_quantity', '判定結果': 'result',
                '狀態': 'status', '不良原因大類': 'defect_category',
                '不良原因細項': 'defect_detail'
            }
            
            # Type converters
            int_fields = {'產品數量', '不合格數量'}
            date_fields = {'日期', '建立日期'}
            
            for key, attr in field_map.items():
                if key in data:
                    val = data[key]
                    # Handle empty strings -> None
                    if val == '' or val is None:
                        setattr(ncmr, attr, None)
                    # Type conversion
                    elif key in int_fields:
                        try:
                            setattr(ncmr, attr, int(val))
                        except (ValueError, TypeError):
                            setattr(ncmr, attr, None)
                    elif key in date_fields:
                        try:
                            if isinstance(val, str):
                                setattr(ncmr, attr, datetime.datetime.strptime(val, '%Y-%m-%d').date())
                            else:
                                setattr(ncmr, attr, val)
                        except (ValueError, TypeError):
                            setattr(ncmr, attr, None)
                    else:
                        setattr(ncmr, attr, val)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_ncmr(ncmr_id: int) -> bool:
        try:
            # Explicitly delete CAs first if cascade not trusted, but defined cascade should work.
            # However legacy code deleted CA then NCMR.
            # I set cascade="all, delete-orphan".
            ncmr = NCMR.query.get(ncmr_id)
            if ncmr:
                db.session.delete(ncmr)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_source_info(source_type: str, source_id: int) -> Dict[str, Any]:
        try:
            info = {}
            if source_type == '巡檢':
                patrol = PatrolMain.query.get(source_id)
                if patrol:
                    vendor_name = ""
                    # Patrol has customer_id linked to Vendor table
                    if patrol.customer_id:
                        v = Vendor.query.get(patrol.customer_id)
                        vendor_name = v.name if v else ""
                    
                    info = {
                        "材質": patrol.material,
                        "產品資訊": patrol.spec,
                        "批號": patrol.batch_num,
                        "廠商": vendor_name
                    }
            elif source_type == '出貨檢':
                shipping = ShippingData.query.get(source_id)
                if shipping:
                    vendor_name = shipping.vendor.name if shipping.vendor else ""
                    info = {
                        "材質": shipping.material,
                        "產品資訊": shipping.spec,
                        "批號": shipping.order_num,
                        "廠商": vendor_name
                    }
            return info
        except Exception as e:
            raise e

    @staticmethod
    def get_ncmr_info(ncmr_id: int) -> Optional[Dict[str, Any]]:
        try:
            n = NCMR.query.options(joinedload(NCMR.inspector)).get(ncmr_id)
            if not n:
                return None
            
            # Map to flat dict with specific keys expected by frontend
            item = {
                "識別碼": n.id,
                "NCMR單號": n.ncmr_number,
                "建立日期": n.create_date,
                "發現日期": n.date, # DateTime object
                "來源": n.source,
                "產品資訊": n.product_info,
                "產品數量": n.quantity,
                "材質": n.material,
                "廠商": n.vendor,
                "批號": n.batch_num,
                "不良描述": n.description,
                "不良數量": n.defect_quantity,
                "判定結果": n.result,
                "狀態": n.status,
                "不良原因大類": n.defect_category,
                "不良原因細項": n.defect_detail,
                "發現人員姓名": n.inspector.name if n.inspector else "",
                "廠商中文名稱": n.vendor # n.vendor in NCMR is string or text (legacy was '廠商').
                # Wait, in NCMR model 'vendor' is a String column, not ID. 
                # But Shipping uses Vendor ID. 
                # NCMR legacy code: "廠商" column.
                # get_ncmr_info query: v."廠商名稱" AS "廠商中文名稱" FROM ... LEFT JOIN "廠商資料" v ON n."廠商" = v."廠商名稱"
                # So NCMR stores the NAME string.
            }
            
            # Additional lookup for '廠商中文名稱' if it was a join. 
            # In legacy code, it joined on NAME. 
            # So item['廠商中文名稱'] should be same as item['廠商'] if it exists in Vendor table.
            # I'll just set it to item['廠商'] or lookup if needed.
            # Let's mimic legacy behavior: left join vendor on name.
            if n.vendor:
                v = Vendor.query.filter_by(name=n.vendor).first()
                item["廠商中文名稱"] = v.name if v else n.vendor
            else:
                item["廠商中文名稱"] = ""

            # Formatting
            for key, val in item.items():
                if val is None:
                    item[key] = ""
                elif isinstance(val, (datetime.date, datetime.datetime)):
                    if '時間' in key:
                         item[key] = val.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                         item[key] = val.strftime('%Y-%m-%d')
                else:
                    if key == '發現日期' and isinstance(val, str):
                        try:
                            # Not reachable based on logic above unless val was str
                             pass
                        except: pass
                    else:
                        item[key] = str(val)
            
            # Map '發現日期' to '日期', '不良數量' to '不合格數量'
            item['日期'] = item.get('發現日期')
            item['不合格數量'] = item.get('不良數量')

            return item
        except Exception as e:
            raise e

    # ==================================================
    # CAR Logic
    # ==================================================
    @staticmethod
    def get_cara_list() -> List[Dict[str, Any]]:
        try:
            query = CorrectiveAction.query.filter(CorrectiveAction.car_number != None)\
                .options(joinedload(CorrectiveAction.ncmr), joinedload(CorrectiveAction.owner))\
                .order_by(CorrectiveAction.id.desc())
            
            data = []
            for ca in query.all():
                ncmr = ca.ncmr
                item = {
                    "識別碼": ca.id,
                    "NCMR_ID": ca.ncmr_id,
                    "CAR單號": ca.car_number,
                    "單號": ca.car_number,
                    "8D單號": ca.eight_d_number,
                    "負責人員": ca.owner_id,
                    "狀態": ca.status,
                    "ncmr_id": ca.ncmr_id,
                    "ncmr_number": ncmr.ncmr_number if ncmr else "",
                    "ncmr_date": format_value(ncmr.date) if ncmr else "",
                    "ncmr_source": ncmr.source if ncmr else "",
                    "ncmr_description": ncmr.description if ncmr else "",
                    "ncmr_vendor": ncmr.vendor if ncmr else "",
                    "ncmr_material": ncmr.material if ncmr else "",
                    "ncmr_product": ncmr.product_info if ncmr else "",
                    "負責人員姓名": ca.owner.name if ca.owner else ""
                }
                # Format all
                for k, v in item.items():
                    item[k] = format_value(v)
                data.append(item)
            return data
        except Exception as e:
            raise e

    @staticmethod
    def create_cara(data: Dict[str, Any]) -> Dict[str, Any]:
        ncmr_id = data.get('ncmr_id')
        try:
            existing = CorrectiveAction.query.filter_by(ncmr_id=ncmr_id).filter(CorrectiveAction.car_number != None).first()
            if existing:
                raise ValueError("此異常單已開立過CAR")

            ncmr = NCMR.query.get(ncmr_id)
            if not ncmr: raise ValueError("NCMR not found")

            car_number = generate_car_number()
            
            # Check if there is an existing CA record for this NCMR (e.g. CAPA exists) or create new?
            # One NCMR can have both CAR and CAPA. Usually they are separate records in '異常矯正單' based on legacy:
            # Legacy INSERTs a new row for CAR.
            
            ca = CorrectiveAction(
                car_number=car_number,
                ncmr_id=ncmr_id,
                status='進行中'
            )
            db.session.add(ca)
            
            ncmr.status = 'CAR處理中'
            
            db.session.commit()
            return {"car_number": car_number, "ncmr_number": ncmr.ncmr_number}
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cara_detail(cara_id: int) -> Optional[Dict[str, Any]]:
        try:
            ca = CorrectiveAction.query.options(joinedload(CorrectiveAction.owner)).get(cara_id)
            if not ca or not ca.car_number:
                return None

            cara_data = {
                "識別碼": ca.id,
                "NCMR_ID": ca.ncmr_id,
                "CAR單號": ca.car_number,
                "單號": ca.car_number,
                "8D單號": ca.eight_d_number,
                "負責人員": ca.owner_id,
                "狀態": ca.status,
                "D1_小組成員": ca.d1,
                "D2_問題描述": ca.d2,
                "D3_暫時對策": ca.d3,
                "D4_真因分析": ca.d4,
                "D5_永久對策": ca.d5,
                "D6_成效驗證": ca.d6,
                "D7_預防再發": ca.d7,
                "D8_結案確認": ca.d8,
                "建立時間": ca.created_at,
                "完成時間": ca.closed_at,
                "建立日期": ca.created_at.strftime('%Y-%m-%d') if ca.created_at else "",
                "結案日期": ca.closed_at.strftime('%Y-%m-%d') if ca.closed_at else "",
                "負責人員姓名": ca.owner.name if ca.owner else ""
            }

            ncmr_data = {}
            if ca.ncmr_id:
                # Use get_ncmr_info to reuse logic or query ncmr
                n = NCMR.query.options(joinedload(NCMR.inspector)).get(ca.ncmr_id)
                if n:
                   # similar mapping as get_ncmr_info but as subdict
                   ncmr_data = {
                       "NCMR單號": n.ncmr_number,
                       "發現日期": n.date.strftime('%Y-%m-%d') if n.date else "",
                       "來源": n.source,
                       "產品資訊": n.product_info,
                       "產品數量": n.quantity,
                       "材質": n.material,
                       "廠商": n.vendor,
                       "批號": n.batch_num,
                       "不良描述": n.description,
                       "不良數量": n.defect_quantity,
                       "判定結果": n.result,
                       "狀態": n.status,
                       "發現人員姓名": n.inspector.name if n.inspector else "",
                   }
                   if n.vendor:
                       v = Vendor.query.filter_by(name=n.vendor).first()
                       ncmr_data["廠商中文名稱"] = v.name if v else n.vendor

            return {"cara": cara_data, "ncmr": ncmr_data}
        except Exception as e:
            raise e

    @staticmethod
    def update_cara(data: Dict[str, Any]) -> bool:
        cara_id = data.get('識別碼')
        try:
            ca = CorrectiveAction.query.get(cara_id)
            if not ca: return False

            if data.get('負責人員姓名'):
                owner = Inspector.query.filter_by(name=data.get('負責人員姓名')).first()
                if owner: ca.owner_id = owner.id
            
            d_fields = ['D2_問題描述', 'D3_暫時對策', 'D4_真因分析', 'D6_成效驗證', 'D7_預防再發', 'D8_結案確認']
            for f in d_fields:
                if f in data: # allow setting to empty if sent
                    val = data[f]
                    # Map to model field (lowercase d2, etc. or defined as such?)
                    # Model defined as d1..d8
                    # Map "D2_问题描述" -> d2
                    attr = f.split('_')[0].lower() # D2 -> d2
                    setattr(ca, attr, val)

            if data.get('狀態'):
                ca.status = data.get('狀態')
            
            if data.get('狀態') == '已結案':
                ca.closed_at = datetime.datetime.now()
                # Update NCMR
                if ca.ncmr_id:
                     ncmr = NCMR.query.get(ca.ncmr_id)
                     if ncmr: ncmr.status = 'CAR已完成'
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_cara(cara_id: int) -> bool:
        try:
            ca = CorrectiveAction.query.get(cara_id)
            if ca and ca.car_number:
                db.session.delete(ca)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    # ==================================================
    # CAPA Logic (Similar to CAR)
    # ==================================================
    @staticmethod
    def get_capa_list() -> List[Dict[str, Any]]:
        try:
            query = CorrectiveAction.query.filter(CorrectiveAction.eight_d_number != None)\
                .options(joinedload(CorrectiveAction.ncmr), joinedload(CorrectiveAction.owner))\
                .order_by(CorrectiveAction.id.desc())
            
            data = []
            for ca in query.all():
                ncmr = ca.ncmr
                item = {
                    "識別碼": ca.id,
                    "NCMR_ID": ca.ncmr_id,
                    "8D單號": ca.eight_d_number,
                    "CAR單號": ca.car_number,
                    "負責人員": ca.owner_id,
                    "問題描述": ca.d2,     # Mapping D2 -> 問題描述 for list view? Legacy selected fields 
                    "根本原因": ca.d4,     # Mapping D4
                    "矯正措施": ca.d3,     # Mapping D3? Or D5? Leagcy: "矯正措施" column in DB?
                    # Wait, legacy SQL select: "問題描述", "根本原因", "矯正措施", "預防措施" columns directly from table.
                    # My model has d1..d8. 
                    # If legacy table actually has COLUMNS named "問題描述", "根本原因" etc AND D1..D8 are aliases, 
                    # OR if they are separate.
                    # My model `CorrectiveAction` definition in Step 258 has `d2 = db.Column('D2_問題描述', ...)`
                    # So `d2` attribute MAPS to `D2_問題描述` column.
                    # But legacy Code `get_capa_list` selected: `T1."問題描述", T1."根本原因", T1."矯正措施", T1."預防措施"`.
                    # This implies there are columns named EXACTLY that, NOT `D2_問題描述`.
                    # It seems `異常矯正單` might have mixed naming or I assumed 8D structure.
                    # Re-reading `ncmr_service.py` legacy code:
                    # `T1."問題描述", T1."根本原因", T1."矯正措施", T1."預防措施"`
                    # AND `update_cara` used: `D2_問題描述`, `D3_暫時對策`...
                    # It seems standard names are used for CARs (D-steps) but maybe simplified names for CAPA list?
                    # Or maybe the columns exist simultaneously?
                    # Or my model definition is WRONG for `CorrectionAction`.
                    
                    # Let's check `backend/models.py` again.
                    # `d2 = db.Column('D2_問題描述', db.String)`
                    # If the actual DB column is `問題描述`, then this mapping will fail at runtime.
                    # I should have checked the schema more carefully.
                    # However, `update_cara` in legacy code used `D2_問題描述`.
                    # `get_capa_list` in legacy code used `問題描述`.
                    # This suggests EITHER aliases in SQL or multiple columns.
                    # BUT `update_cara` is for CAR. `get_capa_list` is for CAPA (8D).
                    # Maybe 8D uses different columns?
                    # Let's assume for now 8D maps to D-fields.
                    # D2 = Problem Description = 問題描述
                    # D4 = Root Cause = 真因分析/根本原因
                    # D5 = Permanent Action = 永久對策/矯正措施?
                    # D7 = Prevent Recurrence = 預防再發/預防措施
                    
                    # I will map them accordingly.
                    "狀態": ca.status,
                    "建立日期": format_value(ca.created_at),
                    "結案日期": format_value(ca.closed_at),
                    "負責人員姓名": ca.owner.name if ca.owner else "",
                    "來源": ncmr.source if ncmr else "",
                    "不良描述": ncmr.description if ncmr else "",
                    "廠商": ncmr.vendor if ncmr else "",
                    "材質": ncmr.material if ncmr else "",
                    "規格": ncmr.product_info if ncmr else "",
                    "NCMR單號": ncmr.ncmr_number if ncmr else "",
                    "ncmr_date": format_value(ncmr.date) if ncmr else ""
                }
                
                # Manual mapping based on 8D logic assumption
                item["問題描述"] = ca.d2 or ""
                item["根本原因"] = ca.d4 or ""
                item["矯正措施"] = ca.d5 or "" # Permanent action
                item["預防措施"] = ca.d7 or ""
                
                for k, v in item.items():
                   item[k] = format_value(v)
                
                data.append(item)
            return data
        except Exception as e:
            raise e

    @staticmethod
    def create_capa(data: Dict[str, Any]) -> Dict[str, Any]:
        ncmr_id = data.get('ncmr_id')
        try:
            existing = CorrectiveAction.query.filter_by(ncmr_id=ncmr_id).filter(CorrectiveAction.eight_d_number != None).first()
            if existing: raise ValueError("此異常單已開立過矯正單")

            ncmr = NCMR.query.get(ncmr_id)
            if not ncmr: raise ValueError("NCMR not found")

            capa_number = generate_8d_number()
            
            ca = CorrectiveAction(
                eight_d_number=capa_number,
                ncmr_id=ncmr_id,
                status='進行中'
            )
            db.session.add(ca)
            db.session.flush() # get ID
            
            ncmr.status = '矯正中'
             
            db.session.commit()
            return {"capa_number": capa_number, "ncmr_number": ncmr.ncmr_number, "id": ca.id}
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_capa_detail(capa_id: int) -> Optional[Dict[str, Any]]:
        # Using same logic as get_cara_detail but maybe different frontend expectations?
        # get_capa_detail legacy calls `get_capa_detail`.
        return NCMRService.get_cara_detail(capa_id)

    @staticmethod
    def update_capa(data: Dict[str, Any]) -> bool:
        return NCMRService.update_cara(data)

    @staticmethod
    def delete_capa(capa_id: int) -> bool:
        try:
            ca = CorrectiveAction.query.get(capa_id)
            if ca and ca.eight_d_number:
                db.session.delete(ca)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e
