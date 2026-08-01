
import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import joinedload, subqueryload
from sqlalchemy import desc
from ..extensions import db
from ..models import NCMR, CorrectiveAction, Inspector, Vendor, PatrolMain, ShippingData, ReworkRequest, ReworkExecution, NcmrDisposition
from ..utils import (
    format_value,
    handle_db_error,
    generate_ncmr_number,
    generate_8d_number,
    validate_status_transition
)

class NCMRService:
    # ==================================================
    # NCMR Logic
    # ==================================================
    @staticmethod
    def get_ncmr_list(
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        date_from: Optional[datetime.date | str] = None,
        date_to: Optional[datetime.date | str] = None,
        source: Optional[str] = None,
        vendor: Optional[str] = None,
        material: Optional[str] = None,
        product_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            query = NCMR.active_query().options(
                joinedload(NCMR.inspector),
                subqueryload(NCMR.corrective_actions),
                subqueryload(NCMR.rework_requests).subqueryload(ReworkRequest.executions)
            )

            if status:
                query = query.filter(NCMR.status == status)
            if date_from:
                query = query.filter(NCMR.date >= _coerce_date(date_from))
            if date_to:
                query = query.filter(NCMR.date <= _coerce_date(date_to))
            if source:
                query = query.filter(NCMR.source == source)
            if vendor:
                query = query.filter(NCMR.vendor.ilike(f'%{vendor}%'))
            if material:
                query = query.filter(NCMR.material.ilike(f'%{material}%'))
            if product_info:
                query = query.filter(NCMR.product_info.ilike(f'%{product_info}%'))

            total = query.count()
            ncmrs = query.order_by(NCMR.id.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()

            data = []
            for n in ncmrs:
                capa_status = None

                capas = [ca for ca in n.corrective_actions if ca.eight_d_number]
                if capas:
                    latest_capa = sorted(capas, key=lambda x: x.id, reverse=True)[0]
                    capa_status = latest_capa.status

                rework_count = 0
                rework_status = None
                if n.rework_requests:
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
                    "CAPA狀態": capa_status,
                    "重工執行次數": rework_count,
                    "重工狀態": rework_status
                }
                data.append(item)

            return {"data": data, "total": total, "page": page, "per_page": per_page}
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
            ncmr = NCMR.active_query().filter_by(id=ncmr_id).first()
            if not ncmr:
                raise ValueError("找不到該筆資料")

            # 狀態轉移驗證
            new_status = data.get('狀態')
            if new_status and new_status != ncmr.status:
                validate_status_transition('NCMR', ncmr.status, new_status)
                ncmr.status = new_status  # 通過驗證後才套用新狀態

            # 結案前置檢查
            if new_status == '已結案':
                # 若有關聯 CAPA，需確認 CAPA 已結案
                open_capas = [ca for ca in ncmr.corrective_actions
                              if ca.deleted_at is None and ca.status != '已結案']
                if open_capas:
                    raise ValueError('CAPA 尚未結案，無法將 NCMR 結案')
                # 若有關聯重工，需確認重工已完成
                open_reworks = [r for r in ncmr.rework_requests
                                if r.deleted_at is None and r.status not in ('已結案', '撤銷')]
                if open_reworks:
                    raise ValueError('尚有未結案的重工申請單，無法將 NCMR 結案')

                # IATF §8.7 處置 gate
                # 注意：NcmrDisposition 無軟刪除，此關聯回傳全部處置
                dispositions = ncmr.dispositions
                if not dispositions:
                    raise ValueError('尚未填寫不合格品處置，無法結案')

                total_disp = sum(int(d.quantity or 0) for d in dispositions)
                defect_total = int(ncmr.defect_quantity or 0)
                if total_disp != defect_total:
                    raise ValueError(
                        f'處置數量加總（{total_disp}）與不良總數（{defect_total}）不符，無法結案'
                    )

                for d in dispositions:
                    if d.disposition_type == '矯正重工':
                        if not d.rework_id:
                            raise ValueError('矯正重工處置須關聯重工單')
                        rw = db.session.get(ReworkRequest, d.rework_id)
                        if not rw or rw.status != '已結案':
                            raise ValueError('關聯重工單尚未結案，無法將 NCMR 結案')
                    elif d.disposition_type == '挑選全檢':
                        if d.pass_qty is None or d.fail_qty is None:
                            raise ValueError('挑選全檢處置須填寫合格數與不合格數')
                        if int(d.pass_qty) + int(d.fail_qty) != int(d.quantity):
                            raise ValueError('挑選全檢的合格數與不合格數加總須等於處置數量')
                    elif d.disposition_type == '讓步放行':
                        # 僅當超出客戶規格時才需授權；未超出屬內部放行、無需授權（依規格 §8.7.1.1 / Q4-Q5）
                        if d.exceed_customer_spec and d.auth_status == '未取得' and not d.unauth_reason:
                            raise ValueError('未授權放行須填寫未授權放行理由')

            if data.get('發現人員姓名'):
                inspector = Inspector.query.filter_by(name=data.get('發現人員姓名')).first()
                if inspector:
                     ncmr.inspector_id = inspector.id

            # Schema 已完成型別轉換；service 僅負責套用正式欄位。
            # 注意：'狀態' 已由上方狀態機驗證區塊單獨處理，
            # 不納入 field_map 以防止被覆蓋為 None 或繞過狀態機驗證
            field_map = {
                '日期': 'date', '建立日期': 'create_date', '來源': 'source', '產品資訊': 'product_info',
                '產品數量': 'quantity', '材質': 'material', '廠商': 'vendor',
                '批號': 'batch_num', '不良描述': 'description',
                '不合格數量': 'defect_quantity', '判定結果': 'result',
                '不良原因大類': 'defect_category',
                '不良原因細項': 'defect_detail'
            }
            
            for key, attr in field_map.items():
                if key in data:
                    setattr(ncmr, attr, data[key])
            
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
            ncmr = NCMR.active_query().filter_by(id=ncmr_id).first()
            if ncmr:
                ncmr.soft_delete()
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
                patrol = db.session.get(PatrolMain, source_id)
                if patrol:
                    vendor_name = ""
                    # Patrol has customer_id linked to Vendor table
                    if patrol.customer_id:
                        v = db.session.get(Vendor, patrol.customer_id)
                        vendor_name = v.name if v else ""
                    
                    info = {
                        "材質": patrol.material,
                        "產品資訊": patrol.spec,
                        "批號": patrol.batch_num,
                        "廠商": vendor_name
                    }
            elif source_type == '出貨檢':
                shipping = db.session.get(ShippingData, source_id)
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
    def get_ncmr_reworks(ncmr_id: int) -> List[Dict[str, Any]]:
        """列出該 NCMR 的重工申請單（供處置關聯選擇）"""
        rows = ReworkRequest.query\
            .filter(ReworkRequest.ncmr_id == ncmr_id)\
            .filter(ReworkRequest.deleted_at.is_(None))\
            .order_by(ReworkRequest.id.desc())\
            .all()
        return [{
            '識別碼': r.id,
            '申請單號': r.rework_number,
            '狀態': r.status,
        } for r in rows]

    # ==================================================
    # 不合格品處置（IATF 16949 §8.7）
    # ==================================================
    @staticmethod
    def _validate_disposition(data: Dict[str, Any]) -> None:
        """處置寫入驗證；不合法拋 ValueError"""
        dtype = data.get('處置類型')
        if dtype not in ('矯正重工', '報廢', '挑選全檢', '讓步放行'):
            raise ValueError(f'無效的處置類型：{dtype!r}')
        if data.get('處置數量') in (None, ''):
            raise ValueError('處置數量為必填')

        if dtype == '挑選全檢':
            pass_qty = data.get('合格數')
            fail_qty = data.get('不合格數')
            if pass_qty is not None and fail_qty is not None:
                try:
                    p, f, total = int(pass_qty), int(fail_qty), int(data['處置數量'])
                except (ValueError, TypeError):
                    raise ValueError('數量格式不合法')
                if p + f != total:
                    raise ValueError('合格數 + 不合格數 必須等於處置數量')

        if dtype == '讓步放行' and data.get('是否超出客戶規格'):
            if not data.get('授權狀態'):
                raise ValueError('超出客戶規格時，授權狀態為必填')
            if data.get('授權狀態') == '未取得' and not data.get('未授權放行理由'):
                raise ValueError('未取得授權時，未授權放行理由為必填')

    @staticmethod
    def get_dispositions(ncmr_id: int) -> List[Dict[str, Any]]:
        rows = NcmrDisposition.query.options(joinedload(NcmrDisposition.handler))\
            .filter_by(ncmr_id=ncmr_id)\
            .order_by(NcmrDisposition.id).all()
        result = []
        for d in rows:
            result.append({
                '識別碼': d.id, 'NCMR_ID': d.ncmr_id,
                '處置類型': d.disposition_type, '處置數量': d.quantity,
                '處置人': d.handler_id, '處置人姓名': d.handler.name if d.handler else '',
                '處置時間': d.handled_at.strftime('%Y-%m-%d %H:%M:%S') if d.handled_at else '',
                '備註': d.note,
                '關聯重工單ID': d.rework_id,
                '合格數': d.pass_qty, '不合格數': d.fail_qty,
                '是否超出客戶規格': d.exceed_customer_spec,
                '授權狀態': d.auth_status, '授權文號': d.auth_doc_no,
                '授權有效期': d.auth_valid_until.strftime('%Y-%m-%d') if d.auth_valid_until else '',
                '授權數量上限': d.auth_max_qty,
                '未授權放行理由': d.unauth_reason, '是否風險項': d.is_risk,
            })
        return result

    @staticmethod
    def _apply_disposition_fields(d: NcmrDisposition, data: Dict[str, Any]) -> None:
        """將輸入資料套用到處置物件（建立/更新共用）"""

        def _to_int(v):
            """將值轉為整數；空值/None 保留為 None；非數字格式拋出友善錯誤"""
            if v in (None, ''):
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                raise ValueError('數量格式不合法')

        d.disposition_type = data['處置類型']
        # 處置數量為必填，直接轉型；非數字時拋出友善錯誤
        try:
            d.quantity = int(data['處置數量'])
        except (ValueError, TypeError):
            raise ValueError('數量格式不合法')
        d.note = data.get('備註')
        d.rework_id = data.get('關聯重工單ID') or None
        d.pass_qty = _to_int(data.get('合格數'))
        d.fail_qty = _to_int(data.get('不合格數'))
        d.exceed_customer_spec = bool(data.get('是否超出客戶規格'))
        d.auth_status = data.get('授權狀態') or None
        d.auth_doc_no = data.get('授權文號') or None
        d.auth_max_qty = _to_int(data.get('授權數量上限'))
        valid = data.get('授權有效期')
        d.auth_valid_until = datetime.datetime.strptime(valid, '%Y-%m-%d').date() if valid else None
        d.unauth_reason = data.get('未授權放行理由') or None
        # 未取得授權 → 自動標記風險項
        d.is_risk = bool(d.exceed_customer_spec and d.auth_status == '未取得')

    @staticmethod
    def create_disposition(ncmr_id: int, data: Dict[str, Any], handler_id: Optional[int]) -> int:
        try:
            ncmr = NCMR.active_query().filter_by(id=ncmr_id).first()
            if not ncmr:
                raise ValueError('找不到該 NCMR')
            NCMRService._validate_disposition(data)
            d = NcmrDisposition(ncmr_id=ncmr_id, handler_id=handler_id)
            NCMRService._apply_disposition_fields(d, data)
            db.session.add(d)
            db.session.commit()
            return d.id
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def update_disposition(disposition_id: int, data: Dict[str, Any]) -> bool:
        try:
            d = db.session.get(NcmrDisposition, disposition_id)
            if not d:
                raise ValueError('找不到該處置記錄')
            NCMRService._validate_disposition(data)
            NCMRService._apply_disposition_fields(d, data)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete_disposition(disposition_id: int) -> bool:
        try:
            d = db.session.get(NcmrDisposition, disposition_id)
            if d:
                db.session.delete(d)
                db.session.commit()
            # 找不到 id 時同樣回傳 True：冪等刪除，符合 RESTful DELETE 語意
            return True
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def get_risk_releases() -> List[Dict[str, Any]]:
        """未授權放行清單（風險項）— IATF §8.7.1.1 風險追蹤"""
        rows = db.session.query(NcmrDisposition, NCMR)\
            .options(joinedload(NcmrDisposition.handler))\
            .join(NCMR, NcmrDisposition.ncmr_id == NCMR.id)\
            .filter(NcmrDisposition.is_risk.is_(True))\
            .filter(NCMR.deleted_at.is_(None))\
            .order_by(NcmrDisposition.handled_at.desc())\
            .all()
        result = []
        for d, n in rows:
            result.append({
                'NCMR單號': n.ncmr_number,
                '產品資訊': n.product_info,
                '材質': n.material,
                '廠商': n.vendor,
                '處置數量': d.quantity,
                '未授權放行理由': d.unauth_reason,
                '處置人姓名': d.handler.name if d.handler else '',
                '處置時間': d.handled_at.strftime('%Y-%m-%d %H:%M:%S') if d.handled_at else '',
            })
        return result

    @staticmethod
    def get_ncmr_info(ncmr_id: int) -> Optional[Dict[str, Any]]:
        try:
            n = NCMR.active_query().options(joinedload(NCMR.inspector)).filter_by(id=ncmr_id).first()
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
    # CAPA Logic
    # ==================================================
    @staticmethod
    def get_capa_list(
        page: int = 1,
        per_page: int = 20,
        date_from: Optional[datetime.date | str] = None,
        date_to: Optional[datetime.date | str] = None,
        vendor: Optional[str] = None,
        material: Optional[str] = None,
        product_info: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            query = CorrectiveAction.query\
                .filter(CorrectiveAction.eight_d_number.isnot(None))\
                .join(NCMR, CorrectiveAction.ncmr_id == NCMR.id)\
                .options(joinedload(CorrectiveAction.ncmr), joinedload(CorrectiveAction.owner))

            if status:
                query = query.filter(CorrectiveAction.status == status)
            if date_from:
                query = query.filter(CorrectiveAction.created_at >= datetime.datetime.combine(_coerce_date(date_from), datetime.time.min))
            if date_to:
                query = query.filter(CorrectiveAction.created_at <= datetime.datetime.combine(_coerce_date(date_to), datetime.time.max))
            if vendor:
                query = query.filter(NCMR.vendor.ilike(f'%{vendor}%'))
            if material:
                query = query.filter(NCMR.material.ilike(f'%{material}%'))
            if product_info:
                query = query.filter(NCMR.product_info.ilike(f'%{product_info}%'))

            total = query.count()
            cas = query.order_by(CorrectiveAction.id.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()

            data = []
            for ca in cas:
                ncmr = ca.ncmr
                item = {
                    "識別碼": ca.id,
                    "NCMR_ID": ca.ncmr_id,
                    "8D單號": ca.eight_d_number,
                    "負責人員": ca.owner_id,
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
                item["問題描述"] = ca.d2 or ""
                item["根本原因"] = ca.d4 or ""
                item["矯正措施"] = ca.d5 or ""
                item["預防措施"] = ca.d7 or ""
                for k, v in item.items():
                    item[k] = format_value(v)
                data.append(item)

            return {"data": data, "total": total, "page": page, "per_page": per_page}
        except Exception as e:
            raise e

    @staticmethod
    def create_capa(data: Dict[str, Any]) -> Dict[str, Any]:
        ncmr_id = data.get('ncmr_id')
        try:
            existing = CorrectiveAction.query.filter_by(ncmr_id=ncmr_id).filter(CorrectiveAction.eight_d_number != None).first()
            if existing: raise ValueError("此異常單已開立過矯正單")

            ncmr = NCMR.active_query().filter_by(id=ncmr_id).first()
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
        """取得 CAPA（8D）詳細資料"""
        try:
            ca = CorrectiveAction.query.options(joinedload(CorrectiveAction.owner)).get(capa_id)
            if not ca or not ca.eight_d_number:
                return None

            capa_data = {
                "識別碼": ca.id,
                "NCMR_ID": ca.ncmr_id,
                "8D單號": ca.eight_d_number,
                "單號": ca.eight_d_number,
                "負責人員": ca.owner_id,
                "狀態": ca.status,
                "D1_小組成員": ca.d1,
                "D2_問題描述": ca.d2,
                "D3_暫時對策": ca.d3,
                "D4_真因分析": ca.d4,
                "D5_永久對策": ca.d5,
                "D6_成效驗證": ca.d6,
                "D7_預防再發": ca.d7,
                "D8_結案確認": ca.d8_confirmation,
                "建立時間": ca.created_at,
                "完成時間": ca.closed_at,
                "建立日期": ca.created_at.strftime('%Y-%m-%d') if ca.created_at else "",
                "結案日期": ca.closed_at.strftime('%Y-%m-%d') if ca.closed_at else "",
                "負責人員姓名": ca.owner.name if ca.owner else ""
            }

            ncmr_data = {}
            if ca.ncmr_id:
                n = NCMR.active_query().options(joinedload(NCMR.inspector)).filter_by(id=ca.ncmr_id).first()
                if n:
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

            return {"capa": capa_data, "ncmr": ncmr_data}
        except Exception as e:
            raise e

    @staticmethod
    def update_capa(data: Dict[str, Any]) -> bool:
        """更新 CAPA（8D）資料"""
        capa_id = data.get('識別碼')
        try:
            ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
            if not ca:
                return False

            if data.get('負責人員姓名'):
                owner = Inspector.query.filter_by(name=data.get('負責人員姓名')).first()
                if owner:
                    ca.owner_id = owner.id

            d_fields = ['D2_問題描述', 'D3_暫時對策', 'D4_真因分析', 'D5_永久對策', 'D6_成效驗證', 'D7_預防再發', 'D8_結案確認']
            for f in d_fields:
                if f in data:
                    val = data[f]
                    attr = f.split('_')[0].lower()  # 例：D2_問題描述 -> d2
                    setattr(ca, attr, val)

            if data.get('狀態'):
                if data.get('狀態') == '已結案' and ca.status != '已結案':
                    raise ValueError('舊版 CAPA 更新不可直接結案，請使用新版 CAPA 結案流程')
                ca.status = data.get('狀態')

            if data.get('狀態') == '已結案':
                ca.closed_at = datetime.datetime.now()
                if ca.ncmr_id:
                    ncmr = NCMR.active_query().filter_by(id=ca.ncmr_id).first()
                    if ncmr:
                        ncmr.status = '矯正完成'

            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_capa(capa_id: int) -> bool:
        try:
            ca = CorrectiveAction.active_query().filter_by(id=capa_id).first()
            if ca and ca.eight_d_number:
                db.session.delete(ca)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e


def _coerce_date(value: datetime.date | str) -> datetime.date:
    """相容 route 已解析的 date 與舊呼叫端傳入的 YYYY-MM-DD 字串。"""
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))
