"""機械性質檢驗 REST API 路由測試（含權限控管）。"""
from backend.models import Role, User
from backend.utils import generate_token, hash_password


def _auth_headers(db_session, role_code, permissions):
    db_session.add(Role(code=role_code, name=role_code, permissions=permissions))
    user = User(username=f'{role_code}_user', password=hash_password('pw12345678'), role=role_code, is_active=True)
    db_session.add(user)
    db_session.flush()
    token = generate_token(user.id, user.username, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_via_api(client, db_session):
    headers = _auth_headers(db_session, 'qc', {
        'mechanical.create': True, 'mechanical.edit': True, 'mechanical.delete': True,
    })
    db_session.commit()
    payload = {
        "產品尺寸": "36x25.2", "材質": "6061-T651", "測試日期": "2026-01-20",
        "measurements": [{"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 70}],
    }
    r = client.post("/api/mechanical/tests", json=payload, headers=headers)
    assert r.status_code == 200
    new_id = r.get_json()["id"]

    r2 = client.get("/api/mechanical/tests?product_size=36", headers=headers)
    assert r2.status_code == 200
    assert r2.get_json()["total"] == 1

    r3 = client.get(f"/api/mechanical/tests/{new_id}", headers=headers)
    assert r3.status_code == 200
    assert r3.get_json()["main"]["材質"] == "6061-T651"


def test_create_requires_permission(client, db_session):
    headers = _auth_headers(db_session, 'viewer', {})
    db_session.commit()
    r = client.post("/api/mechanical/tests", json={"產品尺寸": "x", "材質": "y"}, headers=headers)
    assert r.status_code == 403
