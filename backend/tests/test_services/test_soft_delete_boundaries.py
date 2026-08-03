"""軟刪除邊界：已刪除的單據不得出現在清單、統計與子表查詢中。

這幾條原本各自漏了 deleted_at 過濾，導致已刪除的 8D 出現在逾期清單、
已刪除客訴計入保固統計、已刪除 8D 計入廠商績效分數。
"""
import datetime

from backend.extensions import db
from backend.models import (
    CorrectiveAction,
    CustomerComplaint,
    NCMR,
    ReworkRequest,
    User,
    Vendor,
)
from backend.utils import generate_token


def _admin_headers(db_session, username):
    user = User(username=username, password='pw', role='admin', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}'}


def _overdue_capa(db_session, number):
    ca = CorrectiveAction(
        eight_d_number=number,
        source_type='ncmr',
        status='進行中',
        d0_deadline=datetime.date(2020, 1, 1),      # 必定逾期
    )
    db_session.add(ca)
    db_session.flush()
    return ca


def test_overdue_capa_list_excludes_soft_deleted(app, client, db_session):
    headers = _admin_headers(db_session, 'overdue_capa_user')
    kept = _overdue_capa(db_session, 'CAPA-OVERDUE-KEEP')
    removed = _overdue_capa(db_session, 'CAPA-OVERDUE-DELETED')
    removed.soft_delete()
    db_session.commit()

    response = client.get('/api/capas/overdue', headers=headers)

    assert response.status_code == 200
    numbers = {row['no'] for row in response.get_json()}
    assert kept.eight_d_number in numbers
    assert removed.eight_d_number not in numbers


def test_warranty_stats_excludes_soft_deleted_complaints(app, db_session):
    from backend.services.complaint_stats_service import ComplaintStatsService

    for index, deleted in ((0, False), (1, True)):
        complaint = CustomerComplaint(
            complaint_no=f'CC-WARRANTY-{index}',
            customer='客戶A',
            complaint_date=datetime.date(2026, 5, 1),
            description='保固失效',
            complaint_type='warranty',
            status='處理中',
            failure_hours=100,
        )
        db_session.add(complaint)
        db_session.flush()
        if deleted:
            complaint.soft_delete()
    db_session.commit()

    stats = ComplaintStatsService.warranty_stats()

    assert stats['total'] == 1
    assert stats['warranty_count'] == 1


def test_vendor_performance_excludes_soft_deleted_capa(app, db_session):
    from backend.services.vendor_performance_service import VendorPerformanceService

    vendor = Vendor(name='績效廠商')
    db_session.add(vendor)
    db_session.flush()

    ncmr = NCMR(
        ncmr_number='NCMR-PERF-001',
        date=datetime.date(2026, 5, 2),
        source='進料',
        vendor=vendor.name,
        description='不良',
        status='待處理',
    )
    db_session.add(ncmr)
    db_session.flush()

    created_at = datetime.datetime(2026, 5, 2, 8, 0, 0)
    kept = CorrectiveAction(
        eight_d_number='CAPA-PERF-KEEP', ncmr_id=ncmr.id,
        source_type='ncmr', source_id=ncmr.id, status='進行中',
    )
    removed = CorrectiveAction(
        eight_d_number='CAPA-PERF-DELETED', ncmr_id=ncmr.id,
        source_type='ncmr', source_id=ncmr.id, status='進行中',
    )
    db_session.add_all([kept, removed])
    db_session.flush()
    kept.created_at = created_at
    removed.created_at = created_at
    removed.soft_delete()
    db_session.commit()

    # 走實際使用的聚合路徑（refresh_period → calculate_period）
    from backend.services.vendor_performance_service import parse_period
    rows = VendorPerformanceService.calculate_period(parse_period('2026-05'))
    row = next(r for r in rows if r['vendor_id'] == vendor.id)

    assert row['capa_count'] == 1

    # 單筆路徑（get_or_calculate）也要一致
    single = VendorPerformanceService.get_or_calculate(vendor.id, '2026-05')
    assert single['capa_count'] == 1


def test_soft_deleted_rework_children_are_not_readable(app, db_session):
    from backend.services.rework_service import ReworkService

    req = ReworkRequest(
        rework_number='RW-SOFTDEL-001',
        status='執行中',
        reason='重工',
    )
    db_session.add(req)
    db_session.commit()

    assert ReworkService.get_execution_list(req.rework_number) == []
    assert ReworkService._resolve_rework_id(req.rework_number) == req.id

    req.soft_delete()
    db.session.commit()

    # 主檔已軟刪除後，單號與識別碼都不應再解析得到子表資料
    assert ReworkService._resolve_rework_id(req.rework_number) is None
    assert ReworkService._resolve_rework_id(req.id) is None
