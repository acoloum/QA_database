"""CQI-9 爐溫測試服務 — 設備主檔、測試紀錄、判定、到期、趨勢"""
from typing import Dict, Any, List
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from ..extensions import db
from ..models import Furnace
from ..utils import format_value


def _quarter_of(d) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def _parse_date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    from datetime import date as _date
    return _date.fromisoformat(str(v)[:10])


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

    # ---------- 測試紀錄 ----------
    @staticmethod
    def create_test(data: Dict[str, Any]) -> int:
        from ..models import PyrometryTest, TusPoint, SatPoint
        try:
            test_date = _parse_date(data.get("測試日期"))
            test_type = data.get("測試類型")
            tolerance = float(data.get("允許公差") or 0)
            setpoint = float(data.get("設定溫度") or 0)
            raw_points = data.get("points", [])

            if test_type == "TUS":
                judged = PyrometryService.evaluate_tus(setpoint, tolerance, raw_points)
            else:
                judged = PyrometryService.evaluate_sat(tolerance, raw_points)

            t = PyrometryTest(
                furnace_id=data.get("爐子ID"), test_type=test_type,
                quarter=data.get("季別") or _quarter_of(test_date),
                test_date=test_date, setpoint=setpoint, tolerance=tolerance,
                tester_id=data.get("測試人員") or None,
                test_instrument=data.get("測試儀器編號") or None,
                std_instrument=data.get("標準校正儀器編號") or None,
                cal_due_date=_parse_date(data.get("儀器校正到期日")),
                is_pass=judged["是否合格"],
                tus_range=judged.get("TUS均勻度極差"),
                tus_max_pos=judged.get("TUS最大正偏差"),
                tus_max_neg=judged.get("TUS最大負偏差"),
                note=data.get("備註") or None,
                created_by=data.get("建立人") or None,
            )
            db.session.add(t)
            db.session.flush()

            for p in judged["points"]:
                if test_type == "TUS":
                    db.session.add(TusPoint(
                        test_id=t.id, position=p.get("點位"), tc_no=p.get("熱電偶編號"),
                        correction=p.get("修正值"), temp_max=p.get("最高溫"),
                        temp_min=p.get("最低溫"), max_dev=p.get("最大偏差"),
                        is_pass=p.get("是否合格", True),
                    ))
                else:
                    db.session.add(SatPoint(
                        test_id=t.id, zone=p.get("控溫區"),
                        control_read=p.get("控制儀表讀值"), test_read=p.get("校正測試儀表讀值"),
                        diff=p.get("差值"), correction=p.get("修正值"),
                        deviation=p.get("偏差"), is_pass=p.get("是否合格", True),
                    ))
            db.session.commit()
            return t.id
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_test(test_id: int) -> Dict[str, Any]:
        from ..models import PyrometryTest
        t = PyrometryTest.query.filter(
            PyrometryTest.id == test_id, PyrometryTest.deleted_at.is_(None)
        ).first()
        if not t:
            raise ValueError("找不到該筆爐溫測試")
        main = {
            "識別碼": t.id, "爐子ID": t.furnace_id,
            "爐號": t.furnace.code if t.furnace else "",
            "測試類型": t.test_type, "季別": t.quarter or "",
            "測試日期": format_value(t.test_date), "設定溫度": format_value(t.setpoint),
            "允許公差": format_value(t.tolerance),
            "測試人員": t.tester_id, "測試人員姓名": t.tester.name if t.tester else "",
            "測試儀器編號": t.test_instrument or "", "標準校正儀器編號": t.std_instrument or "",
            "儀器校正到期日": format_value(t.cal_due_date),
            "是否合格": t.is_pass, "TUS均勻度極差": format_value(t.tus_range),
            "TUS最大正偏差": format_value(t.tus_max_pos), "TUS最大負偏差": format_value(t.tus_max_neg),
            "備註": t.note or "",
        }
        tus_points = [{
            "識別碼": p.id, "點位": p.position or "", "熱電偶編號": p.tc_no or "",
            "修正值": format_value(p.correction), "最高溫": format_value(p.temp_max),
            "最低溫": format_value(p.temp_min), "最大偏差": format_value(p.max_dev),
            "是否合格": p.is_pass,
        } for p in sorted(t.tus_points, key=lambda x: x.id)]
        sat_points = [{
            "識別碼": p.id, "控溫區": p.zone or "", "控制儀表讀值": format_value(p.control_read),
            "校正測試儀表讀值": format_value(p.test_read), "差值": format_value(p.diff),
            "修正值": format_value(p.correction), "偏差": format_value(p.deviation),
            "是否合格": p.is_pass,
        } for p in sorted(t.sat_points, key=lambda x: x.id)]
        return {"success": True, "main": main, "tus_points": tus_points, "sat_points": sat_points}

    @staticmethod
    def update_test(test_id: int, data: Dict[str, Any]) -> bool:
        from ..models import PyrometryTest, TusPoint, SatPoint
        try:
            t = db.session.get(PyrometryTest, test_id)
            if not t or t.deleted_at is not None:
                raise ValueError("找不到該筆爐溫測試")
            test_date = _parse_date(data.get("測試日期"))
            tolerance = float(data.get("允許公差") or 0)
            setpoint = float(data.get("設定溫度") or 0)
            raw_points = data.get("points", [])
            if t.test_type == "TUS":
                judged = PyrometryService.evaluate_tus(setpoint, tolerance, raw_points)
            else:
                judged = PyrometryService.evaluate_sat(tolerance, raw_points)

            t.furnace_id = data.get("爐子ID")
            t.quarter = data.get("季別") or _quarter_of(test_date)
            t.test_date = test_date
            t.setpoint = setpoint
            t.tolerance = tolerance
            t.tester_id = data.get("測試人員") or None
            t.test_instrument = data.get("測試儀器編號") or None
            t.std_instrument = data.get("標準校正儀器編號") or None
            t.cal_due_date = _parse_date(data.get("儀器校正到期日"))
            t.is_pass = judged["是否合格"]
            t.tus_range = judged.get("TUS均勻度極差")
            t.tus_max_pos = judged.get("TUS最大正偏差")
            t.tus_max_neg = judged.get("TUS最大負偏差")
            t.note = data.get("備註") or None

            TusPoint.query.filter_by(test_id=test_id).delete()
            SatPoint.query.filter_by(test_id=test_id).delete()
            for p in judged["points"]:
                if t.test_type == "TUS":
                    db.session.add(TusPoint(
                        test_id=t.id, position=p.get("點位"), tc_no=p.get("熱電偶編號"),
                        correction=p.get("修正值"), temp_max=p.get("最高溫"),
                        temp_min=p.get("最低溫"), max_dev=p.get("最大偏差"),
                        is_pass=p.get("是否合格", True)))
                else:
                    db.session.add(SatPoint(
                        test_id=t.id, zone=p.get("控溫區"),
                        control_read=p.get("控制儀表讀值"), test_read=p.get("校正測試儀表讀值"),
                        diff=p.get("差值"), correction=p.get("修正值"),
                        deviation=p.get("偏差"), is_pass=p.get("是否合格", True)))
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_test(test_id: int) -> bool:
        from ..models import PyrometryTest
        try:
            t = db.session.get(PyrometryTest, test_id)
            if not t or t.deleted_at is not None:
                raise ValueError("找不到該筆爐溫測試")
            t.soft_delete()
            db.session.commit()
            return True
        except ValueError:
            raise
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def search_tests(args: Dict[str, Any]) -> Dict[str, Any]:
        from ..models import PyrometryTest
        q = PyrometryTest.query.filter(PyrometryTest.deleted_at.is_(None))
        if args.get("furnace_id"):
            q = q.filter(PyrometryTest.furnace_id == int(args["furnace_id"]))
        if args.get("test_type"):
            q = q.filter(PyrometryTest.test_type == args["test_type"])
        if args.get("quarter"):
            q = q.filter(PyrometryTest.quarter == args["quarter"])
        if args.get("is_pass") in ("0", "1"):
            q = q.filter(PyrometryTest.is_pass.is_(args["is_pass"] == "1"))
        if args.get("date_from"):
            q = q.filter(PyrometryTest.test_date >= _parse_date(args["date_from"]))
        if args.get("date_to"):
            q = q.filter(PyrometryTest.test_date <= _parse_date(args["date_to"]))
        page = int(args.get("page", 1))
        page_size = int(args.get("page_size", 20))
        total = q.count()
        pg = q.order_by(PyrometryTest.test_date.desc(), PyrometryTest.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False)
        data = [{
            "識別碼": t.id, "爐號": t.furnace.code if t.furnace else "",
            "測試類型": t.test_type, "季別": t.quarter or "",
            "測試日期": format_value(t.test_date), "是否合格": t.is_pass,
            "測試人員姓名": t.tester.name if t.tester else "",
        } for t in pg.items]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": pg.pages}
