import numpy as np
import pytest
from datetime import date
from sqlalchemy import event
from backend.extensions import db
from backend.services.patrol_service import PatrolService
from backend.models import (
    Machine, Operator, Inspector, PatrolMain, PatrolDetail,
    ExtrusionToleranceMain, ExtrusionToleranceDetail,
    VendorToleranceMain, VendorToleranceDetail, Vendor,
)


def test_get_history_is_ng_true(app, db_session):
    """量測值超出押出公差時，is_ng 應為 True（標準值從規格 10*2 解析 → 外徑=10）"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*2')
        db_session.add(et_main)
        db_session.flush()
        # 相對公差 ±0.5，無 std_val；標準值由規格解析 → 10.0
        # 絕對界限：[9.5, 10.5]
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            tolerance_min=0.5, tolerance_max=0.5
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.0, max_val=10.2  # 9.0 < 9.5 → NG
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        assert len(result['data']) == 1
        row = result['data'][0]
        assert row['is_ng'] is True
        assert row['tol_found'] is True


def test_get_history_is_ng_false(app, db_session):
    """量測值在公差範圍內時，is_ng 應為 False（標準值從規格 10*2 解析 → 外徑=10）"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*2')
        db_session.add(et_main)
        db_session.flush()
        # 相對公差 ±0.5，無 std_val；標準值由規格解析 → 10.0
        # 絕對界限：[9.5, 10.5]
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            tolerance_min=0.5, tolerance_max=0.5
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.6, max_val=10.4  # 在 [9.5, 10.5] 內 → 合格
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['is_ng'] is False
        assert row['tol_found'] is True


def test_get_history_tol_not_found(app, db_session):
    """查無押出公差資料時，tol_found 應為 False，is_ng 應為 False"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='UNKNOWN_MAT', spec='99*99')
        db_session.add(patrol)
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['tol_found'] is False
        assert row['is_ng'] is False


def test_get_history_concentricity_ng(app, db_session):
    """同心度（厚度 max_val - min_val）超差時，is_ng 應為 True
    tolerance_min=0, tolerance_max=0.3 → 同心度允許範圍 [0, 0.3]
    """
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*2')
        db_session.add(et_main)
        db_session.flush()
        # tolerance_min=0 代表同心度下限=0，tolerance_max=0.3 代表絕對上限
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='同心度',
            tolerance_min=0.0, tolerance_max=0.3
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        # 同心度 = 1.5 - 0.8 = 0.7，超出上限 0.3 → NG
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='厚度', position='前段',
            min_val=0.8, max_val=1.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['is_ng'] is True
        assert row['tol_found'] is True


def test_get_history_tol_cache_called_once_per_combo(app, db_session, monkeypatch):
    """相同 (material, spec) 的多筆記錄，公差只查詢一次"""
    with app.app_context():
        call_count = {'n': 0}
        from backend.services import extrusion_tolerance_service as ets_mod
        original_check = ets_mod.ExtrusionToleranceService.check

        def counting_check(args):
            call_count['n'] += 1
            return original_check(args)

        monkeypatch.setattr(ets_mod.ExtrusionToleranceService, 'check', staticmethod(counting_check))

        for _ in range(3):
            patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
            db_session.add(patrol)
        db_session.commit()

        PatrolService.get_history({'page': 1, 'per_page': 20})
        # 3 筆記錄，相同 combo，只應呼叫 1 次
        assert call_count['n'] == 1


def test_get_history_no_material(app, db_session):
    """記錄無材質時，tol_found 應為 False，is_ng 應為 False"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material=None, spec=None)
        db_session.add(patrol)
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['tol_found'] is False
        assert row['is_ng'] is False


def test_get_history_clamps_per_page(app, db_session):
    with app.app_context():
        for i in range(101):
            db_session.add(PatrolMain(date=date(2026, 1, 1), material=f'MAT-{i}', spec='10*2'))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 5000})

        assert len(result['data']) == 100
        assert result['total'] == 101


def test_get_history_prefers_extrusion_over_vendor(app, db_session):
    """擠壓公差優先於廠商公差：兩者同時存在時，套用擠壓公差"""
    with app.app_context():
        vendor = Vendor(name='廠商甲')
        db_session.add(vendor)
        db_session.flush()

        # 廠商公差：外徑標準值 10.0，公差 ±0.1（嚴，允許 9.9–10.1）
        vt_main = VendorToleranceMain(
            vendor_id=vendor.id, material='6061', spec='10*2'
        )
        db_session.add(vt_main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=vt_main.id, item='外徑',
            std_val=10.0, tolerance_min=0.1, tolerance_max=0.1
        ))

        # 擠壓公差：外徑標準值 10.0，公差 ±1.0（寬鬆，允許 9.0–11.0）
        et_main = ExtrusionToleranceMain(material='6061', spec='10*2*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            std_val=10.0, tolerance_min=1.0, tolerance_max=1.0
        ))

        # 巡檢紀錄：外徑 = 10.5（超出廠商公差 ±0.1，但在擠壓公差 ±1.0 內）
        patrol = PatrolMain(
            date=date(2026, 1, 1),
            material='6061', spec='10*2*100',
            customer_id=vendor.id
        )
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=10.5, max_val=10.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        # 擠壓公差優先（±1.0），10.5 在 9.0–11.0 內 → is_ng=False
        assert row['is_ng'] is False
        assert row['tol_found'] is True


def test_get_history_fallback_to_vendor_when_no_extrusion(app, db_session):
    """無擠壓公差時，fallback 使用廠商專屬公差（桶 1-4）"""
    with app.app_context():
        vendor = Vendor(name='廠商乙')
        db_session.add(vendor)
        db_session.flush()

        # 只有廠商公差，無擠壓公差
        vt_main = VendorToleranceMain(
            vendor_id=vendor.id, material='6061', spec='10*2'
        )
        db_session.add(vt_main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=vt_main.id, item='外徑',
            std_val=10.0, tolerance_min=0.1, tolerance_max=0.1
        ))

        # 巡檢紀錄：外徑 = 10.5（超出廠商公差 ±0.1 → NG）
        patrol = PatrolMain(
            date=date(2026, 1, 1),
            material='6061', spec='10*2*100',
            customer_id=vendor.id
        )
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=10.5, max_val=10.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        # 無擠壓公差，fallback 廠商公差（±0.1），10.5 > 10.1 → is_ng=True
        assert row['is_ng'] is True
        assert row['tol_found'] is True


def test_get_history_vendor_tolerance_cache_isolation(app, db_session):
    """相同 material+spec 但不同廠商時，各自套用各自的廠商公差，不互相污染"""
    with app.app_context():
        vendor_a = Vendor(name='廠商甲')
        vendor_b = Vendor(name='廠商乙')
        db_session.add_all([vendor_a, vendor_b])
        db_session.flush()

        # 廠商甲公差：外徑 ±0.1（嚴）
        vt_a = VendorToleranceMain(vendor_id=vendor_a.id, material='6061', spec='10*2')
        db_session.add(vt_a)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=vt_a.id, item='外徑',
            std_val=10.0, tolerance_min=0.1, tolerance_max=0.1
        ))

        # 廠商乙公差：外徑 ±2.0（寬）
        vt_b = VendorToleranceMain(vendor_id=vendor_b.id, material='6061', spec='10*2')
        db_session.add(vt_b)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=vt_b.id, item='外徑',
            std_val=10.0, tolerance_min=2.0, tolerance_max=2.0
        ))

        # 廠商甲巡檢：外徑 10.5 → 超出甲的 ±0.1 → NG
        patrol_a = PatrolMain(
            date=date(2026, 1, 1), material='6061', spec='10*2*100',
            customer_id=vendor_a.id
        )
        db_session.add(patrol_a)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol_a.id, group=1, item='外徑', position='前段',
            min_val=10.5, max_val=10.5
        ))

        # 廠商乙巡檢：外徑 10.5 → 在乙的 ±2.0 內 → OK
        patrol_b = PatrolMain(
            date=date(2026, 1, 2), material='6061', spec='10*2*100',
            customer_id=vendor_b.id
        )
        db_session.add(patrol_b)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol_b.id, group=1, item='外徑', position='前段',
            min_val=10.5, max_val=10.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        rows = {r['cust_name']: r for r in result['data']}

        assert rows['廠商甲']['is_ng'] is True
        assert rows['廠商乙']['is_ng'] is False


def test_get_history_no_customer_id_unchanged(app, db_session):
    """無廠商（customer_id=None）時，行為與修改前相同（fallback 到押出公差）"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='6061', spec='10*2*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            std_val=10.0, tolerance_min=1.0, tolerance_max=1.0
        ))

        # 無廠商巡檢：外徑 10.5（在押出公差 ±1.0 內，9.0–11.0）
        patrol = PatrolMain(
            date=date(2026, 1, 1), material='6061', spec='10*2*100',
            customer_id=None
        )
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=10.5, max_val=10.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        row = result['data'][0]
        assert row['tol_found'] is True
        assert row['is_ng'] is False


def test_export_excel_batches_patrol_details(app, db_session):
    """匯出巡檢 Excel 時，明細應批次載入，避免資料筆數增加就產生 N+1 查詢。"""
    with app.app_context():
        machine = Machine(name='M1')
        operator = Operator(name='OP1')
        inspector = Inspector(name='I1')
        vendor = Vendor(name='客戶甲')
        db_session.add_all([machine, operator, inspector, vendor])
        db_session.flush()

        for idx in range(5):
            patrol = PatrolMain(
                date=date(2026, 1, idx + 1),
                machine_id=machine.id,
                operator_id=operator.id,
                inspector_id=inspector.id,
                customer_id=vendor.id,
                material='6061',
                spec='10*2',
            )
            db_session.add(patrol)
            db_session.flush()
            db_session.add(PatrolDetail(
                main_id=patrol.id,
                group=1,
                item='外徑',
                position='前段',
                min_val=10.0,
                max_val=10.1,
            ))
        db_session.commit()

        statements = []

        def track_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(db.engine, 'before_cursor_execute', track_sql)
        try:
            PatrolService.export_excel({})
        finally:
            event.remove(db.engine, 'before_cursor_execute', track_sql)

        detail_selects = [
            statement for statement in statements
            if '巡檢子檔' in statement and statement.lstrip().upper().startswith('SELECT')
        ]
        assert len(detail_selects) <= 1


def test_get_patrol_details_returns_all_rows_with_exclusion_status(app, db_session):
    """取得單筆巡檢記錄的全部量測明細，含各筆的排除狀態
    涵蓋同一 main_id 下多筆明細（跨測量項目與測量位置），確認各筆能以
    （組別、測量項目、測量位置）正確區分，而非僅驗證「有資料」。
    """
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.8, max_val=10.2
        ))
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='內徑', position='前段',
            min_val=5.8, max_val=6.2
        ))
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='中段',
            min_val=9.7, max_val=10.1
        ))
        db_session.commit()

        details = PatrolService.get_patrol_details(patrol.id)
        assert len(details) == 3

        rows_by_key = {(d['組別'], d['測量項目'], d['測量位置']): d for d in details}
        assert set(rows_by_key.keys()) == {
            (1, '外徑', '前段'),
            (1, '內徑', '前段'),
            (1, '外徑', '中段'),
        }

        od_front = rows_by_key[(1, '外徑', '前段')]
        assert od_front['最小值'] == pytest.approx(9.8)
        assert od_front['最大值'] == pytest.approx(10.2)
        assert od_front['排除統計'] is False
        assert od_front['排除原因'] is None

        id_front = rows_by_key[(1, '內徑', '前段')]
        assert id_front['最小值'] == pytest.approx(5.8)
        assert id_front['最大值'] == pytest.approx(6.2)

        od_mid = rows_by_key[(1, '外徑', '中段')]
        assert od_mid['最小值'] == pytest.approx(9.7)
        assert od_mid['最大值'] == pytest.approx(10.1)


def test_set_patrol_detail_exclusion_requires_reason(app, db_session):
    """標示離群值時，未填原因應拋出 ValueError（§6.6）"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        detail = PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.8, max_val=10.2
        )
        db_session.add(detail)
        db_session.commit()

        with pytest.raises(ValueError, match='原因'):
            PatrolService.set_patrol_detail_exclusion(detail.id, excluded=True, reason='')


def test_set_patrol_detail_exclusion_round_trips(app, db_session):
    """標示離群後可恢復計入，恢復時清除排除原因"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        detail = PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=9.8, max_val=10.2
        )
        db_session.add(detail)
        db_session.commit()

        result = PatrolService.set_patrol_detail_exclusion(detail.id, excluded=True, reason='量測儀器故障')
        assert result['排除統計'] is True
        assert result['排除原因'] == '量測儀器故障'

        result = PatrolService.set_patrol_detail_exclusion(detail.id, excluded=False, reason='')
        assert result['排除統計'] is False
        assert result['排除原因'] is None


def test_set_patrol_detail_exclusion_raises_for_missing_id(app, db_session):
    with app.app_context():
        with pytest.raises(ValueError, match='不存在'):
            PatrolService.set_patrol_detail_exclusion(999999, excluded=True, reason='測試')


def test_get_spc_excludes_marked_outlier_from_stats(app, db_session):
    """標示為離群的量測明細應排除於統計計算之外，並反映於 excluded_count"""
    with app.app_context():
        for i in range(6):
            patrol = PatrolMain(date=date(2026, 1, i + 1), material='6061', spec='10*2')
            db_session.add(patrol)
            db_session.flush()
            db_session.add(PatrolDetail(
                main_id=patrol.id, group=1, item='外徑', position='前段',
                min_val=9.9, max_val=10.1
            ))
        db_session.commit()

        baseline = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert baseline['excluded_count'] == 0
        assert len(baseline['avgs']) == 6

        target_detail = PatrolDetail.query.join(PatrolMain).filter(
            PatrolMain.date == date(2026, 1, 1)
        ).first()
        PatrolService.set_patrol_detail_exclusion(target_detail.id, excluded=True, reason='量測異常')

        result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert result['excluded_count'] == 1
        assert len(result['avgs']) == 5


def test_get_spc_applies_frozen_limits(app, db_session):
    """管制界限凍結後，get_spc 回傳的界限應為凍結值而非重新計算值，
    且凍結子群體大小（avg_n）不同時，重算後的 d2 須確實傳遞到製程能力指數（Cwk），
    而非僅止於 x_cl/r_cl 等原始通過值"""
    with app.app_context():
        # 廠商公差：外徑標準值 10.0，公差 ±0.5（雙邊規格，允許 9.5–10.5）
        vt_main = VendorToleranceMain(material='6061', spec='10*2')
        db_session.add(vt_main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=vt_main.id, item='外徑',
            std_val=10.0, tolerance_min=0.5, tolerance_max=0.5
        ))

        rng = np.random.default_rng(2026)
        subgroup_means = rng.normal(10.0, 0.15, 30)
        for i, subgroup_mean in enumerate(subgroup_means):
            patrol = PatrolMain(date=date(2026, 1, i + 1), material='6061', spec='10*2')
            db_session.add(patrol)
            db_session.flush()
            db_session.add(PatrolDetail(
                main_id=patrol.id, group=1, item='外徑', position='前段',
                min_val=float(subgroup_mean - 0.1), max_val=float(subgroup_mean + 0.1)
            ))
        db_session.commit()

        result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert result['limits_frozen'] is False

        # 每組固定 2 筆量測值（max_val-min_val 恆為 0.2），即時重新計算的
        # r_cl 恰為 0.2、avg_n 必為 2；凍結時刻意將 r_cl 也設為 0.2（與即時
        # 重算值相同，排除 r_cl 差異的干擾），僅 avg_n 改為 5，
        # 讓兩者的 d2（SPC_CONSTANTS[2][3]=1.128 vs [5][3]=2.326）成為
        # sigma_within=r_cl/d2 唯一的變因，確保下方斷言真正隔離並驗證
        # d2 覆蓋邏輯本身，而非被 r_cl 的差異所混淆
        key = {"material": "6061", "spec": "10*2", "item": "外徑", "position": "前段"}
        PatrolService.freeze_control_limits(key, {
            "x_cl": 99.0, "x_ucl": 100.0, "x_lcl": 98.0,
            "r_cl": 0.2, "r_ucl": 2.0, "r_lcl": 0, "avg_n": 5,
        })

        frozen_result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert frozen_result['limits_frozen'] is True
        assert frozen_result['x_cl'] == pytest.approx(99.0)

        skip_result = PatrolService.get_spc(
            {'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'},
            skip_frozen_limits=True,
        )
        assert skip_result['x_cl'] != pytest.approx(99.0)

        # r_cl 已固定為 0.2（凍結值與即時重算值相同），故 Cwk 的差異只可能
        # 來自 d2（2.326 vs 1.128），證明 d2 覆蓋邏輯確實傳遞進製程能力計算，
        # 而非被 r_cl 的差異所掩蓋（若刪除 d2 覆蓋程式碼，此斷言應會失敗）
        frozen_cwk = frozen_result['process_capability']['cwk']
        skip_cwk = skip_result['process_capability']['cwk']
        assert frozen_cwk is not None and skip_cwk is not None
        assert frozen_cwk != pytest.approx(skip_cwk)


def test_get_spc_null_value_and_excluded_row_does_not_double_count(app, db_session):
    """量測明細無量測值且同時標示離群時，excluded_count 不應計入該列
    （刻意設計，非疏漏：此列本來就不會被計入統計，見 patrol_service.get_spc 註解）"""
    with app.app_context():
        patrol = PatrolMain(date=date(2026, 1, 1), material='6061', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        detail = PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=None, max_val=None
        )
        db_session.add(detail)
        db_session.commit()

        PatrolService.set_patrol_detail_exclusion(detail.id, excluded=True, reason='資料缺失')

        result = PatrolService.get_spc({'item': '外徑', 'pos': '前段', 'mat': '6061', 'spec': '10*2'})
        assert result['excluded_count'] == 0
        assert result['avgs'] == []
