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
