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
