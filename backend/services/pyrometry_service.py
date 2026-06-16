"""CQI-9 爐溫測試服務 — 設備主檔、測試紀錄、判定、到期、趨勢"""
from typing import Dict, Any, List
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from ..extensions import db
from ..models import Furnace
from ..utils import format_value


def _furnace_to_dict(f: Furnace) -> Dict[str, Any]:
    return {
        "識別碼": f.id, "爐號": f.code, "名稱": f.name,
        "製程類型": f.process_type or "",
        "TUS點數": f.tus_points, "SAT點數": f.sat_points,
        "TUS頻率_月": f.tus_freq_months, "SAT頻率_月": f.sat_freq_months,
        "TUS允許公差": format_value(f.tus_tolerance),
        "SAT允許誤差": format_value(f.sat_tolerance),
        "有效加熱區尺寸": f.work_zone or "",
        "儀器型式": f.instrument_type or "", "CQI9等級": f.cqi9_class or "",
        "啟用狀態": f.is_active, "備註": f.note or "",
    }


class PyrometryService:

    # ---------- 設備主檔 ----------
    @staticmethod
    def list_furnaces(active_only: bool = False) -> List[Dict[str, Any]]:
        q = Furnace.query
        if active_only:
            q = q.filter(Furnace.is_active.is_(True))
        return [_furnace_to_dict(f) for f in q.order_by(Furnace.code).all()]

    @staticmethod
    def get_furnace(furnace_id: int) -> Dict[str, Any]:
        f = db.session.get(Furnace, furnace_id)
        if not f:
            raise ValueError("找不到該爐子設備")
        return _furnace_to_dict(f)

    @staticmethod
    def add_furnace(data: Dict[str, Any]) -> int:
        try:
            f = Furnace(
                code=data.get("爐號"), name=data.get("名稱"),
                process_type=data.get("製程類型") or None,
                tus_points=int(data.get("TUS點數", 12) or 12),
                sat_points=int(data.get("SAT點數", 2) or 2),
                tus_freq_months=int(data.get("TUS頻率_月", 3) or 3),
                sat_freq_months=int(data.get("SAT頻率_月", 3) or 3),
                tus_tolerance=data.get("TUS允許公差") or None,
                sat_tolerance=data.get("SAT允許誤差") or None,
                work_zone=data.get("有效加熱區尺寸") or None,
                instrument_type=data.get("儀器型式") or None,
                cqi9_class=data.get("CQI9等級") or None,
                is_active=bool(data.get("啟用狀態", True)),
                note=data.get("備註") or None,
            )
            db.session.add(f)
            db.session.commit()
            return f.id
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_furnace(furnace_id: int, data: Dict[str, Any]) -> bool:
        try:
            f = db.session.get(Furnace, furnace_id)
            if not f:
                raise ValueError("找不到該爐子設備")
            f.code = data.get("爐號")
            f.name = data.get("名稱")
            f.process_type = data.get("製程類型") or None
            f.tus_points = int(data.get("TUS點數", 12) or 12)
            f.sat_points = int(data.get("SAT點數", 2) or 2)
            f.tus_freq_months = int(data.get("TUS頻率_月", 3) or 3)
            f.sat_freq_months = int(data.get("SAT頻率_月", 3) or 3)
            f.tus_tolerance = data.get("TUS允許公差") or None
            f.sat_tolerance = data.get("SAT允許誤差") or None
            f.work_zone = data.get("有效加熱區尺寸") or None
            f.instrument_type = data.get("儀器型式") or None
            f.cqi9_class = data.get("CQI9等級") or None
            f.is_active = bool(data.get("啟用狀態", True))
            f.note = data.get("備註") or None
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_furnace(furnace_id: int) -> bool:
        try:
            f = db.session.get(Furnace, furnace_id)
            if not f:
                raise ValueError("找不到該爐子設備")
            db.session.delete(f)
            db.session.commit()
            return True
        except ValueError:
            raise
        except Exception as e:
            db.session.rollback()
            raise e

    # ---------- 判定邏輯 ----------
    @staticmethod
    def evaluate_tus(setpoint: float, tolerance: float, points: List[Dict[str, Any]]) -> Dict[str, Any]:
        sp = float(setpoint)
        tol = float(tolerance)
        out_points = []
        all_max, all_min = [], []
        overall_pass = True
        for p in points:
            tmax = p.get("最高溫")
            tmin = p.get("最低溫")
            tmax = float(tmax) if tmax is not None else None
            tmin = float(tmin) if tmin is not None else None
            dev_candidates = []
            if tmax is not None:
                dev_candidates.append(tmax - sp); all_max.append(tmax)
            if tmin is not None:
                dev_candidates.append(tmin - sp); all_min.append(tmin)
            # 最大偏差 = 絕對值最大的偏差（保留正負號）
            max_dev = max(dev_candidates, key=abs) if dev_candidates else None
            pt_pass = max_dev is None or abs(max_dev) <= tol
            overall_pass = overall_pass and pt_pass
            np_point = dict(p)
            np_point["最大偏差"] = round(max_dev, 2) if max_dev is not None else None
            np_point["是否合格"] = pt_pass
            out_points.append(np_point)
        tus_range = round(max(all_max) - min(all_min), 2) if all_max and all_min else None
        max_pos = round(max(all_max) - sp, 2) if all_max else None
        max_neg = round(min(all_min) - sp, 2) if all_min else None
        return {
            "是否合格": overall_pass, "TUS均勻度極差": tus_range,
            "TUS最大正偏差": max_pos, "TUS最大負偏差": max_neg, "points": out_points,
        }

    @staticmethod
    def evaluate_sat(tolerance: float, points: List[Dict[str, Any]]) -> Dict[str, Any]:
        tol = float(tolerance)
        out_points = []
        overall_pass = True
        for p in points:
            ctrl = p.get("控制儀表讀值")
            test = p.get("校正測試儀表讀值")
            corr = p.get("修正值") or 0
            diff = None
            if ctrl is not None and test is not None:
                diff = round(float(test) - float(ctrl), 2)
            deviation = round(diff + float(corr), 2) if diff is not None else None
            pt_pass = deviation is None or abs(deviation) <= tol
            overall_pass = overall_pass and pt_pass
            np_point = dict(p)
            np_point["差值"] = diff
            np_point["偏差"] = deviation
            np_point["是否合格"] = pt_pass
            out_points.append(np_point)
        return {"是否合格": overall_pass, "points": out_points}
