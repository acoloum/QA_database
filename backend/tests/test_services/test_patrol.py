import pytest
from datetime import date
from backend.services.patrol_service import PatrolService
from backend.models import (
    PatrolMain, PatrolDetail,
    ExtrusionToleranceMain, ExtrusionToleranceDetail
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
