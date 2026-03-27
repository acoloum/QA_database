
from typing import List, Dict, Any, Optional
import pandas as pd
from io import BytesIO
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import VendorToleranceMain, VendorToleranceDetail, Vendor
from ..utils import format_value

class ToleranceService:
    @staticmethod
    def search_tolerance(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            query = VendorToleranceMain.query.options(joinedload(VendorToleranceMain.vendor))
            
            if args.get('material'):
                query = query.filter(VendorToleranceMain.material.like(f"%{args['material']}%"))
            if args.get('vendor_id'):
                query = query.filter(VendorToleranceMain.vendor_id == args['vendor_id'])
            if args.get('spec'):
                query = query.filter(VendorToleranceMain.spec.like(f"%{args['spec']}%"))
            
            # Pagination
            page = int(args.get('page', 1))
            page_size = int(args.get('page_size', 20))
            
            total = query.count()
            
            query = query.order_by(VendorToleranceMain.id.desc())
            pagination = query.paginate(page=page, per_page=page_size, error_out=False)
            
            data = []
            for t in pagination.items:
                item = {
                    "識別碼": t.id,
                    "材質": t.material,
                    "規格": t.spec,
                    "廠商ID": t.vendor_id,
                    "廠商名稱": t.vendor.name if t.vendor else "",
                    "備註": t.note,
                    "建立日期": format_value(t.created_at)
                }
                data.append(item)
            
            return {
                "success": True,
                "data": data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": pagination.pages
            }
        except Exception as e:
            raise e

    @staticmethod
    def get_tolerance_detail(tolerance_id: int) -> Dict[str, Any]:
        try:
            t = VendorToleranceMain.query.options(
                joinedload(VendorToleranceMain.vendor),
                joinedload(VendorToleranceMain.details)
            ).get(tolerance_id)
            
            if not t: raise ValueError("找不到該筆公差資料")

            main_data = {
                "識別碼": t.id,
                "材質": t.material,
                "規格": t.spec,
                "廠商ID": t.vendor_id,
                "廠商名稱": t.vendor.name if t.vendor else "",
                "備註": t.note,
                "建立日期": format_value(t.created_at)
            }
            
            details = []
            # Sort details by ID as per legacy code order
            sorted_details = sorted(t.details, key=lambda d: d.id)
            for d in sorted_details:
                item = {
                    "識別碼": d.id,
                    "測量項目": d.item,
                    "測量位置": d.position,
                    "尺寸下限": format_value(d.dim_min),
                    "尺寸上限": format_value(d.dim_max),
                    "公差下限": format_value(d.tolerance_min),
                    "公差上限": format_value(d.tolerance_max),
                    "標準值": format_value(d.std_val),
                    "單位": d.unit,
                    "備註": d.note
                }
                details.append(item)
            
            return {"success": True, "main": main_data, "details": details}
        except Exception as e:
            raise e

    @staticmethod
    def add_tolerance(data: Dict[str, Any]) -> int:
        try:
            main = VendorToleranceMain(
                material=data.get('材質'),
                spec=data.get('規格'),
                vendor_id=data.get('廠商ID'),
                note=data.get('備註'),
                created_at=data.get('建立日期')
            )
            db.session.add(main)
            db.session.flush()
            
            for d in data.get('details', []):
                detail = VendorToleranceDetail(
                    main_id=main.id,
                    item=d.get('測量項目'),
                    position=d.get('測量位置'),
                    dim_min=d.get('尺寸下限'),
                    dim_max=d.get('尺寸上限'),
                    tolerance_min=d.get('公差下限'),
                    tolerance_max=d.get('公差上限'),
                    std_val=d.get('標準值'),
                    unit=d.get('單位', 'mm'),
                    note=d.get('備註')
                )
                db.session.add(detail)
            
            db.session.commit()
            return main.id
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_tolerance(tolerance_id: int, data: Dict[str, Any]) -> bool:
        try:
            t = VendorToleranceMain.query.get(tolerance_id)
            if not t: raise ValueError("找不到公差資料")
            
            t.material = data.get('材質')
            t.spec = data.get('規格')
            t.vendor_id = data.get('廠商ID')
            t.note = data.get('備註')
            t.created_at = data.get('建立日期')
            
            # Delete old details (simplest way to update list)
            VendorToleranceDetail.query.filter_by(main_id=tolerance_id).delete()
            
            for d in data.get('details', []):
                detail = VendorToleranceDetail(
                    main_id=t.id,
                    item=d.get('測量項目'),
                    position=d.get('測量位置'),
                    dim_min=d.get('尺寸下限'),
                    dim_max=d.get('尺寸上限'),
                    tolerance_min=d.get('公差下限'),
                    tolerance_max=d.get('公差上限'),
                    std_val=d.get('標準值'),
                    unit=d.get('單位', 'mm'),
                    note=d.get('備註')
                )
                db.session.add(detail)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_tolerance(tolerance_id: int) -> bool:
        try:
            t = VendorToleranceMain.query.get(tolerance_id)
            if t:
                db.session.delete(t)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_options() -> Dict[str, Any]:
        try:
            materials = [r[0] for r in db.session.query(VendorToleranceMain.material).distinct().order_by(VendorToleranceMain.material).all() if r[0]]
            specs = [r[0] for r in db.session.query(VendorToleranceMain.spec).distinct().filter(VendorToleranceMain.spec != None, VendorToleranceMain.spec != '').order_by(VendorToleranceMain.spec).all()]
            vendor_rows = Vendor.query.order_by(Vendor.name).all()
            vendors = [{"id": v.id, "name": v.name.strip()} for v in vendor_rows]
            
            items = [r[0] for r in db.session.query(VendorToleranceDetail.item).distinct().order_by(VendorToleranceDetail.item).all() if r[0]]
            
            return {
                "materials": materials,
                "specs": specs,
                "vendors": vendors,
                "measureItems": items
            }
        except Exception as e:
            raise e

    @staticmethod
    def export_excel(args: Dict[str, Any]) -> BytesIO:
        try:
            query = VendorToleranceMain.query.options(
                joinedload(VendorToleranceMain.vendor),
                joinedload(VendorToleranceMain.details)
            )
            
            if args.get('material'):
                query = query.filter(VendorToleranceMain.material.like(f"%{args['material']}%"))
            if args.get('vendor_id'):
                query = query.filter(VendorToleranceMain.vendor_id == args['vendor_id'])
            if args.get('spec'):
                query = query.filter(VendorToleranceMain.spec.like(f"%{args['spec']}%"))
            
            data_rows = []
            
            # To mimic SQL LEFT JOIN behavior where each detail is a row
            # We iterate mains and then their details
            mains = query.order_by(VendorToleranceMain.id).all()
            
            for m in mains:
                details = sorted(m.details, key=lambda d: d.id)
                if not details:
                     # Add row with main info only? Legacy left join would produce one row with null details.
                     row = [m.id, m.material, m.spec, m.vendor.name if m.vendor else None, 
                            None, None, None, None, None, None, None, None, None]
                     data_rows.append(row)
                else:
                    for d in details:
                        row = [m.id, m.material, m.spec, m.vendor.name if m.vendor else None,
                               d.item, d.position, d.dim_min, d.dim_max, 
                               d.tolerance_min, d.tolerance_max, d.std_val, d.unit, d.note]
                        data_rows.append(row)
            
            cols = ['識別碼', '材質', '規格', '廠商名稱', '測量項目', '測量位置', 
                    '尺寸下限', '尺寸上限', '公差下限', '公差上限', '標準值', '單位', '備註']
            
            df = pd.DataFrame(data_rows, columns=cols)
            
            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return output
        except Exception as e:
            raise e

    @staticmethod
    def parse_spec_values(spec_str: str) -> Dict[str, float]:
        """Parse spec like '62.5*2.3*450' into dimensional values"""
        if not spec_str:
            return {}
        s = str(spec_str).strip().replace('×', '*').replace('x', '*').replace('X', '*')
        while '**' in s:
            s = s.replace('**', '*')
        parts = s.split('*')
        result = {}
        try:
            nums = [float(p.strip()) for p in parts if p.strip()]
        except (ValueError, TypeError):
            return {}
        
        if len(nums) >= 2:
            result['外徑'] = nums[0]
            val2 = nums[1]
            if val2 < (nums[0] / 2):
                result['厚度'] = val2
                result['內徑'] = nums[0] - (val2 * 2)
            else:
                result['內徑'] = val2
                result['厚度'] = (nums[0] - val2) / 2
            if len(nums) >= 3:
                result['長度'] = nums[2]
        elif len(nums) == 1:
            result['外徑'] = nums[0]
        return result

    @staticmethod
    def check_tolerance(args: Dict[str, Any]) -> Dict[str, Any]:
        material = args.get('material')
        if not material: return {"success": False, "error": "材質為必填參數"}
        
        vendor_id = args.get('vendor_id')
        try: vendor_id = int(vendor_id) if vendor_id else None
        except: vendor_id = None
        
        spec = args.get('spec')

        def normalize_spec(s):
            if not s: return ''
            s = str(s).strip().replace('×', '*').replace('x', '*')
            while '**' in s: s = s.replace('**', '*')
            if s.upper() in ('NONE', 'NULL', ''): return ''
            return s.strip()

        input_spec = normalize_spec(spec)

        try:
            # Fetch candidates (使用模糊材質匹配)
            candidates = VendorToleranceMain.query.filter(
                VendorToleranceMain.material.like(f"%{material}%")
            ).all()
            
            # Classification logic (Same as legacy)
            priority_buckets = {i: [] for i in range(1, 9)}
            
            for t in candidates:
                t_vnd_id = t.vendor_id
                t_spec = normalize_spec(t.spec)
                has_vnd = t_vnd_id is not None
                has_spec = t_spec != ''
                
                vendor_match = (t_vnd_id == vendor_id) if (has_vnd and vendor_id is not None) else False
                
                def similar(s1, s2):
                    if not s1 or not s2: return False
                    p1 = s1.split('*'); p2 = s2.split('*')
                    return len(p1)>=2 and len(p2)>=2 and p1[0]==p2[0] and p1[1]==p2[1]

                if vendor_match:
                    if has_spec and t_spec == input_spec: priority_buckets[1].append(t)
                    elif has_spec and input_spec.startswith(t_spec + '*'): priority_buckets[2].append(t)
                    elif has_spec and similar(t_spec, input_spec): priority_buckets[3].append(t)
                    elif not has_spec: priority_buckets[4].append(t)
                elif not has_vnd:
                    if has_spec and t_spec == input_spec: priority_buckets[5].append(t)
                    elif has_spec and input_spec.startswith(t_spec + '*'): priority_buckets[6].append(t)
                    elif has_spec and similar(t_spec, input_spec): priority_buckets[7].append(t)
                    elif not has_spec: priority_buckets[8].append(t)
            
            def score_candidate(candidate, spec_vals):
                """Score how well a candidate matches dimensional conditions."""
                if not spec_vals:
                    return 0
                score = 0
                for detail in candidate.details:
                    item_name = detail.item
                    if item_name not in spec_vals:
                        continue
                    
                    spec_val = spec_vals[item_name]
                    dim_min = detail.dim_min
                    dim_max = detail.dim_max
                    
                    if dim_min is None and dim_max is None:
                        continue
                    
                    if dim_min is not None and spec_val < dim_min:
                        return -1
                    if dim_max is not None and spec_val > dim_max:
                        return -1
                    score += 1
                
                return score

            spec_values = ToleranceService.parse_spec_values(input_spec)

            matched = None
            final_p = None
            for i in range(1, 9):
                bucket = priority_buckets[i]
                if not bucket:
                    continue
                
                if spec_values:
                    # Score candidates and pick the best dimensional match
                    scored = [(c, score_candidate(c, spec_values)) for c in bucket]
                    valid = [(c, s) for c, s in scored if s >= 0]
                    if valid:
                        valid.sort(key=lambda x: x[1], reverse=True)
                        matched = valid[0][0]
                        final_p = i
                        break
                else:
                    # No spec values to parse, just pick first (original behavior)
                    matched = bucket[0]
                    final_p = i
                    break
            
            if not matched:
                return {"success": True, "found": False, "message": "找不到對應的公差標準"}

            # Get details
            details = []
            for d in matched.details:
                details.append({
                    "項目": d.item,
                    "位置": d.position or '',
                    "尺寸下限": d.dim_min, "尺寸上限": d.dim_max,
                    "公差下限": d.tolerance_min, "公差上限": d.tolerance_max,
                    "標準值": d.std_val, "單位": d.unit or 'mm'
                })
            
            p_names = {
                1: "相同廠商+相同材質+相同規格(完全匹配)",
                2: "相同廠商+相同材質+規格部分匹配(開頭匹配)",
                3: "相同廠商+相同材質+規格相近(前兩個部分相同)",
                4: "相同廠商+相同材質+無規格(通用)",
                5: "無廠商+相同材質+相同規格(完全匹配)",
                6: "無廠商+相同材質+規格部分匹配",
                7: "無廠商+相同材質+規格相近",
                8: "無廠商+相同材質+無規格"
            }

            return {
                "success": True, "found": True,
                "tolerance_id": matched.id,
                "material": matched.material,
                "spec": matched.spec,
                "vendor_id": matched.vendor_id,
                "vendor_name": matched.vendor.name.strip() if matched.vendor else '',
                "tolerances": details,
                "matched_priority": final_p,
                "priority_name": p_names.get(final_p, "未知")
            }

        except Exception as e:
            raise e
