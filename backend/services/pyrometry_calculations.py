"""CQI-9 爐溫測試純計算與輸入驗證 helper。"""
from datetime import date
from typing import Any, Dict, List


def quarter_of(d) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def to_float(v) -> float | None:
    """安全轉換為 float；None 或空字串回傳 None。"""
    if v is None or str(v).strip() == '':
        return None
    return float(v)


def parse_date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


class PyrometryValidationError(ValueError):
    """爐溫測試輸入資料驗證錯誤。"""


def validate_test_payload(data: Dict[str, Any], default_test_type: str | None = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise PyrometryValidationError("請提供有效的 JSON 請求內容")
    required = ("爐子ID", "測試日期", "設定溫度")
    missing = [field for field in required if data.get(field) in (None, "")]
    test_type = data.get("測試類型") or default_test_type
    if not test_type:
        missing.append("測試類型")
    if missing:
        raise PyrometryValidationError(f"缺少必要欄位：{', '.join(missing)}")
    if test_type not in ("TUS", "SAT"):
        raise PyrometryValidationError("測試類型必須為 TUS 或 SAT")
    if not isinstance(data.get("points", []), list):
        raise PyrometryValidationError("points 必須為陣列")
    try:
        furnace_id = int(data.get("爐子ID"))
        if furnace_id <= 0:
            raise ValueError
        float(data.get("設定溫度"))
        float(data.get("允許公差") or 0)
        parse_date(data.get("測試日期"))
    except (TypeError, ValueError):
        raise PyrometryValidationError("爐子ID、測試日期、設定溫度或允許公差格式不正確")
    return {**data, "測試類型": test_type, "爐子ID": furnace_id}


def interp_error(points: List, setpoint: float) -> float:
    """以(標準溫度, 器差值)點集對 setpoint 線性內插；超出範圍夾擠取端點。"""
    if not points:
        return 0.0
    pts = sorted(points, key=lambda p: p[0])
    if setpoint <= pts[0][0]:
        return pts[0][1]
    if setpoint >= pts[-1][0]:
        return pts[-1][1]
    for (t0, e0), (t1, e1) in zip(pts, pts[1:]):
        if t0 <= setpoint <= t1:
            if t1 == t0:
                return e0
            return e0 + (setpoint - t0) / (t1 - t0) * (e1 - e0)
    return pts[-1][1]


def _is_excluded(p) -> bool:
    """判斷量測點是否被標記排除；接受 bool / 1 / "true" 等表示法。"""
    v = p.get("已排除")
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def evaluate_tus(setpoint: float, tolerance: float, points: List[Dict[str, Any]]) -> Dict[str, Any]:
    sp = float(setpoint)
    tol = float(tolerance)
    out_points = []
    all_max, all_min = [], []
    overall_pass = True
    for p in points:
        excluded = _is_excluded(p)
        if excluded:
            np_point = dict(p)
            np_point["已排除"] = True
            np_point["最大偏差"] = None
            np_point["是否合格"] = None
            out_points.append(np_point)
            continue
        tmax = to_float(p.get("最高溫"))
        tmin = to_float(p.get("最低溫"))
        corr = to_float(p.get("修正值")) or 0.0
        tmax = tmax + corr if tmax is not None else None
        tmin = tmin + corr if tmin is not None else None
        dev_candidates = []
        if tmax is not None:
            dev_candidates.append(tmax - sp)
            all_max.append(tmax)
        if tmin is not None:
            dev_candidates.append(tmin - sp)
            all_min.append(tmin)
        max_dev = max(dev_candidates, key=abs) if dev_candidates else None
        pt_pass = max_dev is None or abs(max_dev) <= tol
        overall_pass = overall_pass and pt_pass
        np_point = dict(p)
        np_point["已排除"] = False
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


def evaluate_sat(tolerance: float, points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """SAT 判定：每控溫區含多筆取樣讀值，所有讀值均需在公差內。"""
    tol = float(tolerance)
    out_points = []
    overall_pass = True
    for p in points:
        corr = to_float(p.get("修正值")) or 0.0
        raw_readings: List[Dict[str, Any]] = p.get("readings") or []
        if not raw_readings:
            ctrl_s = p.get("控制儀表讀值")
            test_s = p.get("校正測試讀值")
            if ctrl_s is not None or test_s is not None:
                raw_readings = [{"控制儀表讀值": ctrl_s, "校正測試讀值": test_s}]
        computed_readings = []
        worst_diff = None
        worst_dev = None
        zone_pass = True
        for r in raw_readings:
            ctrl = to_float(r.get("控制儀表讀值"))
            test = to_float(r.get("校正測試讀值"))
            diff = round(test - ctrl, 2) if (ctrl is not None and test is not None) else None
            deviation = round(diff + corr, 2) if diff is not None else None
            r_pass = deviation is None or abs(deviation) <= tol
            zone_pass = zone_pass and r_pass
            if deviation is not None and (worst_dev is None or abs(deviation) > abs(worst_dev)):
                worst_dev = deviation
                worst_diff = diff
            cr = {k: v for k, v in r.items() if k not in ("差值", "偏差", "是否合格")}
            cr["差值"] = diff
            cr["偏差"] = deviation
            cr["是否合格"] = r_pass
            computed_readings.append(cr)
        overall_pass = overall_pass and zone_pass
        np_point = {k: v for k, v in p.items() if k not in ("readings", "差值", "偏差", "是否合格")}
        np_point["readings"] = computed_readings
        np_point["差值"] = worst_diff
        np_point["偏差"] = worst_dev
        np_point["是否合格"] = zone_pass
        out_points.append(np_point)
    return {"是否合格": overall_pass, "points": out_points}
