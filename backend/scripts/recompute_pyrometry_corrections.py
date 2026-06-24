# -*- coding: utf-8 -*-
"""回填既有爐溫測試(TUS/SAT)的修正值 — 改用「分量各自四捨五入再相加」。

背景：compute_corrections 已改為先把熱電偶補償、記錄器(溫度計)補償各自四捨五入到
小數 2 位再相加，避免如內插值 0.075 被「先合併再捨入」誤壓成 0.07。既有紀錄的
修正值仍是舊演算法結果，本腳本依各點頻道、以「目前啟用中」的記錄器與熱電偶校正
曲線重算，並連動重算偏差/判定/均勻度等衍生欄位。

用法：
    python -m backend.scripts.recompute_pyrometry_corrections          # dry-run，只列出差異
    python -m backend.scripts.recompute_pyrometry_corrections --apply  # 實際寫入
"""
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import PyrometryTest, Recorder, Thermocouple
from ..services.pyrometry_calculations import interp_error, evaluate_tus, evaluate_sat


def _active_components(setpoint: float):
    """回傳 (熱電偶補償(已捨入), {頻道: 記錄器器差點集}, 記錄器舊固定補正)。"""
    r = Recorder.query.filter(Recorder.is_active.is_(True)).order_by(Recorder.id.desc()).first()
    tc_obj = Thermocouple.query.filter(Thermocouple.is_active.is_(True)).order_by(Thermocouple.id.desc()).first()
    if tc_obj:
        tc_points = [(float(cp.std_temp), float(cp.error)) for cp in tc_obj.cal_points]
        tc_component = round(-interp_error(tc_points, setpoint), 2)
    elif r:
        tc_component = round(float(r.tc_correction or 0), 2)
    else:
        tc_component = 0.0
    by_channel = {}
    if r:
        for cp in r.cal_points:
            by_channel.setdefault(cp.channel, []).append((float(cp.std_temp), float(cp.error)))
    return r, tc_component, by_channel


def _channel_of(point, default_ch):
    if point.channel is not None:
        return point.channel
    return default_ch


def _new_correction(tc_component, by_channel, setpoint, channel):
    rec_component = round(-interp_error(by_channel.get(channel, []), setpoint), 2)
    return round(tc_component + rec_component, 2)


def _f(v):
    return None if v is None else float(v)


def main(apply: bool):
    with app.app_context():
        tests = PyrometryTest.query.order_by(PyrometryTest.id).all()
        total_point_changes = 0
        total_pass_flips = 0
        changed_tests = 0

        for t in tests:
            sp = float(t.setpoint)
            r, tc_component, by_channel = _active_components(sp)
            offset = 0 if t.test_type == "TUS" else 12

            point_lines = []
            test_changed = False

            if t.test_type == "TUS":
                # 先逐點算新修正值，組 payload 重新評估
                pts = sorted(t.tus_points, key=lambda p: p.id)
                payload = []
                new_corrs = []
                for idx, p in enumerate(pts):
                    ch = _channel_of(p, offset + idx + 1)
                    new_corr = _new_correction(tc_component, by_channel, sp, ch)
                    new_corrs.append(new_corr)
                    payload.append({"點位": p.position, "最高溫": _f(p.temp_max),
                                    "最低溫": _f(p.temp_min), "修正值": new_corr})
                res = evaluate_tus(sp, float(t.tolerance or 0), payload)
                for p, new_corr, rp in zip(pts, new_corrs, res["points"]):
                    old_corr = _f(p.correction)
                    old_dev = _f(p.max_dev)
                    new_dev = rp.get("最大偏差")
                    old_pass = bool(p.is_pass)
                    new_pass = bool(rp.get("是否合格"))
                    if old_corr != new_corr or old_dev != new_dev or old_pass != new_pass:
                        flip = "  ←判定翻轉!" if old_pass != new_pass else ""
                        if old_pass != new_pass:
                            total_pass_flips += 1
                        point_lines.append(
                            f"      {p.position or ('點'+str(p.id)):<8} 修正值 {old_corr} → {new_corr}"
                            f" | 偏差 {old_dev} → {new_dev} | {('合格' if old_pass else '不合格')}→{('合格' if new_pass else '不合格')}{flip}")
                        total_point_changes += 1
                        test_changed = True
                        if apply:
                            p.correction = new_corr
                            p.max_dev = new_dev
                            p.is_pass = new_pass
                # 測試層彙總
                agg = [("是否合格", bool(t.is_pass), bool(res["是否合格"])),
                       ("均勻度極差", _f(t.tus_range), res["TUS均勻度極差"]),
                       ("最大正偏差", _f(t.tus_max_pos), res["TUS最大正偏差"]),
                       ("最大負偏差", _f(t.tus_max_neg), res["TUS最大負偏差"])]
                agg_lines = [f"      [彙總] {n}: {o} → {nw}" for n, o, nw in agg if o != nw]
                if apply and (agg_lines or test_changed):
                    t.is_pass = bool(res["是否合格"])
                    t.tus_range = res["TUS均勻度極差"]
                    t.tus_max_pos = res["TUS最大正偏差"]
                    t.tus_max_neg = res["TUS最大負偏差"]
                point_lines.extend(agg_lines)
                if agg_lines:
                    test_changed = True

            else:  # SAT
                pts = sorted(t.sat_points, key=lambda p: p.id)
                payload = []
                new_corrs = []
                for idx, p in enumerate(pts):
                    ch = _channel_of(p, offset + idx + 1)
                    new_corr = _new_correction(tc_component, by_channel, sp, ch)
                    new_corrs.append(new_corr)
                    payload.append({"修正值": new_corr, "readings": p.readings or [],
                                    "控制儀表讀值": _f(p.control_read),
                                    "校正測試讀值": _f(p.test_read)})
                res = evaluate_sat(float(t.tolerance or 0), payload)
                for p, new_corr, rp in zip(pts, new_corrs, res["points"]):
                    old_corr = _f(p.correction)
                    old_dev = _f(p.deviation)
                    new_dev = rp.get("偏差")
                    old_pass = bool(p.is_pass)
                    new_pass = bool(rp.get("是否合格"))
                    if old_corr != new_corr or old_dev != new_dev or old_pass != new_pass:
                        flip = "  ←判定翻轉!" if old_pass != new_pass else ""
                        if old_pass != new_pass:
                            total_pass_flips += 1
                        point_lines.append(
                            f"      {p.zone or ('區'+str(p.id)):<8} 修正值 {old_corr} → {new_corr}"
                            f" | 偏差 {old_dev} → {new_dev} | {('合格' if old_pass else '不合格')}→{('合格' if new_pass else '不合格')}{flip}")
                        total_point_changes += 1
                        test_changed = True
                        if apply:
                            p.correction = new_corr
                            p.diff = rp.get("差值")
                            p.deviation = new_dev
                            p.is_pass = new_pass
                if t.is_pass != bool(res["是否合格"]):
                    point_lines.append(f"      [彙總] 是否合格: {bool(t.is_pass)} → {bool(res['是否合格'])}")
                    test_changed = True
                if apply:
                    t.is_pass = bool(res["是否合格"])

            if test_changed:
                changed_tests += 1
                furnace = t.furnace.name if t.furnace else t.furnace_id
                print(f"  #{t.id} [{t.test_type}] 爐:{furnace} 日期:{t.test_date} 設定:{sp} 公差:±{_f(t.tolerance)}")
                for line in point_lines:
                    print(line)

        print("\n" + "=" * 60)
        print(f"  受影響測試數：{changed_tests} / {len(tests)}")
        print(f"  受影響量測點數：{total_point_changes}")
        print(f"  判定翻轉(合格<->不合格)：{total_pass_flips}")
        print("=" * 60)

        if apply:
            db.session.commit()
            print("  ✅ 已寫入資料庫。")
        else:
            print("  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際更新。")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
