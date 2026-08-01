"""巡檢即時界限查詢路由的權限與契約測試。"""
import pytest
from backend.models import Role, User
from backend.utils import hash_password, generate_token


def _user(db_session, username, role_code):
    user = User(username=username, password=hash_password('pw12345678'),
                role=role_code, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user):
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


@pytest.fixture
def spc_view_roles(db_session):
    db_session.add_all([
        Role(code='spc_viewer', name='SPC檢視', permissions={'spc.view': True}),
        Role(code='no_spc', name='無SPC權限', permissions={}),
    ])
    db_session.commit()


def test_live_limits_route_requires_spc_view(client, db_session, spc_view_roles):
    user = _user(db_session, 'no_spc_user', 'no_spc')
    resp = client.get(
        '/api/patrol/live-limits?mat=SUS304&spec=10*2&item=外徑&pos=前段',
        headers=_headers(user),
    )
    assert resp.status_code == 403


def test_live_limits_route_allows_spc_view_and_returns_not_found(client, db_session, spc_view_roles):
    user = _user(db_session, 'viewer_user', 'spc_viewer')
    resp = client.get(
        '/api/patrol/live-limits?mat=SUS304&spec=10*2&item=外徑&pos=前段',
        headers=_headers(user),
    )
    assert resp.status_code == 200
    assert resp.get_json() == {'found': False}
