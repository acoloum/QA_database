"""SPC 共用研究 API 契約與權限測試。"""

from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook

from backend.models import (
    Role,
    SpcEvent,
    SpcLimitVersion,
    SpcStudy,
    SpcStudyVersion,
    User,
)
from backend.services.spc_contracts import SpcStudyInput, SpcSubgroup
from backend.services.spc_study_service import ADAPTERS
from backend.utils import generate_token, hash_password


def _user(db_session, username, role_code):
    user = User(
        username=username, password=hash_password("pw12345678"),
        role=role_code, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user):
    token = generate_token(user.id, user.username, user.role)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def spc_roles(db_session):
    db_session.add_all([
        Role(code="spc_viewer", name="SPC檢視", permissions={"spc.view": True}),
        Role(
            code="spc_manager", name="SPC管理",
            permissions={"spc.view": True, "spc.manage": True},
        ),
        Role(
            code="spc_approver", name="SPC核准",
            permissions={"spc.view": True, "spc.manage": True, "spc.approve": True},
        ),
        Role(code="qa_supervisor", name="QA主管", permissions={"spc.manage": True}),
        Role(code="qc_manager", name="品管經理", permissions={"spc.manage": True}),
        Role(code="admin", name="系統管理員", permissions={"spc.manage": True}),
        Role(code="inspector", name="檢驗員", permissions={"spc.view": True}),
        Role(code="no_spc", name="無SPC權限", permissions={}),
    ])
    db_session.commit()


def _input(data_hash="a" * 64):
    return SpcStudyInput(
        source="shipping",
        filters={
            "vendor": "", "material": "6061", "spec": "10*1*100",
            "field": "外徑", "start_date": "", "end_date": "",
        },
        process_stream_key="api-stream", characteristic="外徑",
        subgroups=tuple(
            SpcSubgroup(
                key=f"shipping:{index}", timestamp=date(2026, 7, index + 1),
                values=(9.8 + index * 0.01, 10.2 + index * 0.01),
                record_ids=(index + 1,), measurement_ids=(index + 101,),
            )
            for index in range(5)
        ),
        specification={"found": True, "LSL": 9.5, "USL": 10.5},
        data_hash=data_hash,
    )


def test_viewer_can_analyze_and_read_study_contract(
    client, db_session, spc_roles, monkeypatch
):
    viewer = _user(db_session, "spc-viewer", "spc_viewer")
    monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())

    response = client.post(
        "/api/spc/studies/analyze", headers=_headers(viewer),
        json={"source": "shipping", "filters": {"field": "外徑"}},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    version = payload["data"]
    assert version["source"] == "shipping"
    assert version["study_type"] == "retrospective"
    assert version["process_stream_key"] == "api-stream"
    assert version["filters"]["field"] == "外徑"
    assert version["method_version"] == "2026.2"
    assert version["data_hash"] == "a" * 64
    assert version["charts"]["chart_type"] == "xbar_r"
    assert "location" in version["stability"]
    assert "applicable" in version["applicability"]

    listing = client.get("/api/spc/studies", headers=_headers(viewer))
    detail = client.get(
        f"/api/spc/studies/{version['study_id']}", headers=_headers(viewer)
    )
    history = client.get(
        f"/api/spc/studies/{version['study_id']}/history", headers=_headers(viewer)
    )
    assert listing.status_code == detail.status_code == history.status_code == 200
    assert listing.get_json()["data"][0]["id"] == version["study_id"]
    history_data = history.get_json()["data"]
    assert history_data["items"][0]["version_no"] == 1
    assert history_data["page"] == 1
    assert history_data["per_page"] == 20
    assert history_data["total"] == 1


def test_analyze_rejects_non_string_analysis_family_from_api(
    client, db_session, spc_roles
):
    viewer = _user(db_session, "spc-family-api-viewer", "spc_viewer")

    response = client.post(
        "/api/spc/studies/analyze",
        headers=_headers(viewer),
        json={"source": "shipping", "filters": {}, "analysis_family": []},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "SPC_ANALYSIS_FAMILY_INVALID"


def test_analyze_requires_spc_view_permission(client, db_session, spc_roles):
    user = _user(db_session, "no-spc", "no_spc")
    response = client.post(
        "/api/spc/studies/analyze", headers=_headers(user),
        json={"source": "shipping", "filters": {}},
    )
    assert response.status_code == 403


def test_spc_assignees_require_manage_and_expose_minimal_active_quality_users(
    client, db_session, spc_roles
):
    manager = _user(db_session, "assignee-reader", "spc_manager")
    viewer = _user(db_session, "assignee-viewer", "spc_viewer")
    qa = _user(db_session, "qa-choice", "qa_supervisor")
    qc = _user(db_session, "qc-choice", "qc_manager")
    admin = _user(db_session, "admin-choice", "admin")
    _user(db_session, "inspector-choice", "inspector")
    disabled = _user(db_session, "disabled-choice", "qa_supervisor")
    disabled.is_active = False
    db_session.commit()

    forbidden = client.get("/api/spc/assignees", headers=_headers(viewer))
    response = client.get("/api/spc/assignees", headers=_headers(manager))

    assert forbidden.status_code == 403
    assert response.status_code == 200
    rows = response.get_json()["data"]
    assert {row["id"] for row in rows} == {qa.id, qc.id, admin.id}
    assert set(rows[0]) == {"id", "username", "role", "role_name"}


def test_submit_data_hash_conflict_returns_stable_409_contract(
    client, db_session, spc_roles, monkeypatch
):
    manager = _user(db_session, "spc-manager", "spc_manager")
    values = iter((_input(), _input("b" * 64)))
    monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: next(values))
    analyzed = client.post(
        "/api/spc/studies/analyze", headers=_headers(manager),
        json={"source": "shipping", "filters": {}},
    ).get_json()["data"]

    response = client.post(
        f"/api/spc/study-versions/{analyzed['id']}/submit",
        headers=_headers(manager), json={"reason": "建立正式基準"},
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "success": False,
        "code": "STUDY_DATA_CHANGED",
        "message": "來源資料、規格或排除狀態已變更，請重新分析後再送審",
        "details": {"saved_hash": "a" * 64, "current_hash": "b" * 64},
    }


def test_manage_permission_cannot_call_approve_endpoint(
    client, db_session, spc_roles
):
    manager = _user(db_session, "manager-no-approve", "spc_manager")
    response = client.post(
        "/api/spc/study-versions/999/approve",
        headers=_headers(manager), json={"reason": "不應通過"},
    )
    assert response.status_code == 403


def test_legacy_limit_write_endpoints_are_gone(client, db_session, spc_roles):
    manager = _user(db_session, "legacy-manager", "spc_manager")
    for method in (client.post, client.delete):
        response = method(
            "/api/control-limits", headers=_headers(manager),
            json={} if method == client.post else None,
        )
        assert response.status_code == 410
        assert response.get_json()["code"] == "LEGACY_SPC_LIMITS_READ_ONLY"


def test_study_detail_exposes_limit_event_and_ocap_traceability(
    client, db_session, spc_roles, monkeypatch
):
    manager = _user(db_session, "trace-manager", "spc_manager")
    monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())
    analyzed = client.post(
        "/api/spc/studies/analyze", headers=_headers(manager),
        json={"source": "shipping", "filters": {}},
    ).get_json()["data"]

    limit = SpcLimitVersion(
        study_version_id=analyzed["id"], process_stream_key="api-stream",
        characteristic="外徑", revision=1, chart_type="xbar_r",
        limits={"location": {}, "variation": {}}, status="active",
        approved_by=manager.id,
    )
    db_session.add(limit)
    db_session.flush()
    event = SpcEvent(
        limit_version_id=limit.id, study_version_id=analyzed["id"],
        chart_kind="variation", rule_code="beyond_limits", point_index=4,
        observed_value=0.8, status="investigating",
    )
    db_session.add(event)
    db_session.flush()
    db_session.commit()

    created = client.post(
        f"/api/spc/events/{event.id}/ocap",
        headers=_headers(manager),
        json={
            "investigation_6m": {"summary": "壓力波動"},
            "owner_id": None,
            "status": "open",
        },
    )
    assert created.status_code == 200
    created_data = created.get_json()["data"]
    assert created_data["event_id"] == event.id
    assert created_data["investigation_6m"] == {"summary": "壓力波動"}
    assert "created_at" in created_data
    assert "updated_at" in created_data

    updated = client.patch(
        f"/api/spc/ocap/{created_data['id']}",
        headers=_headers(manager),
        json={"process_adjustment": "調整壓力", "status": "open"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["process_adjustment"] == "調整壓力"

    detail = client.get(
        f"/api/spc/studies/{analyzed['study_id']}", headers=_headers(manager)
    ).get_json()["data"]
    saved_limit = detail["versions"][0]["limit_versions"][0]

    assert saved_limit["id"] == limit.id
    assert saved_limit["status"] == "active"
    assert saved_limit["events"][0]["id"] == event.id
    assert saved_limit["events"][0]["ocap"]["investigation_6m"] == {
        "summary": "壓力波動"
    }

    event_response = client.get(
        f"/api/spc/events/{event.id}", headers=_headers(manager)
    )
    assert event_response.status_code == 200
    event_data = event_response.get_json()["data"]
    assert event_data["id"] == event.id
    assert event_data["ocap"]["id"] == created_data["id"]


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ([], "SPC_OCAP_PAYLOAD_INVALID"),
        ({"status": "unknown"}, "SPC_OCAP_STATUS_INVALID"),
        ({"owner_id": True}, "SPC_OCAP_OWNER_INVALID"),
    ],
)
def test_ocap_route_returns_stable_validation_contract(
    client, db_session, spc_roles, payload, expected_code
):
    manager = _user(db_session, f"payload-{expected_code}", "spc_manager")
    study = SpcStudy(
        source="shipping",
        study_type="ongoing",
        process_stream_key=f"route-{expected_code}",
        characteristic="外徑",
        filters={},
        status="active",
        created_by=manager.id,
    )
    db_session.add(study)
    db_session.flush()
    version = SpcStudyVersion(
        study_id=study.id,
        version_no=1,
        method_version="2026.1",
        status="active",
        created_by=manager.id,
    )
    db_session.add(version)
    db_session.flush()
    limit = SpcLimitVersion(
        study_version_id=version.id,
        process_stream_key=study.process_stream_key,
        characteristic=study.characteristic,
        revision=1,
        chart_type="xbar_s",
        limits={},
        status="active",
        created_by=manager.id,
    )
    db_session.add(limit)
    db_session.flush()
    event = SpcEvent(
        limit_version_id=limit.id,
        study_version_id=version.id,
        chart_kind="location",
        rule_code="beyond_limits",
        point_index=0,
    )
    db_session.add(event)
    db_session.commit()

    response = client.post(
        f"/api/spc/events/{event.id}/ocap",
        headers=_headers(manager),
        json=payload,
    )

    assert response.status_code == 422
    assert response.get_json()["code"] == expected_code


def test_spc_report_requires_view_permission(client, db_session, spc_roles):
    user = _user(db_session, "report-no-spc", "no_spc")

    response = client.get("/api/spc-report", headers=_headers(user))

    assert response.status_code == 403


def test_shipping_report_rejects_other_source_and_uses_only_saved_version(
    client, db_session, spc_roles, monkeypatch
):
    viewer = _user(db_session, "report-viewer", "spc_viewer")
    monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters: _input())
    analyzed = client.post(
        "/api/spc/studies/analyze", headers=_headers(viewer),
        json={"source": "shipping", "filters": {"field": "外徑"}},
    ).get_json()["data"]

    patrol_response = client.get(
        f"/api/patrol/export?item=外徑&study_version_id={analyzed['id']}",
        headers=_headers(viewer),
    )
    shipping_response = client.get(
        "/api/spc-report?field=外徑&material=6061&spec=10*1*100"
        f"&study_version_id={analyzed['id']}",
        headers=_headers(viewer),
    )

    assert patrol_response.status_code == 422
    assert shipping_response.status_code == 200
    workbook = load_workbook(BytesIO(shipping_response.data))
    assert "原始數據" not in workbook.sheetnames
    assert "研究樣本" in workbook.sheetnames
