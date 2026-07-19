"""在隔離 PostgreSQL database 中執行時間模型確認競態。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

from backend.app import app
from backend.extensions import db
from backend.models import AuditLog, Role, SpcStudy, SpcStudyVersion, User
from backend.services.spc_errors import SpcConflict
from backend.services import spc_study_service as service_module
from backend.services.spc_study_service import SpcStudyService


def _prepare() -> tuple[int, int]:
    with app.app_context():
        db.create_all()
        role = Role(
            code="pg_spc_approver",
            name="PG SPC 核准",
            permissions={"spc.approve": True},
        )
        actor = User(
            username="pg-time-model-approver",
            password="integration-only",
            role=role.code,
            is_active=True,
        )
        study = SpcStudy(
            source="shipping",
            study_type="retrospective",
            analysis_family="variable",
            process_stream_key="pg-time-model-concurrency",
            characteristic="外徑",
            filters={},
            status="draft",
        )
        version = SpcStudyVersion(
            study=study,
            version_no=1,
            method_version="2026.2",
            code_version="integration",
            data_hash="a" * 64,
            analysis_options={},
            specification_snapshot={},
            chart_result={},
            stability_result={},
            distribution_result={},
            time_model_result={
                "candidate": "C1",
                "confirmed": False,
                "diagnostic_version": "2026.2",
                "reason_code": None,
                "evidence": {"source": "postgres-concurrency"},
            },
            capability_result={},
            applicability_result={},
            status="draft",
        )
        db.session.add_all([role, actor, version])
        db.session.commit()
        return version.id, actor.id


def main() -> None:
    original_id, actor_id = _prepare()
    # 此競態只驗證鎖、CAS、版本與 audit；能力重算已有獨立服務測試。
    service_module._recalculate_capability = lambda _version, _model: {
        "available": False,
        "cp": None,
        "cpk": None,
    }
    barrier = Barrier(2)

    def confirm(model: str) -> dict[str, object]:
        with app.app_context():
            barrier.wait(timeout=10)
            try:
                successor = SpcStudyService.confirm_time_model(
                    original_id,
                    actor_id,
                    model=model,
                    reason=f"PG 並發確認 {model}",
                )
                return {"status": "confirmed", "id": successor.id}
            except SpcConflict as error:
                return {"status": "conflict", "code": error.code}
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(confirm, ("C1", "C2")))

    with app.app_context():
        original = db.session.get(SpcStudyVersion, original_id)
        versions = SpcStudyVersion.query.filter_by(study_id=original.study_id).all()
        audits = AuditLog.query.filter_by(
            action="confirm_time_model", module="spc_study"
        ).all()
        payload = {
            "outcomes": outcomes,
            "version_count": len(versions),
            "successor_count": sum(version.id != original_id for version in versions),
            "audit_count": len(audits),
            "original_status": original.status,
        }
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
