"""open_capa_from_ncmr 路由：軟刪除排除測試

驗證已軟刪除的不合格品單無法被開立 CAPA（資料完整性）。
"""
import datetime
from backend.models import AuditLog, CorrectiveAction, Role, User, NCMR
from backend.services.audit_service import AuditService
from backend.utils import hash_password, generate_token
from backend.extensions import db


def _auth_headers(db_session):
    """建立測試使用者並產生 JWT Header"""
    db_session.add(Role(
        code='qc_manager',
        name='品管主管',
        permissions={'ncmr.edit': True, 'capa.create': True},
    ))
    user = User(
        username='capa_test_user',
        password=hash_password('testpass123'),
        role='qc_manager',
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _make_ncmr(db_session, **kwargs):
    defaults = dict(
        ncmr_number='NCMR-SOFTDEL-001',
        date=datetime.date(2025, 1, 15),
        source='進料',
        description='測試不良描述',
        defect_quantity=5,
        status='待處理',
    )
    defaults.update(kwargs)
    n = NCMR(**defaults)
    db_session.add(n)
    db_session.commit()
    return n


def test_open_capa_blocked_for_soft_deleted_ncmr(app, client, db_session):
    """已軟刪除的 NCMR 不可開立 CAPA，應回 404 且不建立 CAPA"""
    with app.app_context():
        headers = _auth_headers(db_session)
        n = _make_ncmr(db_session)
        n.soft_delete()
        db.session.commit()

        resp = client.post(f'/api/ncmr/{n.id}/open-capa', headers=headers, json={})
        assert resp.status_code == 404
        # 確認未回寫關聯，亦即未建立 CAPA
        refreshed = db.session.get(NCMR, n.id)
        assert refreshed.related_capa_id is None


def test_open_capa_succeeds_for_active_ncmr(app, client, db_session):
    """未刪除的 NCMR 可正常開立 CAPA（確認修正未誤擋正常流程）"""
    with app.app_context():
        headers = _auth_headers(db_session)
        n = _make_ncmr(db_session, ncmr_number='NCMR-SOFTDEL-002')

        resp = client.post(f'/api/ncmr/{n.id}/open-capa', headers=headers, json={})
        assert resp.status_code == 201
        refreshed = db.session.get(NCMR, n.id)
        assert refreshed.related_capa_id is not None
        logs = AuditLog.query.filter_by(module='CAPA', action='create').all()
        assert len(logs) == 1
        assert logs[0].record_id == refreshed.related_capa_id


def test_open_capa_rolls_back_source_and_capa_when_audit_fails(
    app, client, db_session, monkeypatch
):
    """CAPA、來源狀態、來源關聯與稽核必須是同一筆交易。"""
    with app.app_context():
        headers = _auth_headers(db_session)
        ncmr = _make_ncmr(db_session, ncmr_number='NCMR-ATOMIC-CAPA')
        monkeypatch.setattr(
            AuditService,
            'record',
            staticmethod(
                lambda **_: (_ for _ in ()).throw(RuntimeError('secret audit down'))
            ),
        )

        response = client.post(
            f'/api/ncmr/{ncmr.id}/open-capa', headers=headers, json={}
        )

        assert response.status_code == 500
        assert response.get_json() == {
            'success': False,
            'error': {'code': 'INTERNAL_ERROR', 'message': '伺服器內部錯誤'},
        }
        db_session.expire_all()
        stored = db_session.get(NCMR, ncmr.id)
        assert stored.status == '待處理'
        assert stored.related_capa_id is None
        assert CorrectiveAction.query.count() == 0
        assert AuditLog.query.count() == 0
