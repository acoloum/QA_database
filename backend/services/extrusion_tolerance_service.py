from typing import Dict, Any
from sqlalchemy import or_, func
from sqlalchemy.orm import selectinload, joinedload
from ..extensions import db
from ..models import ExtrusionToleranceMain, ExtrusionToleranceDetail, VendorToleranceMain, Vendor
from ..utils import bounded_int, format_value
from .tolerance_service import ToleranceService
from .tolerance_recompute import after_extrusion_tolerance_change


class ExtrusionToleranceService:

    @staticmethod
    def _normalize_spec(s: str) -> str:
        """標準化規格字串（統一分隔符號，並把數值段轉為標準數值寫法）。

        數值段正規化使「4」與「4.0」視為相同——早期公差建檔把 4.0 記成 4，
        出貨/機械規格卻寫 4.0（或反之），逐段字串比對會配對失敗而查不到公差。
        """
        from ..utils import normalize_spec_for_match
        return normalize_spec_for_match(s)

    @staticmethod
    def _match_material(material: str, candidate_material: str) -> bool:
        """
        判斷材質是否匹配（相近材質視為相同，例如 6061-T651 與 6061）
        """
        if not material or not candidate_material:
            return False
        # 移除空白並轉小寫比較
        m1 = material.strip().lower()
        m2 = candidate_material.strip().lower()
        # 完全匹配
        if m1 == m2:
            return True
        # 包含匹配：例如 "6061-T651" 包含 "6061"
        if m1 in m2 or m2 in m1:
            return True
        return False

    @staticmethod
    def _match_spec(input_spec: str, candidate_spec: str) -> bool:
        """
        判斷規格是否匹配（規格前兩段相同視為相近，例如 a*b*c 與 a*b）
        """
        if not input_spec or not candidate_spec:
            return False
        norm_input = ExtrusionToleranceService._normalize_spec(input_spec)
        norm_candidate = ExtrusionToleranceService._normalize_spec(candidate_spec)
        # 完全匹配
        if norm_input == norm_candidate:
            return True
        # 前兩段匹配：例如 "62.5*2.3*450" 與 "62.5*2.3"
        p_input = norm_input.split('*')
        p_candidate = norm_candidate.split('*')
        if len(p_input) >= 2 and len(p_candidate) >= 2:
            if p_input[0] == p_candidate[0] and p_input[1] == p_candidate[1]:
                return True
        return False

    @staticmethod
    def search(args: Dict[str, Any]) -> Dict[str, Any]:
        """列表查詢（分頁）"""
        query = ExtrusionToleranceMain.query
        if args.get('material'):
            query = query.filter(ExtrusionToleranceMain.material.ilike(f"%{args['material']}%"))
        if args.get('spec'):
            query = query.filter(ExtrusionToleranceMain.spec.ilike(f"%{args['spec']}%"))
        if args.get('vendor'):
            query = query.filter(ExtrusionToleranceMain.vendor.ilike(f"%{args['vendor']}%"))

        page = bounded_int(args.get('page'), 1, 1, 1000000)
        page_size = bounded_int(args.get('page_size'), 20, 1, 100)
        # paginate() 內部已算過 total，不再另外 count() 一次
        pagination = query.order_by(ExtrusionToleranceMain.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        data = [
            {
                "識別碼": t.id,
                "材質": t.material,
                "規格": t.spec or '',
                "廠商": t.vendor or '',
                "備註": t.note or '',
                "建立日期": format_value(t.created_at),
            }
            for t in pagination.items
        ]
        return {"success": True, "data": data, "total": pagination.total, "page": page,
                "page_size": page_size, "total_pages": pagination.pages}

    @staticmethod
    def get_detail(tolerance_id: int) -> Dict[str, Any]:
        """取得單筆主檔 + 明細"""
        t = db.session.get(
            ExtrusionToleranceMain,
            tolerance_id,
            options=[joinedload(ExtrusionToleranceMain.details)],
        )
        if not t:
            raise ValueError("找不到該筆擠壓公差資料")

        main = {
            "識別碼": t.id,
            "材質": t.material,
            "規格": t.spec or '',
            "廠商": t.vendor or '',
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
                "特性重要度": d.characteristic_class or '其他',
            }
            for d in sorted(t.details, key=lambda x: x.id)
        ]
        return {"success": True, "main": main, "details": details}

    @staticmethod
    def add(data: Dict[str, Any], user_id=None) -> int:
        """新增主檔 + 明細"""
        try:
            main = ExtrusionToleranceMain(
                material=data.get('材質'),
                spec=data.get('規格') or None,
                vendor=data.get('廠商') or None,
                note=data.get('備註') or None,
                created_at=data.get('建立日期') or None,
            )
            db.session.add(main)
            db.session.flush()

            for d in data.get('details', []):
                db.session.add(ExtrusionToleranceDetail(
                    main_id=main.id,
                    item=d.get('測量項目'),
                    tolerance_min=d.get('公差下限') or None,
                    tolerance_max=d.get('公差上限') or None,
                    std_val=d.get('標準值') or None,
                    unit=d.get('單位', 'mm'),
                    characteristic_class=d.get('特性重要度', '其他'),
                ))

            # 新公差立即回頭補判巡檢紀錄；擠壓公差不被出貨檢驗使用
            db.session.flush()
            after_extrusion_tolerance_change(user_id=user_id, tolerance_id=main.id)

            db.session.commit()
            return main.id
        except Exception as e:
            db.session.rollback()
            raise

    @staticmethod
    def update(tolerance_id: int, data: Dict[str, Any], user_id=None) -> bool:
        """更新主檔 + 明細（刪除重建明細）"""
        try:
            t = db.session.get(ExtrusionToleranceMain, tolerance_id)
            if not t:
                raise ValueError("找不到擠壓公差資料")

            t.material = data.get('材質')
            t.spec = data.get('規格') or None
            t.vendor = data.get('廠商') or None
            t.note = data.get('備註') or None
            t.created_at = data.get('建立日期') or None

            ExtrusionToleranceDetail.query.filter_by(main_id=tolerance_id).delete()
            for d in data.get('details', []):
                db.session.add(ExtrusionToleranceDetail(
                    main_id=t.id,
                    item=d.get('測量項目'),
                    tolerance_min=d.get('公差下限') or None,
                    tolerance_max=d.get('公差上限') or None,
                    std_val=d.get('標準值') or None,
                    unit=d.get('單位', 'mm'),
                    characteristic_class=d.get('特性重要度', '其他'),
                ))

            db.session.flush()
            after_extrusion_tolerance_change(user_id=user_id, tolerance_id=tolerance_id)

            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise

    @staticmethod
    def delete(tolerance_id: int, user_id=None) -> bool:
        """刪除（CASCADE 自動刪明細）"""
        try:
            t = db.session.get(ExtrusionToleranceMain, tolerance_id)
            if not t:
                raise ValueError("找不到擠壓公差資料")
            db.session.delete(t)
            db.session.flush()
            after_extrusion_tolerance_change(user_id=user_id, tolerance_id=tolerance_id)
            db.session.commit()
            return True
        except ValueError:
            raise
        except Exception as e:
            db.session.rollback()
            raise

    @staticmethod
    def get_options() -> Dict[str, Any]:
        """取得篩選選項（材質、規格、廠商清單）"""
        materials = [r[0] for r in db.session.query(ExtrusionToleranceMain.material)
                     .distinct().order_by(ExtrusionToleranceMain.material).all() if r[0]]
        specs = [r[0] for r in db.session.query(ExtrusionToleranceMain.spec)
                 .distinct().filter(ExtrusionToleranceMain.spec != None,
                                    ExtrusionToleranceMain.spec != '')
                 .order_by(ExtrusionToleranceMain.spec).all()]
        vendors = [r[0] for r in db.session.query(ExtrusionToleranceMain.vendor)
                   .distinct().filter(ExtrusionToleranceMain.vendor != None,
                                      ExtrusionToleranceMain.vendor != '')
                   .order_by(ExtrusionToleranceMain.vendor).all()]
        return {"materials": materials, "specs": specs, "vendors": vendors}

    @staticmethod
    def check(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        依材質+規格查詢對應擠壓公差。
        優先順序：
          1. 擠壓公差（相同材質+相同/相近規格）
          2. 廠商公差（廠商專屬紀錄，需有 vendor_id，桶 1-4）
             ※ 不使用無廠商綁定的通用廠商公差（桶 5-8）
        """
        material = args.get('material')
        spec = args.get('spec', '')
        vendor_id = args.get('vendor_id')  # 可選的廠商ID

        if not material:
            return {"success": False, "error": "材質為必填參數"}

        normalize = ExtrusionToleranceService._normalize_spec
        input_spec = normalize(spec)

        # ===== 第一優先：從擠壓公差取得 =====
        # 若有 vendor_id，先查出廠商名稱，只允許：
        #   ① 無廠商（通用）紀錄，或
        #   ② 廠商名稱完全匹配本廠商的紀錄
        # 防止其他廠商的擠壓公差紀錄被誤套用
        vendor_name: str | None = None
        if vendor_id:
            v = db.session.get(Vendor, vendor_id)
            if v:
                vendor_name = v.name.strip()

        candidates = ExtrusionToleranceMain.query.options(
            selectinload(ExtrusionToleranceMain.details)
        )
        # SQL 層初步過濾材質（與 _match_material 的雙向包含語意一致：
        # DB 材質包含查詢值 或 查詢值包含 DB 材質），避免載入無關紀錄
        mat_key = (material or '').strip().lower()
        if mat_key:
            mat_col = func.lower(func.trim(ExtrusionToleranceMain.material))
            candidates = candidates.filter(
                or_(
                    mat_col.ilike(f"%{mat_key}%"),
                    func.lower(mat_key).like(func.concat('%', mat_col, '%')),
                )
            )
        candidates = candidates.all()

        extrusion_buckets: Dict[int, list] = {1: [], 2: [], 3: []}

        for t in candidates:
            # 廠商過濾：擠壓公差有填廠商時，只允許匹配同廠商或通用（無廠商）
            t_vendor = (t.vendor or '').strip()
            if t_vendor:
                # 此紀錄屬於特定廠商，必須與查詢廠商相同才能使用
                if not vendor_name or t_vendor.lower() != vendor_name.lower():
                    continue

            # 使用相似材質匹配
            if not ExtrusionToleranceService._match_material(material, t.material or ''):
                continue

            t_spec = normalize(t.spec or '')
            has_spec = t_spec != ''

            if has_spec:
                # 完全匹配
                if input_spec == t_spec:
                    extrusion_buckets[1].append(t)
                # 相近規格匹配（前兩段相同）
                elif ExtrusionToleranceService._match_spec(input_spec, t_spec):
                    extrusion_buckets[2].append(t)
            else:
                # 無規格（通用）
                extrusion_buckets[3].append(t)

        matched = None
        priority: int = 3  # 預設為通用
        for p in (1, 2, 3):
            if extrusion_buckets[p]:
                matched = extrusion_buckets[p][0]
                priority = p
                break

        if matched:
            p_names = {
                1: "擠壓公差（相同材質+相同規格）",
                2: "擠壓公差（相近材質+相近規格）",
                3: "擠壓公差通用（相同材質+無規格）",
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
                        "公差下限": float(d.tolerance_min) if d.tolerance_min is not None else None,
                        "公差上限": float(d.tolerance_max) if d.tolerance_max is not None else None,
                        "標準值": float(d.std_val) if d.std_val is not None else None,
                        "單位": d.unit or 'mm',
                    }
                    for d in sorted(matched.details, key=lambda x: x.id)
                ],
                "matched_priority": priority,
                "priority_name": p_names[priority],
                "source": "extrusion"
            }

        # ===== 第二優先：廠商公差（僅廠商專屬紀錄，桶 1-4）=====
        # 需有 vendor_id；不使用無廠商綁定的通用紀錄（桶 5-8）
        if vendor_id:
            vendor_result = ToleranceService.check_tolerance({
                'material': material,
                'spec': spec,
                'vendor_id': str(vendor_id)
            })
            # matched_priority <= 4 代表廠商專屬紀錄
            if vendor_result.get('found') and vendor_result.get('matched_priority', 9) <= 4:
                return {
                    "success": True,
                    "found": True,
                    "tolerance_id": vendor_result.get('tolerance_id'),
                    "material": vendor_result.get('material'),
                    "spec": vendor_result.get('spec'),
                    "vendor_id": vendor_result.get('vendor_id'),
                    "vendor_name": vendor_result.get('vendor_name'),
                    "tolerances": vendor_result.get('tolerances', []),
                    "matched_priority": vendor_result.get('matched_priority'),
                    "priority_name": vendor_result.get('priority_name'),
                    "source": "vendor"
                }

        return {"success": True, "found": False, "message": "找不到對應的擠壓公差標準"}
