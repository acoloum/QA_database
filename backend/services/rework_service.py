
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, func
from ..extensions import db
from ..errors import APIError, NotFoundError
from ..models import (
    ReworkRequest, ReworkExecution, ReworkInspection, 
    NCMR, Inspector, CorrectiveAction, CustomerComplaint, ReworkCost
)
from ..utils import (
    format_value,
    generate_number,
    validate_status_transition,
)
from .audit_service import AuditService

class ReworkService:
    @staticmethod
    def _locked_active_request(rework_id: int) -> Optional[ReworkRequest]:
        return db.session.execute(
            db.select(ReworkRequest)
            .where(ReworkRequest.id == rework_id, ReworkRequest.deleted_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    @staticmethod
    def _locked_request_by_number(rework_number: str) -> Optional[ReworkRequest]:
        return db.session.execute(
            db.select(ReworkRequest)
            .where(
                ReworkRequest.rework_number == rework_number,
                ReworkRequest.deleted_at.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    @staticmethod
    def _locked_child(model, child_id: int, not_found_message: str):
        """統一先鎖重工主單、再鎖子資料，避免共用 parent 死鎖順序不一。"""
        rework_id = db.session.execute(
            db.select(model.rework_id).where(model.id == child_id)
        ).scalar_one_or_none()
        if rework_id is None:
            raise NotFoundError(not_found_message)
        request_row = ReworkService._locked_active_request(rework_id)
        if request_row is None:
            raise NotFoundError('找不到重工申請單')
        child = db.session.execute(
            db.select(model)
            .where(model.id == child_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if child is None:
            raise NotFoundError(not_found_message)
        return request_row, child

    @staticmethod
    def _request_snapshot(req: ReworkRequest) -> Dict[str, Any]:
        return {
            'id': req.id,
            'ncmr_id': req.ncmr_id,
            'complaint_id': req.complaint_id,
            'status': req.status,
            'review_status': req.review_status,
            'reviewer_id': req.reviewer_id,
            'deleted_at': req.deleted_at,
            'actual_finish_date': req.actual_finish_date,
        }

    @staticmethod
    def _ncmr_snapshot(ncmr: Optional[NCMR]) -> Optional[Dict[str, Any]]:
        """NCMR 跨模組稽核白名單；不收錄不良描述等自由文字。"""
        if ncmr is None:
            return None
        return {
            'module': 'NCMR',
            'id': ncmr.id,
            'status': ncmr.status,
            'related_capa_id': ncmr.related_capa_id,
            'related_capa_source': ncmr.related_capa_source,
            'deleted_at': ncmr.deleted_at,
        }

    @staticmethod
    def _complaint_snapshot(
        complaint: Optional[CustomerComplaint],
    ) -> Optional[Dict[str, Any]]:
        """客訴跨模組稽核白名單；不收錄客訴內容等自由文字。"""
        if complaint is None:
            return None
        return {
            'module': '客訴',
            'id': complaint.id,
            'status': complaint.status,
            'related_capa_id': complaint.related_capa_id,
            'related_rework_id': complaint.related_rework_id,
            'deleted_at': complaint.deleted_at,
        }

    @staticmethod
    def _child_snapshot(item) -> Dict[str, Any]:
        fields = {
            ReworkExecution: ('id', 'rework_id', 'dept', 'owner_id', 'complete_qty', 'defect_qty', 'yield_rate', 'status'),
            ReworkInspection: ('id', 'rework_id', 'date', 'inspector_id', 'item', 'result', 'defect_qty'),
            ReworkCost: ('id', 'rework_id', 'cost_type', 'cost_item', 'unit_cost', 'quantity', 'total_cost', 'currency'),
        }[type(item)]
        return {field: getattr(item, field) for field in fields}

    def generate_rework_number(self):
        """生成重工單號"""
        return generate_number('RW', "重工申請單", "申請單號")

    @staticmethod
    def get_statistics(args: Dict[str, Any]) -> Dict[str, Any]:
        """獲取重工統計數據"""
        try:
            query = ReworkRequest.active_query()

            if args.get('start_date'):
                query = query.filter(ReworkRequest.created_at >= args['start_date'])
            if args.get('end_date'):
                query = query.filter(ReworkRequest.created_at <= args['end_date'])

            # Application stats
            total = query.count()
            completed = query.filter(ReworkRequest.status.in_(['已結案', '已完成'])).count()
            in_progress = query.filter(ReworkRequest.status == '執行中').count()
            approved = query.filter(ReworkRequest.status == '已核准').count()
            rejected = query.filter(ReworkRequest.review_status == '已拒絕').count()

            qty_query = db.session.query(func.sum(ReworkRequest.quantity)).filter(
                ReworkRequest.deleted_at.is_(None)
            )
            if args.get('start_date'):
                qty_query = qty_query.filter(ReworkRequest.created_at >= args['start_date'])
            if args.get('end_date'):
                qty_query = qty_query.filter(ReworkRequest.created_at <= args['end_date'])
            total_qty = qty_query.scalar() or 0

            # Department stats
            dept_query = db.session.query(
                ReworkRequest.department,
                func.count(ReworkRequest.id).label('count'),
                func.sum(ReworkRequest.quantity).label('quantity')
            ).filter(ReworkRequest.deleted_at.is_(None))
            if args.get('start_date'):
                dept_query = dept_query.filter(ReworkRequest.created_at >= args['start_date'])
            if args.get('end_date'):
                dept_query = dept_query.filter(ReworkRequest.created_at <= args['end_date'])

            dept_results = dept_query.group_by(ReworkRequest.department).all()

            dept_stats = []
            for row in dept_results:
                dept_stats.append({
                    'department': row[0] or '',
                    'count': row[1],
                    'quantity': float(row[2]) if row[2] else 0
                })

            # Cost stats
            cost_query = db.session.query(
                func.count(ReworkCost.id).label('total_records'),
                func.sum(ReworkCost.total_cost).label('total_cost')
            )
            
            labor_query = cost_query
            material_query = cost_query
            equipment_query = cost_query
            
            cost_result = cost_query.first()
            labor_result = labor_query.filter(ReworkCost.cost_type == '人工成本').first()
            material_result = material_query.filter(ReworkCost.cost_type == '材料成本').first()
            equipment_result = equipment_query.filter(ReworkCost.cost_type == '設備成本').first()

            return {
                'application_stats': {
                    'total_applications': total,
                    'completed': completed,
                    'in_progress': in_progress,
                    'approved': approved,
                    'rejected': rejected,
                    'total_rework_quantity': float(total_qty) if total_qty else 0
                },
                'cost_stats': {
                    'total_records': cost_result[0] if cost_result and cost_result[0] else 0,
                    'total_cost': float(cost_result[1]) if cost_result and cost_result[1] else 0,
                    'labor_cost': float(labor_result[1]) if labor_result and labor_result[1] else 0,
                    'material_cost': float(material_result[1]) if material_result and material_result[1] else 0,
                    'equipment_cost': float(equipment_result[1]) if equipment_result and equipment_result[1] else 0
                },
                'department_stats': dept_stats
            }
        except Exception as e:
            raise e

    @staticmethod
    def get_application_list(args: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            query = ReworkRequest.active_query().options(
                joinedload(ReworkRequest.applicant),
                joinedload(ReworkRequest.reviewer),
                joinedload(ReworkRequest.ncmr)
            )

            if args.get('rework_id'):
                query = query.filter(ReworkRequest.id == args['rework_id'])
            if args.get('status'):
                query = query.filter(ReworkRequest.status == args['status'])
            if args.get('start_date'):
                query = query.filter(ReworkRequest.created_at >= args['start_date'])
            if args.get('end_date'):
                query = query.filter(ReworkRequest.created_at <= args['end_date'])

            query = query.order_by(ReworkRequest.created_at.desc())
            
            requests = query.all()
            data = []
            for r in requests:
                ncmr = r.ncmr
                item = {
                    "識別碼": r.id,
                    "NCMR_ID": r.ncmr_id,
                    "申請單號": r.rework_number,
                    "申請人員": r.applicant_id,
                    "部門": r.department,
                    "緊急程度": r.urgency,
                    "產品資訊": r.product_info,
                    "批號": r.batch_num,
                    "重工數量": r.quantity,
                    "申請原因": r.reason,
                    "預計完成日期": r.expected_date,
                    "狀態": r.status,
                    "審核狀態": r.review_status,
                    "審核人員": r.reviewer_id,
                    "審核時間": r.review_time,
                    "審核意見": r.review_opinion,
                    "申請日期": r.created_at,
                    "實際完成日期": r.actual_finish_date,
                    "申請人員姓名": r.applicant.name if r.applicant else "",
                    "審核人員姓名": r.reviewer.name if r.reviewer else "",
                    "ncmr_description": ncmr.description if ncmr else "",
                    "ncmr_number": ncmr.ncmr_number if ncmr else "",
                    "廠商": r.vendor if r.vendor else (ncmr.vendor if ncmr else ""),
                    "材質": r.material if r.material else (ncmr.material if ncmr else ""),
                    # "產品資訊" already in ReworkRequest, but also in NCMR.
                    # Legacy query selected n."產品資訊" AS "產品資訊" but Rework also has "產品資訊" column.
                    # Legacy code selected r.* then overwritten by n."產品資訊" if collision?
                    # Actually `product_info` is in ReworkRequest too.
                    "客訴_ID": r.complaint_id,
                }
                # Format
                for k, v in item.items():
                    item[k] = format_value(v)
                data.append(item)

            # 補上客訴單號（從 CustomerComplaint 反查，避免 N+1 改為批量查詢）
            from ..models import CustomerComplaint
            complaint_ids = [r.complaint_id for r in requests if r.complaint_id]
            if complaint_ids:
                complaints = {
                    c.id: c.complaint_no
                    for c in CustomerComplaint.query.filter(CustomerComplaint.id.in_(complaint_ids)).all()
                }
                for item in data:
                    cid = item.get("客訴_ID")
                    if cid:
                        item["客訴單號"] = complaints.get(cid, "")

            return data
        except Exception as e:
            raise e

    @staticmethod
    def create_application(data: Dict[str, Any], *, actor_id: Optional[int]) -> Dict[str, Any]:
        try:
            ncmr_id = data.get('NCMR_ID')
            ncmr = db.session.execute(
                db.select(NCMR)
                .where(NCMR.id == ncmr_id, NCMR.deleted_at.is_(None))
                .with_for_update()
                .execution_options(populate_existing=True)
            ).scalar_one_or_none()
            if not ncmr:
                raise NotFoundError("找不到對應的NCMR記錄")
            old_source = ReworkService._ncmr_snapshot(ncmr)

            applicant = Inspector.query.filter_by(name=data.get('申請人員姓名')).first()
            if not applicant: raise ValueError("找不到申請人員")

            rework_number = generate_number('RW', "重工申請單", "申請單號")
            
            # Default product info from NCMR if not provided?
            # Legacy code selected from NCMR and inserted.
            product_info = ncmr.product_info or ''
            
            req = ReworkRequest(
                ncmr_id=ncmr_id,
                rework_number=rework_number,
                applicant_id=applicant.id,
                department=data.get('部門', ''),
                urgency=data.get('緊急程度', '普通'),
                product_info=product_info,
                batch_num=data.get('批號', ''),
                quantity=data.get('重工數量'),
                reason=data.get('申請原因'),
                expected_date=data.get('預計完成日期') or None,
                status='申請中',
                vendor=data.get('廠商') or (ncmr.vendor if ncmr else None),
                material=data.get('材質') or (ncmr.material if ncmr else None),
            )
            
            db.session.add(req)
            db.session.flush()
            
            ncmr.status = '轉重工'
            result = {"rework_id": req.id, "ncmr_number": ncmr.ncmr_number}
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='重工',
                record_id=req.id,
                old_value={'rework': None, 'source': old_source},
                new_value={
                    'rework': ReworkService._request_snapshot(req),
                    'source': ReworkService._ncmr_snapshot(ncmr),
                },
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def _create_from_complaint(complaint) -> Dict[str, Any]:
        """建立客訴來源重工單；不 commit，由外層交易擁有者決定。"""
        from ..models import CustomerComplaint
        if not isinstance(complaint, CustomerComplaint):
            raise ValueError('無效的客訴物件')
        rework_number = generate_number('RW', "重工申請單", "申請單號")
        req = ReworkRequest(
            ncmr_id=None,
            complaint_id=complaint.id,
            rework_number=rework_number,
            applicant_id=None,
            product_info=f'{complaint.material or ""} {complaint.spec or ""} / {complaint.customer}'.strip(),
            reason=complaint.description,
            urgency='普通',
            department='',
            status='申請中',
            material=complaint.material,
        )
        db.session.add(req)
        db.session.flush()
        return {'rework_id': req.id, 'rework_number': req.rework_number}

    @staticmethod
    def create_from_complaint(complaint) -> Dict[str, Any]:
        """保留既有公開介面；新的跨 service 流程使用不 commit builder。"""
        try:
            result = ReworkService._create_from_complaint(complaint)
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def update_application(rework_id: int, data: Dict[str, Any]) -> bool:
        try:
            req = ReworkRequest.active_query().filter_by(id=rework_id).first()
            if not req: raise ValueError("找不到重工申請單")

            # 狀態機驗證
            new_status = data.get('status') or data.get('狀態')
            if new_status and new_status != req.status:
                validate_status_transition('重工', req.status, new_status)
                req.status = new_status

            mapping = {
                '部門': 'department', '緊急程度': 'urgency', '產品資訊': 'product_info',
                '批號': 'batch_num', '重工數量': 'quantity', '申請原因': 'reason',
                '預計完成日期': 'expected_date',
                '廠商': 'vendor', '材質': 'material',
            }

            # 申請人員姓名 -> applicant_id 反查
            if '申請人員姓名' in data:
                applicant_name = (data.get('申請人員姓名') or '').strip()
                if applicant_name:
                    applicant = Inspector.query.filter_by(name=applicant_name).first()
                    if not applicant:
                        raise ValueError(f"找不到申請人員：{applicant_name}")
                    req.applicant_id = applicant.id
                else:
                    req.applicant_id = None
            # Note: Legacy updated '廠商', '材質' in ReworkRequest? 
            # ReworkRequest model doesn't have 'vendor' or 'material'. 
            # Legacy update SQL had them in field_mapping but maybe they don't exist in table?
            # Or the table has extra columns not in my model?
            # Reviewing `backend/routes/rework.py`: field_mapping keys '廠商', '材質'.
            # BUT `models.py` ReworkRequest does NOT have them.
            # I should double check if I missed them or if they are legacy artifacts.
            # If they are in DB but not in Model, ORM won't update them.
            # Assuming they are not critical or redundant (stored in NCMR).
            
            for k, attr in mapping.items():
                if k in data:
                    val = data[k]
                    if k == '預計完成日期' and val == '': val = None
                    setattr(req, attr, val)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def approve_application(data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            rework_id = data.get('rework_id')
            action = data.get('action')
            reviewer_name = data.get('審核人員姓名')
            
            req = ReworkService._locked_active_request(rework_id)
            if not req:
                raise NotFoundError("找不到重工申請單")
            old_value = ReworkService._request_snapshot(req)

            reviewer = Inspector.query.filter_by(name=reviewer_name).first()
            
            if action == '核准':
                new_status = '已核准'
            elif action == '拒絕':
                new_status = '已拒絕'
            else:
                raise ValueError("無效的審核動作")

            validate_status_transition('重工', req.status, new_status)
            req.review_status = new_status
            req.status = new_status
            req.reviewer_id = reviewer.id if reviewer else None
            req.review_time = datetime.now()
            req.review_opinion = data.get('opinion', '')
            AuditService.record(
                actor_id=actor_id,
                action='approve' if action == '核准' else 'reject',
                module='重工',
                record_id=req.id,
                old_value=old_value,
                new_value=ReworkService._request_snapshot(req),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_execution_list(rework_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query = ReworkExecution.query.options(
                joinedload(ReworkExecution.owner),
                joinedload(ReworkExecution.executor)
            )
            
            if rework_id:
                try:
                    req_id = int(rework_id)
                    query = query.filter(ReworkExecution.rework_id == req_id)
                except (ValueError, TypeError):
                    if str(rework_id).startswith('RW'):
                        req = ReworkRequest.query.filter_by(rework_number=rework_id).first()
                        if req:
                            query = query.filter(ReworkExecution.rework_id == req.id)
            
            query = query.order_by(ReworkExecution.id.desc())
            
            executions = query.all()
            data = []
            for e in executions:
                item = {
                    "識別碼": e.id,
                    "重工單號": e.rework_id,
                    "執行部門": e.dept,
                    "負責人員": e.owner_id,
                    "協同人員": e.participants,
                    # 保留完整時間（format_value 只回傳日期會遺失時分，導致前端顯示為 UTC 午夜 08:00）
                    "開始時間": e.start_time.strftime('%Y-%m-%d %H:%M:%S') if e.start_time else "",
                    "預計完成時間": e.est_end_time.strftime('%Y-%m-%d %H:%M:%S') if e.est_end_time else "",
                    "實際完成時間": e.real_end_time.strftime('%Y-%m-%d %H:%M:%S') if e.real_end_time else "",
                    "使用設備": e.equipment,
                    "重工方式": e.method,
                    "SOP編號": e.sop_num,
                    "耗材記錄": e.consumables,
                    "完成數量": e.complete_qty,
                    "不良數量": e.defect_qty,
                    "良率": e.yield_rate,
                    "執行狀況": e.status,
                    "異常狀況": e.abnormal,
                    "執行人員": e.executor_id,
                    "負責人員姓名": e.owner.name if e.owner else "",
                    "執行人員姓名": e.executor.name if e.executor else ""
                }
                data.append(item)
            return data
        except Exception as e:
            raise e

    @staticmethod
    def create_execution(data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            executor = Inspector.query.filter_by(name=data.get('負責人員姓名')).first()
            if not executor: raise ValueError("找不到負責人員")

            rework_number = data.get('重工單號')
            req = ReworkService._locked_request_by_number(rework_number)
            if not req:
                raise NotFoundError("找不到重工申請單")

            # Calculate Yield
            comp = float(data.get('完成數量', 0) or 0)
            defect = float(data.get('不良數量', 0) or 0)
            yield_rate = ((comp - defect) / comp * 100) if comp > 0 else None

            # Date parsing
            def parse_dt(s):
                if not s: return None
                s = s.replace('T', ' ')
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
                    try:
                        return datetime.strptime(s, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"時間格式錯誤：{s}")
            
            start_time = parse_dt(data.get('開始時間')) if data.get('開始時間') else None
            est_end = parse_dt(data.get('預計完成時間')) if data.get('預計完成時間') else None
            real_end = parse_dt(data.get('實際完成時間')) if data.get('實際完成時間') else None

            execution = ReworkExecution(
                rework_id=req.id,
                dept=data.get('執行部門', ''),
                owner_id=executor.id,
                participants=data.get('協同人員', ''),
                start_time=start_time,
                est_end_time=est_end,
                real_end_time=real_end,
                equipment=data.get('使用設備', ''),
                method=data.get('重工方式', ''),
                sop_num=data.get('SOP編號', ''),
                consumables=data.get('耗材記錄', ''),
                complete_qty=comp,
                defect_qty=defect,
                yield_rate=yield_rate,
                status=data.get('執行狀況', ''),
                abnormal=data.get('異常狀況', ''),
                executor_id=executor.id # Using same ID for now as per legacy code logic (executor_id passed as owner_id?)
                # Legacy: 
                # INSERT ... VALUES (..., executor_id) -> executor_id came from `data.get('負責人員姓名')` lookup
            )

            if req.status in ('申請中', '已核准'):
                validate_status_transition('重工', req.status, '執行中')
                req.status = '執行中'
            elif req.status != '執行中':
                raise ValueError(f'狀態為 {req.status} 的重工單不可新增執行記錄')
            db.session.add(execution)
            db.session.flush()
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='重工執行',
                record_id=execution.id,
                new_value=ReworkService._child_snapshot(execution),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_execution(execution_id: int) -> Optional[Dict[str, Any]]:
        try:
            e = ReworkExecution.query.options(joinedload(ReworkExecution.owner), joinedload(ReworkExecution.executor)).get(execution_id)
            if not e: return None
            return {
                "識別碼": e.id,
                "重工單號": e.rework_id,
                "執行部門": e.dept,
                "負責人員": e.owner_id,
                "協同人員": e.participants,
                "開始時間": e.start_time, # DateTime
                "預計完成時間": e.est_end_time,
                "實際完成時間": e.real_end_time,
                "使用設備": e.equipment,
                "重工方式": e.method,
                "SOP編號": e.sop_num,
                "耗材記錄": e.consumables,
                "完成數量": e.complete_qty,
                "不良數量": e.defect_qty,
                "良率": e.yield_rate,
                "執行狀況": e.status,
                "異常狀況": e.abnormal,
                "執行人員": e.executor_id,
                "負責人員姓名": e.owner.name if e.owner else "",
                "執行人員姓名": e.executor.name if e.executor else ""
            }
        except Exception as e:
            raise e

    @staticmethod
    def update_execution(execution_id: int, data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            _, e = ReworkService._locked_child(ReworkExecution, execution_id, "找不到執行記錄")
            old_value = ReworkService._child_snapshot(e)

            if data.get('負責人員姓名'):
                owner = Inspector.query.filter_by(name=data.get('負責人員姓名')).first()
                if owner: e.owner_id = owner.id
            
            mapping = {
                '執行部門': 'dept', '協同人員': 'participants', 
                '使用設備': 'equipment', '重工方式': 'method', 'SOP編號': 'sop_num',
                '耗材記錄': 'consumables', '完成數量': 'complete_qty', 
                '不良數量': 'defect_qty', '執行狀況': 'status', '異常狀況': 'abnormal'
            }
            
            for k, attr in mapping.items():
                if k in data: setattr(e, attr, data[k])

            # Dates
            def parse_dt(s):
                if not s: return None
                s = s.replace('T', ' ')
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
                    try:
                        return datetime.strptime(s, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"時間格式錯誤：{s}")
            
            if '開始時間' in data: e.start_time = parse_dt(data['開始時間'])
            if '預計完成時間' in data: e.est_end_time = parse_dt(data['預計完成時間'])
            if '實際完成時間' in data: e.real_end_time = parse_dt(data['實際完成時間'])
            
            AuditService.record(
                actor_id=actor_id,
                action='update',
                module='重工執行',
                record_id=e.id,
                old_value=old_value,
                new_value=ReworkService._child_snapshot(e),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_execution(execution_id: int, *, actor_id: Optional[int]) -> bool:
        try:
            _, e = ReworkService._locked_child(ReworkExecution, execution_id, "找不到執行記錄")
            old_value = ReworkService._child_snapshot(e)
            db.session.delete(e)
            AuditService.record(
                actor_id=actor_id,
                action='delete',
                module='重工執行',
                record_id=e.id,
                old_value=old_value,
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_inspection_list(rework_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query = ReworkInspection.query
            
            if rework_id:
                try:
                    req_id = int(rework_id)
                    query = query.filter(ReworkInspection.rework_id == req_id)
                except (ValueError, TypeError):
                    if str(rework_id).startswith('RW'):
                        req = ReworkRequest.query.filter_by(rework_number=rework_id).first()
                        if req:
                            query = query.filter(ReworkInspection.rework_id == req.id)
            
            query = query.order_by(ReworkInspection.id.desc())
            
            data = []
            for i in query.all():
                inspector = db.session.get(Inspector, i.inspector_id) if i.inspector_id else None
                item = {
                    "識別碼": i.id,
                    "重工單號": i.rework_id,
                    "檢驗日期": format_value(i.date),
                    "檢驗人員": i.inspector_id,
                    "檢驗項目": i.item,
                    "檢驗標準": i.standard,
                    "檢驗結果": i.result,
                    "不良數量": i.defect_qty,
                    "檢驗備註": i.remark,
                    "建立時間": format_value(i.created_at),
                    "檢驗人員姓名": inspector.name if inspector else ""
                }
                data.append(item)
            return data
        except Exception as e:
            raise e
            
    @staticmethod
    def create_inspection(data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            req = ReworkService._locked_request_by_number(data.get('重工單號'))
            if not req:
                raise NotFoundError("找不到重工申請單")

            inspector = Inspector.query.filter_by(name=data.get('檢驗人員姓名')).first()
            if not inspector: raise ValueError("找不到檢驗人員")
            
            insp = ReworkInspection(
                rework_id=req.id,
                date=data.get('檢驗日期'),
                inspector_id=inspector.id,
                item=data.get('檢驗項目', ''),
                standard=data.get('檢驗標準', ''),
                result=data.get('檢驗結果', '合格'),
                defect_qty=data.get('不良數量', 0),
                remark=data.get('檢驗備註', '')
            )
            db.session.add(insp)
            db.session.flush()
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='重工品檢',
                record_id=insp.id,
                new_value=ReworkService._child_snapshot(insp),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_inspection(inspection_id: int) -> Optional[Dict[str, Any]]:
        try:
            i = ReworkInspection.query.options(joinedload(ReworkInspection.inspector)).get(inspection_id)
            if not i: return None
            return {
                "識別碼": i.id,
                "重工單號": i.rework_id,
                "檢驗日期": i.date.strftime('%Y-%m-%d') if i.date else None,
                "檢驗人員": i.inspector_id,
                "檢驗項目": i.item,
                "檢驗標準": i.standard,
                "檢驗結果": i.result,
                "不良數量": i.defect_qty,
                "檢驗備註": i.remark,
                "建立時間": i.created_at.strftime('%Y-%m-%d %H:%M:%S') if i.created_at else None,
                "檢驗人員姓名": i.inspector.name if i.inspector else ""
            }
        except Exception as e:
            raise e

    @staticmethod
    def update_inspection(inspection_id: int, data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            _, i = ReworkService._locked_child(ReworkInspection, inspection_id, "找不到品檢記錄")
            old_value = ReworkService._child_snapshot(i)
            
            if data.get('檢驗人員姓名'):
                inspector = Inspector.query.filter_by(name=data.get('檢驗人員姓名')).first()
                if inspector: i.inspector_id = inspector.id

            mapping = {
                '檢驗日期': 'date', '檢驗項目': 'item', '檢驗標準': 'standard',
                '檢驗結果': 'result', '不良數量': 'defect_qty', '檢驗備註': 'remark'
            }
            
            for k, attr in mapping.items():
                if k in data: setattr(i, attr, data[k])
            
            AuditService.record(
                actor_id=actor_id,
                action='update',
                module='重工品檢',
                record_id=i.id,
                old_value=old_value,
                new_value=ReworkService._child_snapshot(i),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_inspection(inspection_id: int, *, actor_id: Optional[int]) -> bool:
        try:
            _, i = ReworkService._locked_child(ReworkInspection, inspection_id, "找不到品檢記錄")
            old_value = ReworkService._child_snapshot(i)
            db.session.delete(i)
            AuditService.record(
                actor_id=actor_id,
                action='delete',
                module='重工品檢',
                record_id=i.id,
                old_value=old_value,
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def close_rework(data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            rework_id = data.get('rework_id')
            req = ReworkService._locked_active_request(rework_id)
            if not req:
                raise NotFoundError("找不到該重工單")
            old_request = ReworkService._request_snapshot(req)

            if req.status == '已結案':
                raise APIError("該重工單已結案", code='INVALID_STATE', status_code=409)
            if not ReworkService._has_passed_final_inspection(req):
                raise ValueError("重工結案前必須至少有一筆品檢合格且不良數為 0 的品檢記錄")

            validate_status_transition('重工', req.status, '已結案')
            req.status = '已結案'
            req.actual_finish_date = datetime.now()

            # 重工完成時自動同步 NCMR（無關聯 CAPA 時）
            if req.ncmr_id:
                ncmr = db.session.execute(
                    db.select(NCMR)
                    .where(NCMR.id == req.ncmr_id, NCMR.deleted_at.is_(None))
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).scalar_one_or_none()
                old_source = ReworkService._ncmr_snapshot(ncmr)
                if ncmr and ncmr.status == '矯正中':
                    # 只有在 NCMR 沒有任何 CAPA（或全部已結案）時才自動結案
                    open_capas = [
                        ca for ca in ncmr.corrective_actions
                        if ca.deleted_at is None and ca.status != '已結案'
                    ]
                    if not open_capas:
                        ncmr.status = '矯正完成'
            else:
                ncmr = None
                old_source = None

            AuditService.record(
                actor_id=actor_id,
                action='close',
                module='重工',
                record_id=req.id,
                old_value={'rework': old_request, 'source': old_source},
                new_value={
                    'rework': ReworkService._request_snapshot(req),
                    'source': ReworkService._ncmr_snapshot(ncmr),
                },
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def _has_passed_final_inspection(req: ReworkRequest) -> bool:
        for inspection in req.inspections:
            result = (inspection.result or '').strip()
            defect_qty = inspection.defect_qty or 0
            if '合格' in result and '不合格' not in result and defect_qty <= 0:
                return True
        return False

    @staticmethod
    def delete_rework(rework_id: int, *, actor_id: Optional[int]) -> bool:
        try:
            req = ReworkService._locked_active_request(rework_id)
            if not req:
                raise NotFoundError("找不到重工申請單")
            complaint = None
            if req.complaint_id:
                complaint = db.session.execute(
                    db.select(CustomerComplaint)
                    .where(
                        CustomerComplaint.id == req.complaint_id,
                        CustomerComplaint.deleted_at.is_(None),
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).scalar_one_or_none()
            old_value = {
                'rework': ReworkService._request_snapshot(req),
                'source': ReworkService._complaint_snapshot(complaint),
            }

            # 軟刪除申請單（保留相關執行/品檢/成本記錄）
            req.soft_delete()
            if complaint and complaint.related_rework_id == req.id:
                complaint.related_rework_id = None
                complaint.status = '處理中' if complaint.related_capa_id else '待處理'
            AuditService.record(
                actor_id=actor_id,
                action='delete',
                module='重工',
                record_id=req.id,
                old_value=old_value,
                new_value={
                    'rework': ReworkService._request_snapshot(req),
                    'source': ReworkService._complaint_snapshot(complaint),
                },
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cost_list(rework_number: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query = ReworkCost.query.options(joinedload(ReworkCost.recorder))
            
            if rework_number:
                req = ReworkRequest.query.filter_by(rework_number=rework_number).first()
                if req:
                    query = query.filter(ReworkCost.rework_id == req.id)
            
            query = query.order_by(ReworkCost.created_at.desc())
            
            data = []
            for c in query.all():
                item = {
                    "識別碼": c.id,
                    "重工單號": c.rework_id,
                    "成本類型": c.cost_type,
                    "成本項目": c.cost_item,
                    "單位成本": c.unit_cost,
                    "數量": c.quantity,
                    "總成本": c.total_cost,
                    "成本幣別": c.currency,
                    "記錄人員": c.recorder_id,
                    "記錄人員姓名": c.recorder.name if c.recorder else "",
                    "備註": c.remark,
                    "記錄日期": format_value(c.created_at)
                }
                data.append(item)
            return data
        except Exception as e:
            raise e

    @staticmethod
    def create_cost(data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            rework_number = data.get('重工單號')
            req = ReworkService._locked_request_by_number(rework_number)
            if not req:
                raise NotFoundError("找不到重工申請單")

            recorder = Inspector.query.filter_by(name=data.get('記錄人員姓名')).first()
            if not recorder: raise ValueError("找不到記錄人員")

            unit_cost = float(data.get('單位成本', 0) or 0)
            quantity = float(data.get('數量', 0) or 0)
            total_cost = unit_cost * quantity

            cost = ReworkCost(
                rework_id=req.id,
                cost_type=data.get('成本類型'),
                cost_item=data.get('成本項目'),
                unit_cost=unit_cost,
                quantity=quantity,
                total_cost=total_cost,
                currency=data.get('成本幣別', 'TWD'),
                recorder_id=recorder.id,
                remark=data.get('備註', '')
            )
            db.session.add(cost)
            db.session.flush()
            AuditService.record(
                actor_id=actor_id,
                action='create',
                module='重工成本',
                record_id=cost.id,
                new_value=ReworkService._child_snapshot(cost),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_cost(cost_id: int) -> Optional[Dict[str, Any]]:
        try:
            c = ReworkCost.query.options(joinedload(ReworkCost.recorder)).get(cost_id)
            if not c: return None
            return {
                "識別碼": c.id,
                "重工單號": c.rework_id,
                "成本類型": c.cost_type,
                "成本項目": c.cost_item,
                "單位成本": c.unit_cost,
                "數量": c.quantity,
                "總成本": c.total_cost,
                "成本幣別": c.currency,
                "記錄人員": c.recorder_id,
                "記錄人員姓名": c.recorder.name if c.recorder else "",
                "備註": c.remark,
                "記錄日期": format_value(c.record_date)
            }
        except Exception as e:
            raise e

    @staticmethod
    def update_cost(cost_id: int, data: Dict[str, Any], *, actor_id: Optional[int]) -> bool:
        try:
            _, c = ReworkService._locked_child(ReworkCost, cost_id, "找不到成本記錄")
            old_value = ReworkService._child_snapshot(c)

            if data.get('記錄人員姓名'):
                recorder = Inspector.query.filter_by(name=data.get('記錄人員姓名')).first()
                if recorder:
                    c.recorder_id = recorder.id

            c.cost_type = data.get('成本類型', c.cost_type)
            c.cost_item = data.get('成本項目', c.cost_item)
            c.unit_cost = float(data.get('單位成本', c.unit_cost or 0) or 0)
            c.quantity = float(data.get('數量', c.quantity or 0) or 0)
            c.total_cost = c.unit_cost * c.quantity
            c.currency = data.get('成本幣別', c.currency)
            c.remark = data.get('備註', c.remark)

            AuditService.record(
                actor_id=actor_id,
                action='update',
                module='重工成本',
                record_id=c.id,
                old_value=old_value,
                new_value=ReworkService._child_snapshot(c),
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_cost(cost_id: int, *, actor_id: Optional[int]) -> bool:
        try:
            _, c = ReworkService._locked_child(ReworkCost, cost_id, "找不到成本記錄")
            old_value = ReworkService._child_snapshot(c)
            db.session.delete(c)
            AuditService.record(
                actor_id=actor_id,
                action='delete',
                module='重工成本',
                record_id=c.id,
                old_value=old_value,
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e
