import pytest
from datetime import date
from backend.services.patrol_service import PatrolService
from backend.models import (
    PatrolMain, PatrolDetail,
    ExtrusionToleranceMain, ExtrusionToleranceDetail,
    VendorToleranceMain, VendorToleranceDetail, Vendor,
)


def test_get_history_is_ng_true(app, db_session):
    """量測值超出押出公差時，is_ng 應為 True"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*10*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            tolerance_min=0.5, tolerance_max=1.5
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=0.8, max_val=2.0  # 2.0 超出上限 1.5
        ))
        db_session.commit()

        result = PatrolService.get_history({'page': 1, 'per_page': 20})
        assert len(result['data']) == 1
        row = result['data'][0]
        assert row['is_ng'] is True
        assert row['tol_found'] is True


def test_get_history_is_ng_false(app, db_session):
    """量測值在公差範圍內時，is_ng 應為 False"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*10*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            tolerance_min=0.5, tolerance_max=1.5
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=0.8, max_val=1.2  # 在範圍內
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
    """同心度（厚度 max_val - min_val）超差時，is_ng 應為 True"""
    with app.app_context():
        et_main = ExtrusionToleranceMain(material='SUS304', spec='10*10*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='同心度',
            tolerance_min=0.0, tolerance_max=0.3
        ))

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*10*100')
        db_session.add(patrol)
        db_session.flush()
        # 同心度 = 1.5 - 0.8 = 0.7，超出上限 0.3
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


def test_get_history_prefers_vendor_tolerance(app, db_session):
    """廠商+材質+規格三者相近時，優先套用廠商公差，而非押出公差"""
    with app.app_context():
        vendor = Vendor(name='廠商甲')
        db_session.add(vendor)
        db_session.flush()

        # 廠商公差：外徑標準值 10.0，公差 ±0.1（允許 9.9–10.1）
        vt_main = VendorToleranceMain(
            vendor_id=vendor.id, material='6061', spec='10*2'
        )
        db_session.add(vt_main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=vt_main.id, item='外徑',
            std_val=10.0, tolerance_min=0.1, tolerance_max=0.1
        ))

        # 押出公差：外徑標準值 10.0，公差 ±1.0（允許 9.0–11.0，更寬鬆）
        et_main = ExtrusionToleranceMain(material='6061', spec='10*2*100')
        db_session.add(et_main)
        db_session.flush()
        db_session.add(ExtrusionToleranceDetail(
            main_id=et_main.id, item='外徑',
            std_val=10.0, tolerance_min=1.0, tolerance_max=1.0
        ))

        # 巡檢紀錄：外徑 = 10.5（超出廠商公差 ±0.1，但在押出公差 ±1.0 內）
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
        # 若正確套用廠商公差（±0.1），10.5 超差 → is_ng=True
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
