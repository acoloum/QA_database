
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import func, text
from sqlalchemy.orm import selectinload
from scipy import stats as scipy_stats
from ..extensions import db
from ..models import PatrolMain, PatrolDetail, Machine, Operator, Inspector, Vendor
from .extrusion_tolerance_service import ExtrusionToleranceService
from ..utils import (
    format_value,
    validate_patrol_data,
    handle_db_error
)

# SPC 常數查表 (依子群體大小 n)
# Keys: n, Values: (A2, D3, D4, d2)
SPC_CONSTANTS = {
    2: (1.880, 0.000, 3.267, 1.128),
    3: (1.023, 0.000, 2.574, 1.693),
    4: (0.729, 0.000, 2.282, 2.059),
    5: (0.577, 0.000, 2.114, 2.326),
    6: (0.483, 0.000, 2.004, 2.534),
    7: (0.419, 0.076, 1.924, 2.704),
    8: (0.373, 0.136, 1.864, 2.847),
    9: (0.337, 0.184, 1.816, 2.970),
    10: (0.308, 0.223, 1.777, 3.078),
}


def _remap_sheet_ref(formula: str, name_map: dict) -> str:
    """將圖表公式中的工作表參考（如 '管制圖數據'!A1:A10）替換為新名稱"""
    for old_name, new_name in name_map.items():
        # Excel 公式中的工作表名稱可能用單引號包裹
        formula = formula.replace(f"'{old_name}'!", f"'{new_name}'!")
        formula = formula.replace(f"{old_name}!", f"'{new_name}'!")
    return formula


class PatrolService:
    @staticmethod
    def get_options() -> Dict[str, List[Dict[str, Any]]]:
        """獲取下拉選單選項"""
        try:
            machines = [{"id": r.id, "name": r.name.strip()} for r in Machine.query.all()]
            operators = [{"id": r.id, "name": r.name.strip()} for r in Operator.query.all()]
            inspectors = [{"id": r.id, "name": r.name.strip()} for r in Inspector.query.filter_by(group='品保').order_by(Inspector.name).all()]
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
        """獲取巡檢 SPC 統計數據（含公差界限、製程能力、分佈統計）"""
        item = args.get('item', '厚度')
        pos = args.get('pos', '')
        material = args.get('mat', '')
        spec = args.get('spec', '')

        # --- 1. 公差查詢 ---
        tolerance_limits = {"USL": None, "LSL": None, "found": False}
        if material:
            try:
                from ..services.tolerance_service import ToleranceService

                # 解析 vendor_id
                vendor_id = None
                # 巡檢的 customer_id 對應 Vendor 表
                # 這裡使用篩選條件中的材質/規格來查公差

                tol_result = ToleranceService.check_tolerance({
                    'material': material,
                    'spec': spec or '',
                    'vendor_id': ''
                })

                if tol_result.get('found'):
                    tolerance_limits["found"] = True
                    # 從規格解析名義值 (e.g. '31.9*2.2*589')
                    nominal_from_spec = {}
                    if spec:
                        s = str(spec).strip().replace('×', '*').replace('x', '*').replace('X', '*')
                        while '**' in s: s = s.replace('**', '*')
                        parts = s.split('*')
                        try:
                            nums = [float(p.strip()) for p in parts if p.strip()]
                            if len(nums) >= 2:
                                nominal_from_spec['外徑'] = nums[0]
                                val2 = nums[1]
                                if val2 < (nums[0] / 2):
                                    nominal_from_spec['厚度'] = val2
                                    nominal_from_spec['內徑'] = nums[0] - (val2 * 2)
                                else:
                                    nominal_from_spec['內徑'] = val2
                                    nominal_from_spec['厚度'] = (nums[0] - val2) / 2
                                if len(nums) >= 3:
                                    nominal_from_spec['長度'] = nums[2]
                            elif len(nums) == 1:
                                nominal_from_spec['外徑'] = nums[0]
                        except (ValueError, TypeError):
                            pass

                    for t in tol_result.get('tolerances', []):
                        if t.get('項目') == item:
                            tolerance_limits["公差下限"] = t.get('公差下限')
                            tolerance_limits["公差上限"] = t.get('公差上限')
                            tolerance_limits["尺寸下限"] = t.get('尺寸下限')
                            tolerance_limits["尺寸上限"] = t.get('尺寸上限')

                            dim_min = t.get('尺寸下限')
                            dim_max = t.get('尺寸上限')
                            if dim_min is not None and dim_max is not None:
                                tolerance_limits["LSL"] = dim_min
                                tolerance_limits["USL"] = dim_max
                            else:
                                tol_min = t.get('公差下限')
                                tol_max = t.get('公差上限')
                                std = t.get('標準值')
                                if std is None and item in nominal_from_spec:
                                    std = nominal_from_spec[item]
                                if tol_min is not None and tol_max is not None and std is not None:
                                    tolerance_limits["LSL"] = std - abs(tol_min)
                                    tolerance_limits["USL"] = std + abs(tol_max)
                            break
            except Exception:
                pass

        # --- 2. 資料查詢 ---
        query = db.session.query(
            PatrolMain.date, PatrolDetail.main_id, PatrolDetail.group,
            PatrolDetail.min_val, PatrolDetail.max_val
        ).join(PatrolDetail).filter(PatrolDetail.item == item)

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
        if args.get('cust_id'):
            query = query.filter(PatrolMain.customer_id == args['cust_id'])
        if material:
            query = query.filter(PatrolMain.material.like(f"%{material}%"))
        if spec:
            query = query.filter(PatrolMain.spec.like(f"%{spec}%"))

        query = query.order_by(PatrolMain.date.asc(), PatrolDetail.group.asc())
        rows = query.all()

        if not rows:
            return {"labels": [], "avgs": [], "ranges": []}

        # --- 3. 分組聚合 ---
        from collections import OrderedDict
        groups: Dict[str, List[float]] = OrderedDict()
        group_dates: Dict[str, str] = {}  # key -> full date string
        group_ids: Dict[str, int] = {}    # key -> main_id

        for r in rows:
            val1 = r[3]
            val2 = r[4]
            if val1 is None or val2 is None:
                continue

            date_str = r[0].strftime('%m/%d') if hasattr(r[0], 'strftime') else str(r[0])
            full_date = r[0].strftime('%Y-%m-%d') if hasattr(r[0], 'strftime') else str(r[0])
            key = f"{date_str}-#{r[1]}-G{r[2]}"

            try:
                fv1, fv2 = float(val1), float(val2)
                groups.setdefault(key, []).extend([fv1, fv2])
                group_dates[key] = full_date
                group_ids[key] = r[1]
            except ValueError:
                continue

        labels = list(groups.keys())
        avgs = []
        ranges_list = []
        subgroup_sizes = []
        all_values = []
        ids_valid = []
        dates_valid = []

        for k in labels:
            vals = groups[k]
            avgs.append(float(np.mean(vals)))
            ranges_list.append(float(np.ptp(vals)))
            subgroup_sizes.append(len(vals))
            all_values.extend(vals)
            ids_valid.append(str(group_ids[k]))
            dates_valid.append(group_dates[k])

        # --- 4. 控制限計算（動態 SPC 常數）---
        BASELINE_COUNT = 25
        if len(avgs) >= 5:
            baseline_count = min(BASELINE_COUNT, len(avgs))
            base_avgs = avgs[:baseline_count]
            base_ranges = ranges_list[:baseline_count]
            base_ns = subgroup_sizes[:baseline_count]

            avg_n = round(float(np.mean(base_ns)))
            avg_n = max(2, min(10, avg_n))
            A2, D3, D4, d2 = SPC_CONSTANTS[avg_n]

            x_cl = float(np.mean(base_avgs))
            r_cl = float(np.mean(base_ranges))
            x_ucl = x_cl + A2 * r_cl
            x_lcl = x_cl - A2 * r_cl
            r_ucl = D4 * r_cl
            r_lcl = D3 * r_cl
            x_lcl = max(x_lcl, 0)
        else:
            x_cl = x_ucl = x_lcl = r_cl = r_ucl = r_lcl = 0.0
            d2 = 2.326
            avg_n = 5
            baseline_count = 0

        # --- 5. 製程能力指標 (Cp/Cpk/Pp/Ppk) ---
        process_capability = {"available": False}
        usl = tolerance_limits.get("USL")
        lsl = tolerance_limits.get("LSL")

        if usl is not None and lsl is not None and len(avgs) >= 5:
            x_bar = float(np.mean(avgs))
            sigma_within = r_cl / d2 if r_cl > 0 else 0

            if len(all_values) >= 2:
                sigma_overall = float(np.std(all_values, ddof=1))
            else:
                sigma_overall = 0

            process_capability["available"] = True
            process_capability["usl"] = float(usl)
            process_capability["lsl"] = float(lsl)

            if sigma_within > 0:
                cp = (float(usl) - float(lsl)) / (6 * sigma_within)
                cpu = (float(usl) - x_bar) / (3 * sigma_within)
                cpl = (x_bar - float(lsl)) / (3 * sigma_within)
                cpk = min(cpu, cpl)
                process_capability.update({
                    "cp": round(cp, 3), "cpk": round(cpk, 3),
                    "cpu": round(cpu, 3), "cpl": round(cpl, 3)
                })
            else:
                process_capability.update({"cp": None, "cpk": None, "cpu": None, "cpl": None})

            if sigma_overall > 0:
                pp = (float(usl) - float(lsl)) / (6 * sigma_overall)
                ppu = (float(usl) - x_bar) / (3 * sigma_overall)
                ppl = (x_bar - float(lsl)) / (3 * sigma_overall)
                ppk = min(ppu, ppl)
                process_capability.update({
                    "pp": round(pp, 3), "ppk": round(ppk, 3),
                    "ppu": round(ppu, 3), "ppl": round(ppl, 3)
                })
            else:
                process_capability.update({"pp": None, "ppk": None, "ppu": None, "ppl": None})

            process_capability["sigma_within"] = round(sigma_within, 6)
            process_capability["sigma_overall"] = round(sigma_overall, 6)

            # PPM 估算
            if sigma_overall > 0:
                z_upper = (float(usl) - x_bar) / sigma_overall
                z_lower = (x_bar - float(lsl)) / sigma_overall
                ppm_upper = round(float(scipy_stats.norm.sf(z_upper) * 1_000_000), 1)
                ppm_lower = round(float(scipy_stats.norm.sf(z_lower) * 1_000_000), 1)
                ppm_total = round(ppm_upper + ppm_lower, 1)
                process_capability["ppm"] = {"upper": ppm_upper, "lower": ppm_lower, "total": ppm_total}
            else:
                process_capability["ppm"] = {"upper": 0, "lower": 0, "total": 0}

        # --- 6. 偏態 / 峰態 ---
        distribution_stats = {}
        if len(all_values) >= 4:
            arr = np.array(all_values, dtype=float)
            distribution_stats["skewness"] = round(float(scipy_stats.skew(arr)), 3)
            distribution_stats["kurtosis"] = round(float(scipy_stats.kurtosis(arr)), 3)
            sk = abs(distribution_stats["skewness"])
            ku = abs(distribution_stats["kurtosis"])
            if sk < 0.5 and ku < 1.0:
                distribution_stats["normality"] = "good"
                distribution_stats["normality_label"] = "分佈接近常態"
            elif sk < 1.0 and ku < 2.0:
                distribution_stats["normality"] = "moderate"
                distribution_stats["normality_label"] = "分佈略偏，Cpk 僅供參考"
            else:
                distribution_stats["normality"] = "poor"
                distribution_stats["normality_label"] = "分佈明顯非常態，Cpk 可能不準確"

        # --- 7. 月度 Cpk 趨勢 ---
        cpk_trend = []
        if usl is not None and lsl is not None and len(avgs) >= 5:
            monthly_values = defaultdict(list)
            val_idx = 0
            for i in range(len(avgs)):
                month_key = dates_valid[i][:7] if dates_valid[i] else 'unknown'
                n_raw = subgroup_sizes[i]
                for j in range(n_raw):
                    if val_idx < len(all_values):
                        monthly_values[month_key].append(all_values[val_idx])
                        val_idx += 1

            for month_key in sorted(monthly_values.keys()):
                vals = monthly_values[month_key]
                if len(vals) >= 5:
                    m_mean = float(np.mean(vals))
                    m_std = float(np.std(vals, ddof=1))
                    if m_std > 0:
                        m_cpu = (float(usl) - m_mean) / (3 * m_std)
                        m_cpl = (m_mean - float(lsl)) / (3 * m_std)
                        m_cpk = round(min(m_cpu, m_cpl), 3)
                        cpk_trend.append({"month": month_key, "cpk": m_cpk, "count": len(vals)})

        return {
            "labels": labels,
            "ids": ids_valid,
            "dates": dates_valid,
            "avgs": [float(x) for x in avgs],
            "ranges": [float(x) for x in ranges_list],
            "subgroup_sizes": subgroup_sizes,
            "all_values": [round(v, 4) for v in all_values],
            "x_cl": x_cl,
            "x_ucl": x_ucl,
            "x_lcl": x_lcl,
            "r_cl": r_cl,
            "r_ucl": r_ucl,
            "r_lcl": r_lcl,
            "avg_subgroup_size": avg_n if len(avgs) >= 5 else 5,
            "tolerance": tolerance_limits,
            "process_capability": process_capability,
            "distribution_stats": distribution_stats,
            "cpk_trend": cpk_trend
        }

    @staticmethod
    def get_detail(id: int) -> Optional[Dict[str, Any]]:
        """獲取巡檢詳細資料（主檔+子檔）"""
        patrol = db.session.get(PatrolMain, id)
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
    def _compute_is_ng(details: list, material: str, spec: str, customer_id) -> bool:
        """
        依量測明細與擠壓公差計算是否超差。
        複用 get_history 內的判斷邏輯，於新增/更新時即時儲存結果。
        """
        if not material:
            return False
        result = ExtrusionToleranceService.check({
            'material': material,
            'spec': spec or '',
            'vendor_id': customer_id
        })
        if not result.get('found'):
            return False
        tol_map = {t['項目']: t for t in result.get('tolerances', [])}

        # 從規格解析標準值（如 "85*2.8" → {外徑:85, 厚度:2.8}）
        spec_nominal: dict = {}
        if spec:
            parts = (spec or '').replace('×', '*').replace('x', '*').replace('X', '*').split('*')
            try:
                if len(parts) >= 1:
                    spec_nominal['外徑'] = float(parts[0])
                if len(parts) >= 2:
                    spec_nominal['厚度'] = float(parts[1])
            except ValueError:
                pass

        for d in details:
            tol = tol_map.get(d.item)
            if tol:
                dim_min = tol.get('尺寸下限')
                dim_max = tol.get('尺寸上限')
                if dim_min is None and dim_max is None:
                    std_val = tol.get('標準值') or spec_nominal.get(d.item)
                    tol_min = tol.get('公差下限')
                    tol_max = tol.get('公差上限')
                    if std_val is not None:
                        if tol_min is not None:
                            dim_min = std_val - abs(tol_min)
                        if tol_max is not None:
                            dim_max = std_val + abs(tol_max)
                for val in [
                    float(d.min_val) if d.min_val is not None else None,
                    float(d.max_val) if d.max_val is not None else None,
                ]:
                    if val is None:
                        continue
                    if dim_min is not None and val < dim_min:
                        return True
                    if dim_max is not None and val > dim_max:
                        return True

            # 同心度判斷
            if d.item == '厚度' and d.min_val is not None and d.max_val is not None:
                conc_tol = tol_map.get('同心度')
                if conc_tol:
                    conc_dim_min = conc_tol.get('尺寸下限')
                    conc_dim_max = conc_tol.get('尺寸上限')
                    if conc_dim_min is None and conc_dim_max is None:
                        std_val = conc_tol.get('標準值')
                        tol_min = conc_tol.get('公差下限')
                        tol_max = conc_tol.get('公差上限')
                        if std_val is not None:
                            if tol_min is not None:
                                conc_dim_min = std_val - abs(tol_min)
                            if tol_max is not None:
                                conc_dim_max = std_val + abs(tol_max)
                        elif tol_min == 0.0 and tol_max is not None:
                            conc_dim_min = 0.0
                            conc_dim_max = float(tol_max)
                        elif tol_max is not None:
                            # 同心度：僅有公差上限時，直接作為絕對上限
                            conc_dim_max = float(tol_max)
                    concentricity = float(d.max_val) - float(d.min_val)
                    if conc_dim_min is not None and concentricity < conc_dim_min:
                        return True
                    if conc_dim_max is not None and concentricity > conc_dim_max:
                        return True
        return False

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

            # 計算並儲存 is_ng
            db.session.flush()
            new_patrol.is_ng = PatrolService._compute_is_ng(
                new_patrol.details,
                new_patrol.material or '',
                new_patrol.spec or '',
                new_patrol.customer_id
            )

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
            patrol = db.session.get(PatrolMain, record_id)
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

            # 重新計算並儲存 is_ng
            db.session.flush()
            patrol.is_ng = PatrolService._compute_is_ng(
                patrol.details,
                patrol.material or '',
                patrol.spec or '',
                patrol.customer_id
            )

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
            patrol = db.session.get(PatrolMain, record_id)
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
            query = db.session.query(
                PatrolMain,
                Machine.name.label('m_name'),
                Operator.name.label('op_name'),
                Vendor.name.label('cust_name')
            )\
                .outerjoin(Machine, PatrolMain.machine_id == Machine.id)\
                .outerjoin(Operator, PatrolMain.operator_id == Operator.id)\
                .outerjoin(Vendor, PatrolMain.customer_id == Vendor.id)\
                .options(selectinload(PatrolMain.details))

            if args.get('s_date'): query = query.filter(PatrolMain.date >= args['s_date'])
            if args.get('e_date'): query = query.filter(PatrolMain.date <= args['e_date'])
            if args.get('m_id'):   query = query.filter(PatrolMain.machine_id == args['m_id'])
            if args.get('op_id'):  query = query.filter(PatrolMain.operator_id == args['op_id'])
            if args.get('cust_id'): query = query.filter(PatrolMain.customer_id == args['cust_id'])
            if args.get('mat'):    query = query.filter(PatrolMain.material.like(f"%{args['mat']}%"))
            if args.get('spec'):   query = query.filter(PatrolMain.spec.like(f"%{args['spec']}%"))

            query = query.order_by(PatrolMain.id.desc())

            page = int(args.get('page', 1))
            per_page = int(args.get('per_page', 20))

            pagination = query.paginate(page=page, per_page=per_page, error_out=False)

            # --- 批次查詢押出公差（以避免 N+1） ---
            # 延遲匯入以避免循環依賴（patrol_service ↔ extrusion_tolerance_service）
            from ..services.extrusion_tolerance_service import ExtrusionToleranceService

            unique_combos = {
                (patrol_item.material or '', patrol_item.spec or '', patrol_item.customer_id)
                for patrol_item, *_ in pagination.items
                if patrol_item.material
            }

            tol_cache: dict = {}
            for mat, sp, vid in unique_combos:
                result = ExtrusionToleranceService.check({'material': mat, 'spec': sp, 'vendor_id': vid})
                if result.get('found'):
                    tol_cache[(mat, sp, vid)] = {t['項目']: t for t in result.get('tolerances', [])}
                else:
                    tol_cache[(mat, sp, vid)] = None

            data = []
            for item in pagination.items:
                patrol, m_name, op_name, cust_name = item

                # --- NG 計算 ---
                mat = patrol.material or ''
                sp = patrol.spec or ''
                tol_map = tol_cache.get((mat, sp, patrol.customer_id)) if mat else None
                tol_found = tol_map is not None
                is_ng = False

                if tol_found:
                    # 從規格字串解析標準值（如 "85*2.8" → {'外徑': 85.0, '厚度': 2.8}）
                    # 供無標準值的相對公差記錄使用
                    spec_nominal: dict = {}
                    if sp:
                        parts = sp.replace('×', '*').replace('x', '*').replace('X', '*').split('*')
                        try:
                            if len(parts) >= 1:
                                spec_nominal['外徑'] = float(parts[0])
                            if len(parts) >= 2:
                                spec_nominal['厚度'] = float(parts[1])
                        except ValueError:
                            pass

                    for d in patrol.details:
                        tol = tol_map.get(d.item)
                        if tol:
                            # 優先使用尺寸下限/尺寸上限（絕對限制），其次使用公差下限/公差上限（相對限制）
                            dim_min = tol.get('尺寸下限')
                            dim_max = tol.get('尺寸上限')

                            # 如果沒有尺寸下限/上限，則從標準值和公差計算
                            # 標準值優先使用公差記錄本身，否則 fallback 到規格解析值
                            if dim_min is None and dim_max is None:
                                std_val = tol.get('標準值') or spec_nominal.get(d.item)
                                tol_min = tol.get('公差下限')
                                tol_max = tol.get('公差上限')
                                if std_val is not None:
                                    if tol_min is not None:
                                        dim_min = std_val - abs(tol_min)
                                    if tol_max is not None:
                                        dim_max = std_val + abs(tol_max)

                            # 進行 NG 判斷
                            for val in [
                                float(d.min_val) if d.min_val is not None else None,
                                float(d.max_val) if d.max_val is not None else None,
                            ]:
                                if val is None:
                                    continue
                                if dim_min is not None and val < dim_min:
                                    is_ng = True
                                if dim_max is not None and val > dim_max:
                                    is_ng = True

                        # 同心度：厚度行的 max_val - min_val 與同心度公差比對
                        if d.item == '厚度' and d.min_val is not None and d.max_val is not None:
                            conc_tol = tol_map.get('同心度')
                            if conc_tol:
                                # 優先使用尺寸下限/尺寸上限
                                conc_dim_min = conc_tol.get('尺寸下限')
                                conc_dim_max = conc_tol.get('尺寸上限')

                                if conc_dim_min is None and conc_dim_max is None:
                                    std_val = conc_tol.get('標準值')
                                    tol_min = conc_tol.get('公差下限')
                                    tol_max = conc_tol.get('公差上限')
                                    if std_val is not None:
                                        if tol_min is not None:
                                            conc_dim_min = std_val - abs(tol_min)
                                        if tol_max is not None:
                                            conc_dim_max = std_val + abs(tol_max)
                                    elif tol_min == 0.0 and tol_max is not None:
                                        # 同心度：tolerance_min=0 表示「最小值=0」，tolerance_max 為絕對上限
                                        conc_dim_min = 0.0
                                        conc_dim_max = float(tol_max)
                                    elif tol_max is not None:
                                        # 同心度：僅有公差上限時，直接作為絕對上限
                                        conc_dim_max = float(tol_max)
                                
                                concentricity = float(d.max_val) - float(d.min_val)
                                if conc_dim_min is not None and concentricity < conc_dim_min:
                                    is_ng = True
                                if conc_dim_max is not None and concentricity > conc_dim_max:
                                    is_ng = True

                        if is_ng:
                            break

                date_str = patrol.date.strftime('%Y-%m-%d') if patrol.date else ''
                data.append({
                    'id': patrol.id,
                    'date': date_str,
                    'm_name': m_name.strip() if m_name else '',
                    'op_name': op_name.strip() if op_name else '',
                    'cust_name': cust_name.strip() if cust_name else '',
                    'mat': patrol.material,
                    'spec': patrol.spec,
                    'is_ng': is_ng,
                    'tol_found': tol_found,
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
        """匯出巡檢資料 Excel（含 SPC 統計與圖表，按規格+材質分組）"""
        from ..services.spc_report import SpcReportService
        from openpyxl import load_workbook

        spc_item = args.get('item', '')      # 測量項目（外徑/內徑/厚度）
        spc_position = args.get('position', '')  # 測量位置（前段/中段/後段/全段）

        try:
            # === 1. 查詢原始資料 ===
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
            .outerjoin(Vendor, PatrolMain.customer_id == Vendor.id)\
            .options(selectinload(PatrolMain.details))

            if args.get('s_date'): query = query.filter(PatrolMain.date >= args['s_date'])
            if args.get('e_date'): query = query.filter(PatrolMain.date <= args['e_date'])
            if args.get('m_id'):   query = query.filter(PatrolMain.machine_id == args['m_id'])
            if args.get('op_id'):  query = query.filter(PatrolMain.operator_id == args['op_id'])
            if args.get('cust_id'): query = query.filter(PatrolMain.customer_id == args['cust_id'])
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

            # 先產生原始數據工作表
            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl', sheet_name='原始數據')
            output.seek(0)

            # === 2. 如果有選擇 SPC 項目，按規格+材質分組產生 SPC 報表 ===
            if spc_item and rows:
                wb = load_workbook(output)

                # 收集所有不重複的「規格+材質」組合
                spec_mat_set: Dict[str, Dict[str, Any]] = {}
                for row in rows:
                    patrol = row[0]
                    v_name = row[4]  # Vendor.name
                    mat = (patrol.material or '').strip()
                    spec_val = (patrol.spec or '').strip()
                    cust = (v_name.strip() if v_name else '')
                    if mat or spec_val:
                        group_key = f"{spec_val}_{mat}"
                        if group_key not in spec_mat_set:
                            spec_mat_set[group_key] = {'spec': spec_val, 'material': mat, 'customers': set()}
                        if cust:
                            spec_mat_set[group_key]['customers'].add(cust)

                for group_key, group_info in spec_mat_set.items():
                    # 為每個組合呼叫 get_spc 取得統計數據
                    spc_args = {
                        'item': spc_item,
                        'pos': spc_position if spc_position != '全段' else '',
                        'mat': group_info['material'],
                        'spec': group_info['spec'],
                        's_date': args.get('s_date', ''),
                        'e_date': args.get('e_date', ''),
                        'm_id': args.get('m_id', ''),
                        'op_id': args.get('op_id', ''),
                    }
                    stats_data = PatrolService.get_spc(spc_args)

                    # 跳過無數據的組合
                    if not stats_data.get('avgs'):
                        continue

                    # 產生 SPC 報表（獨立 Workbook）
                    pos_label = spc_position if spc_position else '全段'
                    field_label = f"{spc_item}-{pos_label}"
                    # 從該分組的實際資料中取得客戶名稱
                    group_customers = group_info.get('customers', set())
                    cust_display = '、'.join(sorted(group_customers)) if group_customers else '無'
                    filters = {
                        'material': group_info['material'] or '全部',
                        'spec': group_info['spec'] or '全部',
                        'customer': cust_display,
                        'start_date': args.get('s_date', '不限'),
                        'end_date': args.get('e_date', '不限'),
                    }
                    spc_output = SpcReportService.generate_report(stats_data, field_label, filters)

                    # 把 SPC workbook 的工作表複製到主 workbook
                    spc_wb = load_workbook(spc_output)
                    # 建立工作表名稱前綴（截斷以避免超過 31 字元限制）
                    # 清除 Excel 工作表名稱不允許的字元: * ? / \ [ ] :
                    def sanitize_sheet_name(name: str) -> str:
                        # * 以 X 代替，其餘不允許字元直接移除
                        name = name.replace('*', 'X')
                        for ch in ['?', '/', '\\', '[', ']', ':']:
                            name = name.replace(ch, '')
                        return name.strip()

                    spec_short = sanitize_sheet_name(group_info['spec'][:8]) if group_info['spec'] else '無規格'
                    mat_short = sanitize_sheet_name(group_info['material'][:6]) if group_info['material'] else '無材質'
                    prefix = f"{spec_short}-{mat_short}"

                    # 建立舊工作表名稱 → 新工作表名稱的對照表
                    sheet_name_map = {}
                    for spc_sheet in spc_wb.sheetnames:
                        new_name = sanitize_sheet_name(f"{prefix} {spc_sheet}")
                        if len(new_name) > 31:
                            new_name = new_name[:31]
                        base_name = new_name
                        counter = 1
                        while new_name in wb.sheetnames:
                            suffix = f"_{counter}"
                            new_name = base_name[:31 - len(suffix)] + suffix
                            counter += 1
                        sheet_name_map[spc_sheet] = new_name

                    for spc_sheet in spc_wb.sheetnames:
                        new_name = sheet_name_map[spc_sheet]
                        source_ws = spc_wb[spc_sheet]
                        target_ws = wb.create_sheet(title=new_name)

                        # 複製儲存格內容、樣式
                        for row_cells in source_ws.iter_rows():
                            for cell in row_cells:
                                new_cell = target_ws.cell(
                                    row=cell.row, column=cell.column, value=cell.value
                                )
                                if cell.has_style:
                                    new_cell.font = cell.font.copy()
                                    new_cell.fill = cell.fill.copy()
                                    new_cell.border = cell.border.copy()
                                    new_cell.alignment = cell.alignment.copy()
                                    new_cell.number_format = cell.number_format

                        # 複製合併儲存格
                        for merged_range in source_ws.merged_cells.ranges:
                            target_ws.merge_cells(str(merged_range))

                        # 複製欄寬
                        for col_letter, dim in source_ws.column_dimensions.items():
                            target_ws.column_dimensions[col_letter].width = dim.width

                        # 複製圖表，並更新數據參考的工作表名稱
                        for chart in source_ws._charts:
                            # 更新圖表 series 中的工作表參考
                            for series in chart.series:
                                if series.val and hasattr(series.val, 'numRef') and series.val.numRef:
                                    series.val.numRef.f = _remap_sheet_ref(
                                        series.val.numRef.f, sheet_name_map)
                                if series.cat and hasattr(series.cat, 'numRef') and series.cat.numRef:
                                    series.cat.numRef.f = _remap_sheet_ref(
                                        series.cat.numRef.f, sheet_name_map)
                                if series.cat and hasattr(series.cat, 'strRef') and series.cat.strRef:
                                    series.cat.strRef.f = _remap_sheet_ref(
                                        series.cat.strRef.f, sheet_name_map)
                            target_ws.add_chart(chart)

                # 輸出最終結果
                output = BytesIO()
                wb.save(output)
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
