"""把凍結計畫與有效觀測餵給受控統計引擎，產生不可變結果版本。

分析在單一交易內完成：任何一步失敗都不留下半成品結果。結果的
raw_data_summary 保存完整的分析輸入，讓報告與歷史畫面永遠讀得到
當時的證據，而不受後續主檔或觀測狀態變動影響。
"""

from datetime import datetime, timezone
from decimal import Decimal

from ..extensions import db
from ..models import (
    MsaObservation,
    MsaPlanVersion,
    MsaResultVersion,
    MsaStudy,
    MsaWorkflowDecision,
)
from ..utils import log_audit
from .msa_contracts import MsaMethodContext
from .msa_errors import (
    MsaConflict,
    MsaNotFound,
    MsaValidationError,
)
from .msa_evaluation import evaluate
from .msa_method_registry import MsaMethodRegistry
from .msa_numeric import MsaNumericError, canonical_hash, require_finite_tree
from .msa_observation_service import MsaObservationService


# 統計引擎的程式版本；引擎行為改變時必須同步調整，讓結果可追溯
CODE_VERSION = "msa-engine-1.0.0"

# collecting 也允許：完整性檢查會擋下資料未齊的情形，錯誤訊息更精確
_ANALYZABLE_STATUSES = {
    "collecting", "ready_for_analysis", "analyzed", "rejected",
}


class MsaAnalysisService:
    """以受控方法與凍結準則產生 MSA 結果版本。"""

    @staticmethod
    def analyze(
        plan_id: int, *, actor_id: int, expected_plan_hash=None,
    ) -> MsaResultVersion:
        try:
            plan = (
                MsaPlanVersion.query
                .filter_by(id=plan_id)
                .with_for_update()
                .one_or_none()
            )
            if plan is None:
                raise MsaNotFound(
                    "MSA_PLAN_NOT_FOUND",
                    "找不到 MSA 計畫版本",
                    details={"plan_id": plan_id},
                )
            if plan.frozen_at is None:
                raise MsaConflict(
                    "MSA_PLAN_NOT_FROZEN",
                    "計畫尚未凍結，不可產生正式結果",
                    details={"plan_id": plan_id},
                )
            if (
                expected_plan_hash is not None
                and expected_plan_hash != plan.plan_hash
            ):
                raise MsaConflict(
                    "MSA_DATA_CHANGED",
                    "計畫內容已變更，請重新載入後再分析",
                    details={
                        "expected_plan_hash": expected_plan_hash,
                        "actual_plan_hash": plan.plan_hash,
                    },
                )

            study = (
                MsaStudy.query
                .filter_by(id=plan.study_id)
                .with_for_update()
                .one()
            )
            if study.status not in _ANALYZABLE_STATUSES:
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "研究目前狀態不可進行分析",
                    details={
                        "status": study.status,
                        "allowed": sorted(_ANALYZABLE_STATUSES),
                    },
                )

            completeness = MsaObservationService.completeness(plan.id)
            if not completeness["complete"]:
                raise MsaValidationError(
                    "MSA_DATA_INCOMPLETE",
                    "盲測矩陣尚有缺漏，不可產生正式結果",
                    details={
                        "expected": completeness["expected"],
                        "recorded": completeness["recorded"],
                        "missing": completeness["missing"][:20],
                    },
                )

            descriptor = MsaMethodRegistry.get(plan.method_code)
            observations = MsaAnalysisService._effective_observations(plan)
            analysis_input = {
                "study": MsaAnalysisService._study_snapshot(study),
                "plan": MsaAnalysisService._plan_snapshot(plan),
                "effective_observations": observations,
                "method": descriptor.as_dict(),
                "criteria": plan.criteria_snapshot,
            }
            data_hash = canonical_hash(analysis_input)

            context = MsaAnalysisService._context(study, plan, descriptor)
            engine_input = MsaAnalysisService._engine_input(
                descriptor.code, plan, observations, context,
            )
            output = descriptor.engine(engine_input, context)

            try:
                require_finite_tree(output.statistics)
                require_finite_tree(output.chart_data)
            except MsaNumericError as error:
                raise MsaValidationError(
                    "MSA_NUMERIC_FAILURE",
                    "統計結果包含非有限值，拒絕保存正式結果",
                    details={"path": error.path},
                ) from error

            conclusion, blockers = evaluate(
                descriptor.code, output.statistics, plan.criteria_snapshot,
            )

            result = MsaResultVersion(
                study_id=study.id,
                plan_version_id=plan.id,
                result_version_no=(
                    MsaAnalysisService._next_result_no(study.id)
                ),
                method_code=descriptor.code,
                method_version=descriptor.version,
                code_version=CODE_VERSION,
                data_hash=data_hash,
                raw_data_summary=analysis_input,
                applicability_result=output.applicability,
                statistics=output.statistics,
                chart_data=output.chart_data,
                criteria_snapshot=plan.criteria_snapshot,
                conclusion=conclusion,
                warnings=list(output.warnings),
                blockers=blockers,
                status="analyzed",
                created_by_id=actor_id,
            )
            db.session.add(result)
            db.session.flush()

            old_status = study.status
            study.status = "analyzed"
            study.current_result_version_id = result.id
            study.updated_by_id = actor_id
            study.updated_at = datetime.now(timezone.utc)

            db.session.add(MsaWorkflowDecision(
                study_id=study.id,
                result_version_id=result.id,
                action="analyze",
                from_status=old_status,
                to_status="analyzed",
                reason="依受控方法與凍結準則產生結果版本",
                actor_id=actor_id,
                separation_check={"passed": True, "checked_actor_id": actor_id},
                extra_data={
                    "method_code": descriptor.code,
                    "data_hash": data_hash,
                    "system_disposition": conclusion["system_disposition"],
                },
            ))
            log_audit(
                actor_id,
                "analyze",
                "msa_result",
                result.id,
                new_val={
                    "study_id": study.id,
                    "plan_version_id": plan.id,
                    "method_code": descriptor.code,
                    "data_hash": data_hash,
                    "system_disposition": conclusion["system_disposition"],
                },
            )
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise

    # ------------------------------------------------------------------
    # 快照與輸入
    # ------------------------------------------------------------------

    @staticmethod
    def _study_snapshot(study: MsaStudy) -> dict:
        return {
            "id": study.id,
            "study_no": study.study_no,
            "study_type": study.study_type,
            "measurement_purpose": study.measurement_purpose,
            "characteristic": study.characteristic,
            "unit": study.unit,
            "lsl": _text(study.lsl),
            "usl": _text(study.usl),
            "process_sigma": _text(study.process_sigma),
        }

    @staticmethod
    def _plan_snapshot(plan: MsaPlanVersion) -> dict:
        return {
            "id": plan.id,
            "plan_version_no": plan.plan_version_no,
            "method_code": plan.method_code,
            "method_version": plan.method_version,
            "design_type": plan.design_type,
            "part_count": plan.part_count,
            "appraiser_count": plan.appraiser_count,
            "trial_count": plan.trial_count,
            "random_seed": plan.random_seed,
            "plan_hash": plan.plan_hash,
            "frozen_at": (
                plan.frozen_at.isoformat() if plan.frozen_at else None
            ),
            "equipment_snapshot": plan.equipment_snapshot,
            "category_set": plan.category_set,
            "parts": [
                {
                    "part_no": part.part_no,
                    "blind_code": part.blind_code,
                    "part_identifier": part.part_identifier,
                    "reference_value": _text(part.reference_value),
                    "reference_uncertainty": _text(part.reference_uncertainty),
                    "reference_category": part.reference_category,
                }
                for part in sorted(plan.parts, key=lambda row: row.part_no)
            ],
            "appraisers": [
                {
                    "appraiser_no": row.appraiser_no,
                    "blind_code": row.blind_code,
                    "name": row.name,
                }
                for row in sorted(
                    plan.appraisers, key=lambda row: row.appraiser_no
                )
            ],
        }

    @staticmethod
    def _effective_observations(plan: MsaPlanVersion) -> list[dict]:
        """依實際輸入順序序列化目前有效的觀測。"""
        part_codes = {part.id: part.blind_code for part in plan.parts}
        appraiser_codes = {
            row.id: row.blind_code for row in plan.appraisers
        }
        rows = (
            MsaObservation.query
            .filter_by(plan_version_id=plan.id, is_effective=True)
            .order_by(MsaObservation.actual_entry_order.asc())
            .all()
        )
        return [
            {
                "part_blind_code": part_codes.get(row.part_id),
                "appraiser_blind_code": appraiser_codes.get(row.appraiser_id),
                "trial_no": row.trial_no,
                "requested_order": row.requested_order,
                "actual_entry_order": row.actual_entry_order,
                "numeric_value": _text(row.numeric_value),
                "attribute_value": row.attribute_value,
                "measured_at": (
                    row.measured_at.isoformat() if row.measured_at else None
                ),
                "source": row.source,
                "entered_by_id": row.entered_by_id,
            }
            for row in rows
        ]

    @staticmethod
    def _context(study, plan, descriptor) -> MsaMethodContext:
        tolerance = None
        if study.lsl is not None and study.usl is not None:
            tolerance = float(study.usl - study.lsl)
        return MsaMethodContext(
            method_code=descriptor.code,
            method_version=descriptor.version,
            alpha=float(
                (plan.criteria_snapshot or {}).get("thresholds", {}).get(
                    "alpha", descriptor.alpha
                )
            ),
            study_variation_multiplier=descriptor.study_variation_multiplier,
            tolerance=tolerance,
            process_sigma=(
                float(study.process_sigma)
                if study.process_sigma is not None else None
            ),
            criteria=dict(plan.criteria_snapshot or {}),
        )

    @staticmethod
    def _engine_input(method_code, plan, observations, context):
        """把序列化觀測轉成各引擎需要的輸入形狀。"""
        if method_code in {
            "MSA4_GRR_RANGE_1_0", "MSA4_GRR_XBAR_R_1_0", "MSA4_GRR_ANOVA_1_0",
        }:
            return [
                {
                    "part": row["part_blind_code"],
                    "appraiser": row["appraiser_blind_code"],
                    "trial": row["trial_no"],
                    "value": _number(row["numeric_value"]),
                }
                for row in observations
            ]

        parts_by_code = {
            part.blind_code: part for part in plan.parts
        }

        if method_code == "MSA4_ATTRIBUTE_1_0":
            return [
                {
                    "sample": row["part_blind_code"],
                    "appraiser": row["appraiser_blind_code"],
                    "trial": row["trial_no"],
                    "value": row["attribute_value"],
                    "reference": (
                        parts_by_code[row["part_blind_code"]].reference_category
                    ),
                }
                for row in observations
            ]

        if method_code == "MSA4_BIAS_1_0":
            part = sorted(plan.parts, key=lambda row: row.part_no)[0]
            return {
                "reference_value": (
                    float(part.reference_value)
                    if part.reference_value is not None else None
                ),
                "readings": [
                    _number(row["numeric_value"]) for row in observations
                ],
            }

        if method_code == "MSA4_LINEARITY_1_0":
            grouped = {}
            for row in observations:
                part = parts_by_code[row["part_blind_code"]]
                grouped.setdefault(part.part_no, {
                    "reference_value": (
                        float(part.reference_value)
                        if part.reference_value is not None else None
                    ),
                    "readings": [],
                })["readings"].append(_number(row["numeric_value"]))
            return [grouped[key] for key in sorted(grouped)]

        if method_code == "MSA4_STABILITY_1_0":
            grouped = {}
            for row in observations:
                key = row["measured_at"] or row["part_blind_code"]
                grouped.setdefault(key, []).append(
                    _number(row["numeric_value"])
                )
            return [
                {"measured_on": key, "readings": grouped[key]}
                for key in sorted(grouped)
            ]

        if method_code == "MSA4_NONREPEATABLE_1_0":
            design_type = (context.criteria or {}).get("design_type")
            if design_type in {"homogeneous_lot", "multiple_stations"}:
                group_key = (
                    "lot" if design_type == "homogeneous_lot" else "station"
                )
                return [
                    {
                        group_key: row["part_blind_code"],
                        "value": _number(row["numeric_value"]),
                    }
                    for row in observations
                ]
            return [
                {
                    "unit": row["part_blind_code"],
                    "position": row["trial_no"],
                    "value": _number(row["numeric_value"]),
                }
                for row in observations
            ]

        raise MsaValidationError(
            "MSA_METHOD_NOT_REGISTERED",
            "沒有對應的引擎輸入轉換",
            details={"method_code": method_code},
        )

    @staticmethod
    def _next_result_no(study_id: int) -> int:
        current = db.session.execute(
            db.select(db.func.max(MsaResultVersion.result_version_no))
            .where(MsaResultVersion.study_id == study_id)
        ).scalar_one_or_none()
        return (current or 0) + 1


def _text(value):
    return str(value) if value is not None else None


def _number(value):
    if value is None:
        return None
    return float(Decimal(str(value)))
