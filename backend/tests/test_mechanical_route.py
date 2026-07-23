"""機械性質檢驗 REST API 路由測試（含權限控管）。"""
import pytest

from backend.models import Role, User, Vendor, VendorToleranceDetail, VendorToleranceMain
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


@pytest.mark.parametrize("payload", [
    {"材質": "6061-T651"},
    {
        "產品尺寸": "36x25.2", "材質": "6061-T651", "測試日期": "not-a-date",
        "measurements": [],
    },
    {
        "產品尺寸": "36x25.2", "材質": "6061-T651",
        "measurements": [{"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": "NaN"}],
    },
])
def test_create_invalid_payload_returns_400(client, db_session, payload):
    headers = _auth_headers(db_session, 'qc', {'mechanical.create': True})
    db_session.commit()

    response = client.post("/api/mechanical/tests", json=payload, headers=headers)

    assert response.status_code == 400


def test_missing_test_remains_404(client, db_session):
    headers = _auth_headers(db_session, 'qc', {'mechanical.edit': True})
    db_session.commit()

    response = client.put(
        "/api/mechanical/tests/999", json={"產品尺寸": "36x25.2", "材質": "6061-T651"}, headers=headers
    )

    assert response.status_code == 404


def test_get_spec_accepts_vendor_id_and_scopes_limits(client, db_session):
    headers = _auth_headers(db_session, 'qc', {})
    first_vendor = Vendor(name="安泰")
    second_vendor = Vendor(name="宏達")
    db_session.add_all([first_vendor, second_vendor])
    db_session.flush()
    for vendor, lower_limit in [(first_vendor, 60), (second_vendor, 75)]:
        main = VendorToleranceMain(vendor_id=vendor.id, material="6061-T651", spec="36*25.2")
        db_session.add(main)
        db_session.flush()
        db_session.add(VendorToleranceDetail(
            main_id=main.id, item="洛氏硬度", tolerance_min=lower_limit, unit=""
        ))
    db_session.commit()

    response = client.get(
        f"/api/mechanical/spec?material=6061-T651&product_size=36x25.2&vendor_id={second_vendor.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["limits"]["硬度"] == 75


def test_get_spec_rejects_invalid_vendor_id(client, db_session):
    headers = _auth_headers(db_session, 'qc', {})
    db_session.commit()

    response = client.get(
        "/api/mechanical/spec?material=6061-T651&product_size=36x25.2&vendor_id=invalid",
        headers=headers,
    )

    assert response.status_code == 400
