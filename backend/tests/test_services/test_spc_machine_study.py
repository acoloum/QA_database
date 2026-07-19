"""巡檢機器績效研究資格與核准測試。"""

from datetime import date, timedelta

import pytest

from backend.models import Role, SpcLimitVersion, User
from backend.services.spc_contracts import SpcStudyInput, SpcSubgroup
from backend.services.spc_errors import SpcValidationError
from backend.services.spc_study_service import ADAPTERS, SpcStudyService
from backend.utils import hash_password
from backend.utils import generate_token


def _user(db_session, username, role):
    user = User(username=username, password=hash_password("pw12345678"), role=role)
    db_session.add(user)
    db_session.commit()
    return user


def _machine_input():
    values = tuple(10.0 + index * 0.004 for index in range(50))
    return SpcStudyInput(
        source="patrol",
        filters={"m_id": 1, "mat": "6061", "spec": "10*1*100", "item": "外徑", "pos": "前段"},
        process_stream_key="machine-stream",
        characteristic="外徑",
        subgroups=tuple(
            SpcSubgroup(
                key=f"patrol:{index}", timestamp=date(2026, 7, 1) + timedelta(days=index),
                values=(value,), distribution_values=(value,), record_ids=(index + 1,), measurement_ids=(index + 101,),
            )
            for index, value in enumerate(values)
        ),
        specification={"found": True, "consistent": True, "LSL": 9.0, "USL": 11.0, "characteristic_class": "主要"},
        options={"conditions_confirmed": True, "condition_reason": "固定機台設定、量具與原料批次均已確認"},
        data_hash="a" * 64,
        metadata={"source_semantics": "patrol_min_max_observations", "operators": [1, 2]},
        analysis_family="machine",
    )


def test_machine_research_approves_without_creating_spc_limits(app, db_session, monkeypatch):
    with app.app_context():
        db_session.add_all([
            Role(code="spc_manager", name="SPC管理", permissions={"spc.view": True, "spc.manage": True}),
            Role(code="spc_approver", name="SPC核准", permissions={"spc.approve": True}),
        ])
        db_session.commit()
        manager = _user(db_session, "machine-manager", "spc_manager")
        approver = _user(db_session, "machine-approver", "spc_approver")
        monkeypatch.setitem(ADAPTERS, "patrol", lambda _filters, **_kwargs: _machine_input())

        version = SpcStudyService.analyze(
            "patrol", _machine_input().filters, manager.id,
            analysis_family="machine", options=_machine_input().options,
        )
        SpcStudyService.submit(version.id, manager.id, reason="送審機器績效研究")
        approved = SpcStudyService.approve_research(
            version.id, approver.id, reason="條件與績效證據完整"
        )

        assert approved.status == approved.study.status == "approved"
        assert SpcLimitVersion.query.count() == 0


def test_machine_analysis_requires_patrol_and_complete_exact_filters(app, db_session):
    with app.app_context():
        db_session.add(Role(code="spc_viewer", name="SPC檢視", permissions={"spc.view": True}))
        db_session.commit()
        viewer = _user(db_session, "machine-viewer", "spc_viewer")

        with pytest.raises(SpcValidationError) as exc:
            SpcStudyService.analyze(
                "shipping", {"m_id": 1, "mat": "6061", "spec": "10*1*100", "item": "外徑", "pos": "前段"},
                viewer.id, analysis_family="machine",
                options={"conditions_confirmed": True, "condition_reason": "條件確認"},
            )

        assert exc.value.code == "MACHINE_SOURCE_UNSUPPORTED"


def test_machine_research_approval_api_requires_approval_permission(client, app, db_session, monkeypatch):
    with app.app_context():
        db_session.add_all([
            Role(code="spc_manager", name="SPC管理", permissions={"spc.view": True, "spc.manage": True}),
            Role(code="spc_approver", name="SPC核准", permissions={"spc.approve": True}),
        ])
        db_session.commit()
        manager = _user(db_session, "machine-api-manager", "spc_manager")
        approver = _user(db_session, "machine-api-approver", "spc_approver")
        monkeypatch.setitem(ADAPTERS, "patrol", lambda _filters, **_kwargs: _machine_input())
        version = SpcStudyService.analyze(
            "patrol", _machine_input().filters, manager.id,
            analysis_family="machine", options=_machine_input().options,
        )
        SpcStudyService.submit(version.id, manager.id, reason="送審機器績效研究")
        headers = {
            "Authorization": f"Bearer {generate_token(approver.id, approver.username, approver.role)}",
            "Content-Type": "application/json",
        }

        response = client.post(
            f"/api/spc/study-versions/{version.id}/approve-research",
            headers=headers, json={"reason": "完成機器研究核准"},
        )

        assert response.status_code == 200
        assert response.get_json()["data"]["status"] == "approved"


def test_confirmed_c_model_research_uses_limit_free_approval(app, db_session, monkeypatch):
    with app.app_context():
        db_session.add_all([
            Role(code="spc_viewer", name="SPC檢視", permissions={"spc.view": True}),
            Role(code="spc_approver", name="SPC核准", permissions={"spc.approve": True}),
        ])
        db_session.commit()
        viewer = _user(db_session, "research-viewer", "spc_viewer")
        approver = _user(db_session, "research-approver", "spc_approver")
        study_input = SpcStudyInput(
            source="shipping", filters={"field": "外徑"}, process_stream_key="c-model-stream",
            characteristic="外徑",
            subgroups=tuple(
                SpcSubgroup(
                    key=f"shipping:{index}", timestamp=date(2026, 7, index + 1),
                    values=(9.9 + index * 0.01, 10.1 + index * 0.01),
                    record_ids=(index + 1,), measurement_ids=(index + 101,),
                ) for index in range(5)
            ),
            specification={"found": True, "LSL": 9.0, "USL": 11.0}, data_hash="c" * 64,
        )
        from backend.models import SpcStudy, SpcStudyVersion
        study = SpcStudy(
            source="shipping", study_type="retrospective", analysis_family="variable",
            process_stream_key="c-model-stream", characteristic="外徑", filters={"field": "外徑"},
            status="submitted", created_by=viewer.id,
        )
        db_session.add(study)
        db_session.flush()
        version = SpcStudyVersion(
            study_id=study.id, version_no=1, method_version="2026.2", data_hash="c" * 64,
            analysis_options={}, specification_snapshot={"found": True, "LSL": 9.0, "USL": 11.0},
            time_model_result={"model": "C1", "confirmed": True}, status="submitted",
            created_by=viewer.id,
        )
        db_session.add(version)
        db_session.commit()
        monkeypatch.setitem(ADAPTERS, "shipping", lambda _filters, **_kwargs: study_input)

        approved = SpcStudyService.approve_research(
            version.id, approver.id, reason="時間模型研究證據已確認"
        )

        assert approved.status == "approved"
        assert SpcLimitVersion.query.count() == 0
