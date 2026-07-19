"""屬性型 SPC 研究版本、持續監控與報表的生命週期測試。"""

from datetime import date

import pytest
from openpyxl import load_workbook

import backend.services.spc_study_service as study_module
from backend.models import Role, SpcLimitVersion, User
from backend.services.spc_attribute_engine import AttributeSubgroup
from backend.services.spc_contracts import SpcStudyInput
from backend.services.spc_report import SpcReportService
from backend.services.spc_study_service import ADAPTERS, SpcStudyService


def _viewer(db_session):
    db_session.add(Role(
        code="attribute_viewer", name="屬性研究檢視", permissions={"spc.view": True}
    ))
    user = User(username="attribute-viewer", password="hashed", role="attribute_viewer")
    db_session.add(user)
    db_session.flush()
    return user


def _attribute_input(*, counts=(3, 4, 2, 3, 5), options=None, data_hash="a" * 64):
    return SpcStudyInput(
        source="shipping",
        filters={"field": "外徑", "material": "6061", "spec": "10*1*100"},
        process_stream_key="attribute-shipping-stream",
        characteristic="不符合單位",
        analysis_family="attribute",
        options=dict(options or {}),
        data_hash=data_hash,
        specification={"found": True, "source": "measurement_and_specification_snapshot"},
        subgroups=tuple(
            AttributeSubgroup(
                key=f"attribute:{index}", timestamp=date(2026, 7, index + 1),
                inspected=100, nonconforming=count, record_ids=(index + 1,),
            )
            for index, count in enumerate(counts)
        ),
        metadata={
            "classification_evidence": [{"record_id": index + 1, "eligible": True}
                                        for index in range(len(counts))],
            "classification_snapshot": [],
            "eligible_record_count": len(counts),
            "excluded_record_count": 0,
        },
    )


def _adapter(_filters, *, analysis_family, options, input_contract_version):
    assert analysis_family == "attribute"
    assert input_contract_version == "2026.2"
    return _attribute_input(options=options)


def test_attribute_analysis_persists_family_counts_and_exact_limits(
    app, db_session, monkeypatch
):
    with app.app_context():
        actor = _viewer(db_session)
        monkeypatch.setitem(ADAPTERS, "shipping", _adapter)

        version = SpcStudyService.analyze(
            "shipping", {"field": "外徑"}, actor.id,
            analysis_family="attribute",
            options={"interval": "day", "chart_type": "p"},
        )

        assert version.study.analysis_family == "attribute"
        assert version.method_version == "2026.2"
        assert version.chart_result["chart_type"] == "p"
        assert version.chart_result["x"] == [3, 4, 2, 3, 5]
        assert version.chart_result["n"] == [100] * 5
        assert version.chart_result["exact_alpha"] == pytest.approx(0.0027)
        assert version.chart_result["interval"] == "day"
        assert version.chart_result["eligibility_evidence"][0]["eligible"] is True
        assert version.chart_result["exclusion_evidence"] == []
        assert version.stability_result["residual_method"] == "binomial_pearson"
        assert version.analysis_options == {"interval": "day", "chart_type": "p"}
        assert version.samples[0].values == [3.0, 100.0]


def test_attribute_ongoing_uses_approved_limits_without_recentering(
    app, db_session, monkeypatch
):
    with app.app_context():
        actor = _viewer(db_session)
        monkeypatch.setitem(ADAPTERS, "shipping", _adapter)
        baseline = SpcStudyService.analyze(
            "shipping", {"field": "外徑"}, actor.id,
            analysis_family="attribute",
            options={"interval": "day", "chart_type": "p"},
        )
        limit = SpcLimitVersion(
            study_version_id=baseline.id,
            analysis_family="attribute",
            process_stream_key=baseline.study.process_stream_key,
            characteristic=baseline.study.characteristic,
            revision=1,
            chart_type="p",
            limits={
                "center": baseline.chart_result["center"],
                "alpha": baseline.chart_result["exact_alpha"],
                "interval": "day",
                "baseline_n": 100,
                "rules_used": ["beyond_limits", "run_9_same_side", "trend_6"],
            },
            status="active", created_by=actor.id, approved_by=actor.id,
        )
        db_session.add(limit)
        db_session.commit()
        monkeypatch.setitem(
            ADAPTERS, "shipping",
            lambda _filters, *, analysis_family, options, input_contract_version:
                _attribute_input(counts=(8, 7, 9, 8, 10), options=options, data_hash="b" * 64),
        )

        ongoing = SpcStudyService.analyze(
            "shipping", {"field": "外徑"}, actor.id, study_type="ongoing",
            analysis_family="attribute",
            options={"interval": "day", "chart_type": "p"},
        )

        assert ongoing.chart_result["center"] == baseline.chart_result["center"]
        assert ongoing.chart_result["x"] == [8, 7, 9, 8, 10]
        assert ongoing.stability_result["residual_method"] == "binomial_pearson"
        assert ongoing.time_model_result["limit_version_id"] == limit.id


def test_attribute_report_includes_immutable_counts_and_method_metadata(
    app, db_session, monkeypatch
):
    with app.app_context():
        actor = _viewer(db_session)
        monkeypatch.setitem(ADAPTERS, "shipping", _adapter)
        version = SpcStudyService.analyze(
            "shipping", {"field": "外徑"}, actor.id,
            analysis_family="attribute",
            options={"interval": "week", "chart_type": "p"},
        )

        workbook = load_workbook(SpcReportService.generate_version_report(version.id))
        audit = {
            workbook["版本稽核"].cell(row=row, column=1).value:
            workbook["版本稽核"].cell(row=row, column=2).value
            for row in range(1, workbook["版本稽核"].max_row + 1)
        }
        headers = [cell.value for cell in workbook["管制圖數據"][1]]

        assert audit["研究版本ID"] == version.id
        assert audit["資料雜湊"] == version.data_hash
        assert audit["方法版本"] == "2026.2"
        assert audit["分析族別"] == "attribute"
        assert audit["時間區間"] == "week"
        assert "受檢數(n)" in headers
        assert "不符合數(x)" in headers
