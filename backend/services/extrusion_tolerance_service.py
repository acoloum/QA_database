from typing import Dict, Any
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import ExtrusionToleranceMain, ExtrusionToleranceDetail
from ..utils import format_value


class ExtrusionToleranceService:

    @staticmethod
    def _normalize_spec(s: str) -> str:
        """標準化規格字串（統一分隔符號）"""
        if not s:
            return ''
        s = str(s).strip().replace('×', '*').replace('x', '*').replace('X', '*')
        while '**' in s:
            s = s.replace('**', '*')
        return s.strip()

    @staticmethod
    def search(args: Dict[str, Any]) -> Dict[str, Any]:
        """列表查詢（分頁）"""
        query = ExtrusionToleranceMain.query
        if args.get('material'):
            query = query.filter(ExtrusionToleranceMain.material.like(f"%{args['material']}%"))
        if args.get('spec'):
            query = query.filter(ExtrusionToleranceMain.spec.like(f"%{args['spec']}%"))

        page = int(args.get('page', 1))
        page_size = int(args.get('page_size', 20))
        total = query.count()
        pagination = query.order_by(ExtrusionToleranceMain.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        data = [
            {
                "識別碼": t.id,
                "材質": t.material,
                "規格": t.spec or '',
                "備註": t.note or '',
                "建立日期": format_value(t.created_at),
            }
            for t in pagination.items
        ]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": pagination.pages}

    @staticmethod
    def get_detail(tolerance_id: int) -> Dict[str, Any]:
        """取得單筆主檔 + 明細"""
        t = ExtrusionToleranceMain.query.options(
            joinedload(ExtrusionToleranceMain.details)
        ).get(tolerance_id)
        if not t:
            raise ValueError("找不到該筆擠壓公差資料")

        main = {
            "識別碼": t.id,
            "材質": t.material,
            "規格": t.spec or '',
            "備註": t.note or '',
            "建立日期": format_value(t.created_at),
        }
        details = [
            {
                "識別碼": d.id,
                "測量項目": d.item,
                "測量位置": d.position or '',
                "公差下限": format_value(d.tolerance_min),
                "公差上限": format_value(d.tolerance_max),
                "標準值": format_value(d.std_val),
                "單位": d.unit or 'mm',
            }
            for d in sorted(t.details, key=lambda x: x.id)
        ]
        return {"success": True, "main": main, "details": details}

    @staticmethod
    def add(data: Dict[str, Any]) -> int:
        """新增主檔 + 明細"""
        main = ExtrusionToleranceMain(
            material=data.get('材質'),
            spec=data.get('規格') or None,
            note=data.get('備註') or None,
            created_at=data.get('建立日期') or None,
        )
        db.session.add(main)
        db.session.flush()

        for d in data.get('details', []):
            db.session.add(ExtrusionToleranceDetail(
                main_id=main.id,
                item=d.get('測量項目'),
                position=d.get('測量位置') or None,
                tolerance_min=d.get('公差下限') or None,
                tolerance_max=d.get('公差上限') or None,
                std_val=d.get('標準值') or None,
                unit=d.get('單位', 'mm'),
            ))

        db.session.commit()
        return main.id

    @staticmethod
    def update(tolerance_id: int, data: Dict[str, Any]) -> bool:
        """更新主檔 + 明細（刪除重建明細）"""
        t = ExtrusionToleranceMain.query.get(tolerance_id)
        if not t:
            raise ValueError("找不到擠壓公差資料")

        t.material = data.get('材質')
        t.spec = data.get('規格') or None
        t.note = data.get('備註') or None
        t.created_at = data.get('建立日期') or None

        ExtrusionToleranceDetail.query.filter_by(main_id=tolerance_id).delete()
        for d in data.get('details', []):
            db.session.add(ExtrusionToleranceDetail(
                main_id=t.id,
                item=d.get('測量項目'),
                position=d.get('測量位置') or None,
                tolerance_min=d.get('公差下限') or None,
                tolerance_max=d.get('公差上限') or None,
                std_val=d.get('標準值') or None,
                unit=d.get('單位', 'mm'),
            ))

        db.session.commit()
        return True

    @staticmethod
    def delete(tolerance_id: int) -> bool:
        """刪除（CASCADE 自動刪明細）"""
        t = ExtrusionToleranceMain.query.get(tolerance_id)
        if t:
            db.session.delete(t)
            db.session.commit()
        return True

    @staticmethod
    def get_options() -> Dict[str, Any]:
        """取得篩選選項（材質、規格清單）"""
        materials = [r[0] for r in db.session.query(ExtrusionToleranceMain.material)
                     .distinct().order_by(ExtrusionToleranceMain.material).all() if r[0]]
        specs = [r[0] for r in db.session.query(ExtrusionToleranceMain.spec)
                 .distinct().filter(ExtrusionToleranceMain.spec != None,
                                    ExtrusionToleranceMain.spec != '')
                 .order_by(ExtrusionToleranceMain.spec).all()]
        return {"materials": materials, "specs": specs}

    @staticmethod
    def check(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        依材質+規格查詢對應擠壓公差。
        優先等級：
          1. 材質 + 規格完全匹配
          2. 材質 + 規格前兩段匹配（OD*壁厚 相同，長度不同）
          3. 材質 + 無規格（通用）
        """
        material = args.get('material')
        if not material:
            return {"success": False, "error": "材質為必填參數"}

        normalize = ExtrusionToleranceService._normalize_spec
        input_spec = normalize(args.get('spec', ''))

        candidates = ExtrusionToleranceMain.query.options(
            joinedload(ExtrusionToleranceMain.details)
        ).filter_by(material=material).all()

        buckets: Dict[int, list] = {1: [], 2: [], 3: []}

        for t in candidates:
            t_spec = normalize(t.spec or '')
            has_spec = t_spec != ''

            if has_spec:
                if t_spec == input_spec:
                    buckets[1].append(t)
                else:
                    p_in = input_spec.split('*')
                    p_t = t_spec.split('*')
                    if (len(p_in) >= 2 and len(p_t) >= 2
                            and p_in[0] == p_t[0] and p_in[1] == p_t[1]):
                        buckets[2].append(t)
            else:
                buckets[3].append(t)

        matched = None
        priority = None
        for p in (1, 2, 3):
            if buckets[p]:
                matched = buckets[p][0]
                priority = p
                break

        if not matched:
            return {"success": True, "found": False, "message": "找不到對應的擠壓公差標準"}

        p_names = {
            1: "材質+規格完全匹配",
            2: "材質+規格前兩段匹配",
            3: "材質+無規格（通用）",
        }

        return {
            "success": True,
            "found": True,
            "tolerance_id": matched.id,
            "material": matched.material,
            "spec": matched.spec or '',
            "tolerances": [
                {
                    "項目": d.item,
                    "位置": d.position or '',
                    "公差下限": float(d.tolerance_min) if d.tolerance_min is not None else None,
                    "公差上限": float(d.tolerance_max) if d.tolerance_max is not None else None,
                    "標準值": float(d.std_val) if d.std_val is not None else None,
                    "單位": d.unit or 'mm',
                }
                for d in matched.details
            ],
            "matched_priority": priority,
            "priority_name": p_names[priority],
        }
