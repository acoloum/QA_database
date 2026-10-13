"""機械性質檢驗 REST API 路由測試（含權限控管）。"""
import pytest

from backend.models import Role, User, Vendor, VendorToleranceDetail, VendorToleranceMain
from backend.utils import generate_token, hash_password


def _auth_headers(db_session, role_code, permissions):
    db_session.add(Role(code=role_code, name=role_code, permissions=permissions))
    user = User(username=f'{role_code}_user', password=hash_password('pw12345678'), role=role_code, is_active=True)
    db_session.add(user)
    db_session.flush()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_via_api(client, db_session):
    headers = _auth_headers(db_session, 'qc', {
        'mechanical.view': True, 'mechanical.create': True,
        'mechanical.edit': True, 'mechanical.delete': True,
    })
    db_session.commit()
    payload = {
        "產品尺寸": "36x25.2", "材質": "6061-T651", "測試日期": "2026-01-20",
        "extrusion_numbers": [{"序號": 1, "編號": "E1"}],
        "t4_furnace_numbers": [
            {"序號": 1, "編號": "T4-01"},
            {"序號": 2, "編號": "T4-02"},
        ],
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
    assert r3.get_json()["extrusion_numbers"][0]["編號"] == "E1"
    assert len(r3.get_json()["t4_furnace_numbers"]) == 2

    payload["batches"] = []
    invalid = client.post("/api/mechanical/tests", json=payload, headers=headers)
    assert invalid.status_code == 400


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
        "產品尺寸": "36x25.2", "材質": "6061-T651", "測試日期": False,
        "measurements": [],
    },
    {
        "產品尺寸": "36x25.2", "材質": "6061-T651", "測試日期": 0,
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
    headers = _auth_headers(db_session, 'qc', {'mechanical.view': True})
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
    headers = _auth_headers(db_session, 'qc', {'mechanical.view': True})
    db_session.commit()

    response = client.get(
        "/api/mechanical/spec?material=6061-T651&product_size=36x25.2&vendor_id=invalid",
        headers=headers,
    )

    assert response.status_code == 400


def test_get_spec_rejects_missing_vendor(client, db_session):
    headers = _auth_headers(db_session, 'qc', {'mechanical.view': True})
    db_session.commit()

    response = client.get(
        "/api/mechanical/spec?material=6061-T651&product_size=36x25.2&vendor_id=999999",
        headers=headers,
    )

    assert response.status_code == 400


def test_get_options_is_vendor_scoped(client, db_session):
    headers = _auth_headers(db_session, 'qc', {'mechanical.view': True})
    vendor = Vendor(name="安泰")
    other = Vendor(name="宏達")
    db_session.add_all([vendor, other])
    db_session.flush()
    db_session.add_all([
        VendorToleranceMain(vendor_id=vendor.id, material="6061-T651", spec="36*25.2"),
        VendorToleranceMain(vendor_id=other.id, material="7075", spec="99*99"),
    ])
    db_session.commit()

    response = client.get(
        f"/api/mechanical/options?vendor_id={vendor.id}", headers=headers
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "materials": ["6061-T651"],
        "product_sizes": ["36*25.2"],
    }


@pytest.mark.parametrize(("body", "content_type"), [
    ("", "application/json"),
    ("{broken", "application/json"),
    ('{"產品尺寸":"x","材質":"y"}', "text/plain"),
])
def test_create_rejects_invalid_json_request(client, db_session, body, content_type):
    headers = _auth_headers(db_session, 'qc', {'mechanical.create': True})
    db_session.commit()
    headers["Content-Type"] = content_type

    response = client.post("/api/mechanical/tests", data=body, headers=headers)

    assert response.status_code == 400


def _seed_outlier(db_session):
    from datetime import date
    from backend.models import MechanicalMeasurement, MechanicalTest
    for i in range(12):
        test = MechanicalTest(product_size="66.7*59", material="6061-T651", test_date=date(2026, 1, 1 + i))
        test.measurements.append(MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=60 + i))
        db_session.add(test)
    bad = MechanicalTest(product_size="66.7*59", material="6061-T651", test_date=date(2026, 2, 1))
    bad.measurements.append(MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=669))
    db_session.add(bad)
    db_session.flush()
    return bad.measurements[0].id


def test_suspect_measurements_via_api(client, db_session):
    headers = _auth_headers(db_session, 'qc_view', {'mechanical.view': True})
    measurement_id = _seed_outlier(db_session)
    db_session.commit()

    r = client.get("/api/mechanical/suspect-measurements", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 1
    assert body["data"][0]["識別碼"] == measurement_id
    assert "66.9" in body["data"][0]["提示"]

    invalid = client.get("/api/mechanical/suspect-measurements?item=EC值", headers=headers)
    assert invalid.status_code == 400


def test_suspect_measurements_requires_view_permission(client, db_session):
    headers = _auth_headers(db_session, 'nobody', {})
    db_session.commit()
    r = client.get("/api/mechanical/suspect-measurements", headers=headers)
    assert r.status_code == 403


def test_measurement_exclusion_via_api(client, db_session):
    headers = _auth_headers(db_session, 'qc_spc', {
        'mechanical.view': True, 'mechanical.edit': True, 'spc.manage': True,
    })
    measurement_id = _seed_outlier(db_session)
    db_session.commit()
    url = f"/api/mechanical/measurements/{measurement_id}/exclusion"

    missing_reason = client.patch(url, json={"排除統計": True, "排除原因": ""}, headers=headers)
    assert missing_reason.status_code == 400

    r = client.patch(url, json={"排除統計": True, "排除原因": "小數點誤植"}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()["排除統計"] is True

    suspects = client.get("/api/mechanical/suspect-measurements", headers=headers).get_json()
    assert suspects["total"] == 0

    not_found = client.patch(
        "/api/mechanical/measurements/999999/exclusion",
        json={"排除統計": True, "排除原因": "x"}, headers=headers,
    )
    assert not_found.status_code == 404


@pytest.mark.parametrize("permissions", [
    {'mechanical.edit': True},
    {'spc.manage': True},
])
def test_measurement_exclusion_requires_edit_and_spc_manage(client, db_session, permissions):
    headers = _auth_headers(db_session, 'partial', permissions)
    measurement_id = _seed_outlier(db_session)
    db_session.commit()
    r = client.patch(
        f"/api/mechanical/measurements/{measurement_id}/exclusion",
        json={"排除統計": True, "排除原因": "誤植"}, headers=headers,
    )
    assert r.status_code == 403
