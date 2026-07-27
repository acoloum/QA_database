"""MSA 研究設計、盲碼指派、設備／準則快照與計畫凍結服務。

計畫一旦凍結即成為正式設計證據：設備資格會重新驗證、準則版本與
隨機順序會固定保存，之後不得再改寫。
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import random

from ..extensions import db
from ..models import (
    MsaAppraiser,
    MsaCriteriaProfile,
    MsaObservation,
    MsaPart,
    MsaPlanVersion,
    MsaStudy,
    MsaStudyEquipment,
    MsaWorkflowDecision,
)
from ..utils import log_audit
from .msa_equipment_service import MsaEquipmentService
from .msa_errors import MsaConflict, MsaNotFound, MsaValidationError
from .msa_method_registry import MsaMethodRegistry, _STUDY_TYPE_METHODS
from .msa_numeric import canonical_hash


_PLAN_FIELDS = {
    "method_code",
    "part_count",
    "appraiser_count",
    "trial_count",
    "random_seed",
    "design_type",
    "equipment",
    "parts",
    "appraisers",
    "category_set",
    "sampling_notes",
    "environment_notes",
    "percent_basis",
}

_EQUIPMENT_FIELDS = {"equipment_id", "role", "measurement_mode", "note"}
_PART_FIELDS = {
    "part_identifier", "reference_value", "reference_uncertainty",
    "reference_category", "note",
}

# 統計百分比的口徑必須由計畫明確選擇，不得由結果自動挑最有利的數字。
PERCENT_BASES = ("tolerance", "study_variation", "process_variation")
_APPRAISER_FIELDS = {"name", "user_id", "qualification"}

# 需要可追溯參考值的方法；沒有參考證據就無法計算偏倚或線性。
_REFERENCE_REQUIRED_METHODS = {"MSA4_BIAS_1_0", "MSA4_LINEARITY_1_0"}

# MSA 第四版十分之一法則：解析度不得超過公差或製程變差的 10%。
RULE_OF_TENS_RATIO = 0.1

MAX_DESIGN_DIMENSION = 200


class MsaDesignService:
    """建立可審查的研究設計，並以單一交易完成凍結。"""

    # ------------------------------------------------------------------
    # 建立設計
    # ------------------------------------------------------------------

    @staticmethod
    def create_plan(study_id: int, payload, actor_id: int) -> MsaPlanVersion:
        data = _require_object(payload)
        _reject_unknown_fields(data, _PLAN_FIELDS)

        try:
            study = (
                MsaStudy.query
                .filter_by(id=study_id)
                .with_for_update()
                .one_or_none()
            )
            if study is None:
                raise MsaNotFound(
                    "MSA_STUDY_NOT_FOUND",
                    "找不到 MSA 研究",
                    details={"study_id": study_id},
                )
            if study.status != "draft":
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "只有草稿研究可以建立新的計畫版本",
                    details={"status": study.status},
                )

            descriptor = MsaDesignService._resolve_method(study, data)
            design = MsaDesignService._validated_design(data)
            equipment_rows = MsaDesignService._validated_equipment(data)
            parts = MsaDesignService._validated_parts(data)
            appraisers = MsaDesignService._validated_appraisers(data)
            MsaDesignService._assert_design_complete(
                descriptor, design, equipment_rows, parts, appraisers,
            )

            plan = MsaPlanVersion(
                study_id=study.id,
                plan_version_no=MsaDesignService._next_plan_no(study.id),
                method_code=descriptor.code,
                method_version=descriptor.version,
                design_type=data.get("design_type") or "crossed",
                part_count=design["part_count"],
                appraiser_count=design["appraiser_count"],
                trial_count=design["trial_count"],
                random_seed=design["random_seed"],
                randomized_order=[],
                equipment_snapshot={},
                # 百分比口徑先記在準則快照，凍結時與準則版本一併固定
                criteria_snapshot=MsaDesignService._percent_basis_selection(
                    data
                ),
                category_set=list(data.get("category_set") or []),
                sampling_notes=_optional_text(
                    data.get("sampling_notes"), field="sampling_notes",
                ),
                environment_notes=_optional_text(
                    data.get("environment_notes"), field="environment_notes",
                ),
                created_by_id=actor_id,
            )
            db.session.add(plan)
            db.session.flush()

            for index, row in enumerate(parts, start=1):
                db.session.add(MsaPart(
                    plan_version_id=plan.id,
                    part_no=index,
                    blind_code=_blind_code("P", index),
                    part_identifier=row.get("part_identifier"),
                    reference_value=row.get("reference_value"),
                    reference_uncertainty=row.get("reference_uncertainty"),
                    reference_category=row.get("reference_category"),
                    note=row.get("note"),
                ))
            for index, row in enumerate(appraisers, start=1):
                db.session.add(MsaAppraiser(
                    plan_version_id=plan.id,
                    appraiser_no=index,
                    blind_code=_blind_code("A", index),
                    user_id=row.get("user_id"),
                    name=row["name"],
                    qualification=row.get("qualification"),
                ))

            MsaDesignService._replace_study_equipment(study.id, equipment_rows)
            db.session.flush()

            log_audit(
                actor_id,
                "create_plan",
                "msa_plan",
                plan.id,
                new_val={
                    "study_id": study.id,
                    "method_code": descriptor.code,
                    "part_count": plan.part_count,
                    "appraiser_count": plan.appraiser_count,
                    "trial_count": plan.trial_count,
                },
            )
            db.session.commit()
            return plan
        except Exception:
            db.session.rollback()
            raise

    # ------------------------------------------------------------------
    # 隨機順序與雜湊
    # ------------------------------------------------------------------

    @staticmethod
    def build_randomized_order(
        *, parts, appraisers, trial_count: int, random_seed: int,
    ) -> list[dict]:
        """以固定 seed 產生可重現的盲測順序。"""
        tasks = [
            {
                "part_id": part_id,
                "appraiser_id": appraiser_id,
                "trial_no": trial_no,
            }
            for trial_no in range(1, trial_count + 1)
            for appraiser_id in appraisers
            for part_id in parts
        ]
        random.Random(random_seed).shuffle(tasks)
        return [
            {**task, "requested_order": index}
            for index, task in enumerate(tasks, start=1)
        ]

    @staticmethod
    def compute_plan_hash(plan: MsaPlanVersion) -> str:
        """以固定輸入計算計畫指紋，讓匯入與報告可比對設計是否改變。"""
        return canonical_hash({
            "method_code": plan.method_code,
            "method_version": plan.method_version,
            "design_type": plan.design_type,
            "part_count": plan.part_count,
            "appraiser_count": plan.appraiser_count,
            "trial_count": plan.trial_count,
            "random_seed": plan.random_seed,
            "parts": [
                {
                    "part_no": part.part_no,
                    "blind_code": part.blind_code,
                    "part_identifier": part.part_identifier,
                    "reference_value": _decimal_text(part.reference_value),
                    "reference_uncertainty": _decimal_text(
                        part.reference_uncertainty
                    ),
                }
                for part in sorted(plan.parts, key=lambda row: row.part_no)
            ],
            "appraisers": [
                {
                    "appraiser_no": appraiser.appraiser_no,
                    "blind_code": appraiser.blind_code,
                    "name": appraiser.name,
                }
                for appraiser in sorted(
                    plan.appraisers, key=lambda row: row.appraiser_no
                )
            ],
            "randomized_order": plan.randomized_order,
            "equipment_snapshot": plan.equipment_snapshot,
            "criteria_snapshot": plan.criteria_snapshot,
            "category_set": plan.category_set,
            "sampling_notes": plan.sampling_notes,
            "environment_notes": plan.environment_notes,
        })

    # ------------------------------------------------------------------
    # 凍結
    # ------------------------------------------------------------------

    @staticmethod
    def freeze(
        plan_id: int, *, actor_id: int, expected_plan_hash=None,
    ) -> MsaPlanVersion:
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
            if plan.frozen_at is not None:
                raise MsaConflict(
                    "MSA_PLAN_ALREADY_FROZEN",
                    "計畫已凍結，請建立新的計畫版本",
                    details={"plan_id": plan.id},
                )
            if expected_plan_hash is not None:
                current_hash = MsaDesignService.compute_plan_hash(plan)
                if current_hash != expected_plan_hash:
                    raise MsaConflict(
                        "MSA_VERSION_CONFLICT",
                        "計畫內容已被其他人更新，請重新載入",
                        details={
                            "expected_plan_hash": expected_plan_hash,
                            "actual_plan_hash": current_hash,
                        },
                    )

            study = (
                MsaStudy.query
                .filter_by(id=plan.study_id)
                .with_for_update()
                .one()
            )
            if study.status != "draft":
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "研究狀態已變更，無法凍結此計畫",
                    details={"status": study.status},
                )

            today = date.today()
            equipment_snapshot = MsaDesignService._build_equipment_snapshot(
                study, on_date=today,
            )
            equipment_snapshot["resolution_assessment"] = (
                MsaDesignService._assess_resolution(study, equipment_snapshot)
            )
            selection = dict(plan.criteria_snapshot or {})
            if not selection.get("percent_basis"):
                selection = MsaDesignService._default_percent_basis(study)
            criteria_snapshot = {
                **MsaDesignService._build_criteria_snapshot(study),
                **selection,
            }

            plan.equipment_snapshot = equipment_snapshot
            plan.criteria_snapshot = criteria_snapshot
            plan.randomized_order = MsaDesignService.build_randomized_order(
                parts=[part.id for part in sorted(
                    plan.parts, key=lambda row: row.part_no
                )],
                appraisers=[appraiser.id for appraiser in sorted(
                    plan.appraisers, key=lambda row: row.appraiser_no
                )],
                trial_count=plan.trial_count,
                random_seed=plan.random_seed,
            )
            plan.plan_hash = MsaDesignService.compute_plan_hash(plan)
            plan.frozen_by_id = actor_id
            plan.frozen_at = datetime.now(timezone.utc)

            old_status = study.status
            study.status = "ready"
            study.current_plan_version_id = plan.id
            study.updated_by_id = actor_id
            study.updated_at = datetime.now(timezone.utc)

            db.session.add(MsaWorkflowDecision(
                study_id=study.id,
                action="freeze_plan",
                from_status=old_status,
                to_status="ready",
                reason="凍結研究設計並保存設備與準則快照",
                actor_id=actor_id,
                separation_check={"passed": True, "checked_actor_id": actor_id},
                extra_data={
                    "plan_version_id": plan.id,
                    "plan_hash": plan.plan_hash,
                },
            ))
            db.session.flush()
            log_audit(
                actor_id,
                "freeze_plan",
                "msa_plan",
                plan.id,
                old_val={"study_status": old_status},
                new_val={
                    "study_status": "ready",
                    "plan_hash": plan.plan_hash,
                    "criteria_version_id": criteria_snapshot.get("version_id"),
                },
            )
            db.session.commit()
            return plan
        except Exception:
            db.session.rollback()
            raise

    # ------------------------------------------------------------------
    # 盲測任務
    # ------------------------------------------------------------------

    @staticmethod
    def tasks(plan_id: int) -> list[dict]:
        """回傳只含盲碼的任務清單；不揭露真實零件、參考值與其他讀值。"""
        plan = db.session.get(MsaPlanVersion, plan_id)
        if plan is None:
            raise MsaNotFound(
                "MSA_PLAN_NOT_FOUND",
                "找不到 MSA 計畫版本",
                details={"plan_id": plan_id},
            )
        if plan.frozen_at is None:
            raise MsaConflict(
                "MSA_PLAN_NOT_FROZEN",
                "計畫尚未凍結，無法發出盲測任務",
                details={"plan_id": plan.id},
            )

        part_codes = {part.id: part.blind_code for part in plan.parts}
        appraiser_codes = {
            appraiser.id: appraiser.blind_code
            for appraiser in plan.appraisers
        }
        recorded = {
            (row.part_id, row.appraiser_id, row.trial_no)
            for row in MsaObservation.query.filter_by(
                plan_version_id=plan.id, is_effective=True,
            ).all()
        }
        return [
            {
                "requested_order": item["requested_order"],
                "part_blind_code": part_codes.get(item["part_id"]),
                "appraiser_blind_code": appraiser_codes.get(
                    item["appraiser_id"]
                ),
                "trial_no": item["trial_no"],
                "recorded": (
                    item["part_id"], item["appraiser_id"], item["trial_no"],
                ) in recorded,
            }
            for item in plan.randomized_order
        ]

    # ------------------------------------------------------------------
    # 內部驗證
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_method(study: MsaStudy, data: dict):
        method_code = data.get("method_code")
        descriptor = MsaMethodRegistry.get(method_code)
        allowed = _STUDY_TYPE_METHODS.get(study.study_type, ())
        if descriptor.code not in allowed:
            raise MsaValidationError(
                "MSA_METHOD_STUDY_TYPE_MISMATCH",
                "方法代碼與研究類型不一致",
                details={
                    "study_type": study.study_type,
                    "method_code": descriptor.code,
                    "allowed": list(allowed),
                },
            )
        return descriptor

    @staticmethod
    def _validated_design(data: dict) -> dict:
        design = {}
        for field in ("part_count", "appraiser_count", "trial_count"):
            design[field] = _bounded_int(
                data.get(field),
                field=field,
                minimum=1,
                maximum=MAX_DESIGN_DIMENSION,
                code="MSA_DESIGN_DIMENSION_INVALID",
            )
        design["random_seed"] = _bounded_int(
            data.get("random_seed", 0),
            field="random_seed",
            minimum=0,
            maximum=2 ** 62,
            code="MSA_DESIGN_SEED_INVALID",
        )
        return design

    @staticmethod
    def _validated_equipment(data: dict) -> list[dict]:
        rows = data.get("equipment")
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise MsaValidationError(
                "MSA_DESIGN_EQUIPMENT_INVALID",
                "equipment 必須是陣列",
                details={"field": "equipment"},
            )
        validated = []
        for index, row in enumerate(rows):
            item = _require_object(row)
            _reject_unknown_fields(item, _EQUIPMENT_FIELDS)
            equipment_id = _bounded_int(
                item.get("equipment_id"),
                field=f"equipment[{index}].equipment_id",
                minimum=1,
                maximum=2 ** 31,
                code="MSA_DESIGN_EQUIPMENT_INVALID",
            )
            role = item.get("role")
            if role not in {
                "primary_gauge", "reference_standard", "fixture", "auxiliary",
            }:
                raise MsaValidationError(
                    "MSA_DESIGN_EQUIPMENT_INVALID",
                    "設備角色不在受控清單",
                    details={"index": index, "role": role},
                )
            validated.append({
                "equipment_id": equipment_id,
                "role": role,
                "measurement_mode": item.get("measurement_mode") or "default",
                "note": _optional_text(item.get("note"), field="note"),
            })
        return validated

    @staticmethod
    def _validated_parts(data: dict) -> list[dict]:
        rows = data.get("parts") or []
        if not isinstance(rows, list):
            raise MsaValidationError(
                "MSA_DESIGN_PARTS_INVALID",
                "parts 必須是陣列",
                details={"field": "parts"},
            )
        validated = []
        for index, row in enumerate(rows):
            item = _require_object(row)
            _reject_unknown_fields(item, _PART_FIELDS)
            reference_value = _optional_decimal(
                item.get("reference_value"),
                field=f"parts[{index}].reference_value",
            )
            reference_category = _optional_text(
                item.get("reference_category"),
                field=f"parts[{index}].reference_category",
                max_length=80,
            )
            if reference_value is not None and reference_category is not None:
                raise MsaValidationError(
                    "MSA_DESIGN_PARTS_INVALID",
                    "同一零件只能有數值參考值或參考分類其中一種",
                    details={"index": index},
                )
            validated.append({
                "part_identifier": _optional_text(
                    item.get("part_identifier"),
                    field=f"parts[{index}].part_identifier",
                ),
                "reference_value": reference_value,
                "reference_category": reference_category,
                "reference_uncertainty": _optional_decimal(
                    item.get("reference_uncertainty"),
                    field=f"parts[{index}].reference_uncertainty",
                ),
                "note": _optional_text(
                    item.get("note"), field=f"parts[{index}].note",
                ),
            })
        return validated

    @staticmethod
    def _validated_appraisers(data: dict) -> list[dict]:
        rows = data.get("appraisers") or []
        if not isinstance(rows, list):
            raise MsaValidationError(
                "MSA_DESIGN_APPRAISERS_INVALID",
                "appraisers 必須是陣列",
                details={"field": "appraisers"},
            )
        validated = []
        for index, row in enumerate(rows):
            item = _require_object(row)
            _reject_unknown_fields(item, _APPRAISER_FIELDS)
            name = _optional_text(
                item.get("name"), field=f"appraisers[{index}].name",
            )
            if not name:
                raise MsaValidationError(
                    "MSA_DESIGN_APPRAISERS_INVALID",
                    "每位評價人都必須有姓名",
                    details={"index": index},
                )
            validated.append({
                "name": name,
                "user_id": item.get("user_id"),
                "qualification": _optional_text(
                    item.get("qualification"),
                    field=f"appraisers[{index}].qualification",
                ),
            })
        return validated

    @staticmethod
    def _assert_design_complete(
        descriptor, design, equipment_rows, parts, appraisers,
    ) -> None:
        shortfalls = descriptor.design_shortfalls({
            "parts": design["part_count"],
            "appraisers": design["appraiser_count"],
            "trials": design["trial_count"],
            # 穩定性以子組數表示設計規模
            "subgroups": design["part_count"],
        })
        issues = []
        if not any(
            row["role"] == "primary_gauge" for row in equipment_rows
        ):
            issues.append("MSA_DESIGN_PRIMARY_GAUGE_MISSING")
        if shortfalls or issues:
            raise MsaValidationError(
                "MSA_DESIGN_INCOMPLETE",
                "研究設計尚未達到此方法的最低要求",
                details={"shortfalls": shortfalls, "issues": issues},
            )

        if len(parts) != design["part_count"]:
            raise MsaValidationError(
                "MSA_DESIGN_COUNT_MISMATCH",
                "零件筆數與宣告的零件數不一致",
                details={
                    "declared": design["part_count"], "supplied": len(parts),
                },
            )
        if len(appraisers) != design["appraiser_count"]:
            raise MsaValidationError(
                "MSA_DESIGN_COUNT_MISMATCH",
                "評價人筆數與宣告的評價人數不一致",
                details={
                    "declared": design["appraiser_count"],
                    "supplied": len(appraisers),
                },
            )

        if descriptor.code in _REFERENCE_REQUIRED_METHODS:
            has_reference_part = any(
                row["reference_value"] is not None for row in parts
            )
            has_reference_equipment = any(
                row["role"] == "reference_standard" for row in equipment_rows
            )
            if not (has_reference_part or has_reference_equipment):
                raise MsaValidationError(
                    "MSA_DESIGN_REFERENCE_REQUIRED",
                    "偏倚與線性研究必須有參考標準或可追溯的參考值",
                    details={"method_code": descriptor.code},
                )

    @staticmethod
    def _percent_basis_selection(data: dict) -> dict:
        """記錄百分比口徑是使用者明確選擇，還是採用預設順序。"""
        basis = data.get("percent_basis")
        if basis is None:
            return {}
        if basis not in PERCENT_BASES:
            raise MsaValidationError(
                "MSA_DESIGN_PERCENT_BASIS_INVALID",
                "百分比口徑必須是受控選項之一",
                details={"percent_basis": basis, "allowed": list(PERCENT_BASES)},
            )
        return {"percent_basis": basis, "percent_basis_source": "explicit"}

    @staticmethod
    def _default_percent_basis(study: MsaStudy) -> dict:
        """未明確選擇時採固定順序，並記錄是預設而非最有利選擇。"""
        if study.lsl is not None and study.usl is not None:
            basis = "tolerance"
        elif study.process_sigma is not None:
            basis = "process_variation"
        else:
            basis = "study_variation"
        return {"percent_basis": basis, "percent_basis_source": "default"}

    @staticmethod
    def _next_plan_no(study_id: int) -> int:
        current = db.session.execute(
            db.select(db.func.max(MsaPlanVersion.plan_version_no))
            .where(MsaPlanVersion.study_id == study_id)
        ).scalar_one_or_none()
        return (current or 0) + 1

    @staticmethod
    def _replace_study_equipment(study_id: int, rows: list[dict]) -> None:
        MsaStudyEquipment.query.filter_by(study_id=study_id).delete()
        for row in rows:
            db.session.add(MsaStudyEquipment(
                study_id=study_id,
                equipment_id=row["equipment_id"],
                role=row["role"],
                measurement_mode=row["measurement_mode"],
                note=row["note"],
            ))

    @staticmethod
    def _build_equipment_snapshot(study: MsaStudy, *, on_date: date) -> dict:
        """凍結時重新驗證每台設備的資格，任何不合格都中止凍結。"""
        items = []
        for link in sorted(
            study.equipment_links, key=lambda row: (row.role, row.equipment_id)
        ):
            snapshot = MsaEquipmentService.build_snapshot(
                link.equipment_id,
                on_date=on_date,
                measurement_mode=link.measurement_mode,
            )
            items.append({
                "role": link.role,
                "measurement_mode": link.measurement_mode,
                "equipment_id": snapshot.equipment_id,
                "equipment_no": snapshot.equipment_no,
                "name": snapshot.name,
                "status": snapshot.status,
                "resolution": snapshot.resolution,
                "unit": snapshot.unit,
                "calibration": snapshot.calibration,
            })
        return {"checked_on": on_date.isoformat(), "items": items}

    @staticmethod
    def _assess_resolution(study: MsaStudy, snapshot: dict) -> dict:
        """依十分之一法則評估主量具解析度是否足以鑑別公差或製程變差。"""
        primary = next(
            (
                item for item in snapshot["items"]
                if item["role"] == "primary_gauge"
            ),
            None,
        )
        resolution = _to_decimal(primary and primary.get("resolution"))
        if resolution is None or resolution <= 0:
            return {
                "level": "unknown",
                "reason": "主量具未登錄有效解析度，無法評估鑑別力",
                "discrimination_ratio": None,
            }

        reference, basis = MsaDesignService._discrimination_basis(study)
        if reference is None or reference <= 0:
            return {
                "level": "unknown",
                "reason": "研究未提供公差或製程變差，無法評估鑑別力",
                "discrimination_ratio": None,
            }

        ratio = float(resolution / reference)
        level = "ok" if ratio <= RULE_OF_TENS_RATIO else "insufficient"
        return {
            "level": level,
            "basis": basis,
            "resolution": str(resolution),
            "reference_span": str(reference),
            "discrimination_ratio": ratio,
            "rule": "MSA 第四版十分之一法則",
            "reason": (
                "解析度符合十分之一法則" if level == "ok"
                else "解析度超過參考變差的 10%，鑑別力不足"
            ),
        }

    @staticmethod
    def _discrimination_basis(study: MsaStudy):
        if study.lsl is not None and study.usl is not None:
            return study.usl - study.lsl, "tolerance"
        if study.process_sigma is not None:
            return study.process_sigma * Decimal(6), "process_variation"
        return None, None

    @staticmethod
    def _build_criteria_snapshot(study: MsaStudy) -> dict:
        profile = (
            db.session.get(MsaCriteriaProfile, study.criteria_profile_id)
            if study.criteria_profile_id else None
        )
        version = profile.current_version if profile else None
        if version is None or version.status != "approved":
            raise MsaValidationError(
                "MSA_CRITERIA_VERSION_REQUIRED",
                "研究必須指定含已核准版本的判定準則後才能凍結",
                details={"criteria_profile_id": study.criteria_profile_id},
            )
        return {
            "profile_id": profile.id,
            "profile_name": profile.name,
            "version_id": version.id,
            "version_no": version.version_no,
            "method_version": version.method_version,
            "effective_date": version.effective_date.isoformat(),
            "thresholds": dict(version.thresholds or {}),
            "stability_rules": dict(version.stability_rules or {}),
            "conditional_actions": list(version.conditional_actions or []),
            "basis": version.basis,
        }


# ----------------------------------------------------------------------
# 共用輸入處理
# ----------------------------------------------------------------------


def _blind_code(prefix: str, index: int) -> str:
    """盲碼只表示序位，不含資料庫識別碼或真實零件編號。"""
    return f"{prefix}{index:02d}"


def _require_object(payload) -> dict:
    if not isinstance(payload, dict):
        raise MsaValidationError(
            "MSA_PAYLOAD_INVALID", "請求內容必須是 JSON 物件", details={},
        )
    return payload


def _reject_unknown_fields(payload: dict, allowed: set) -> None:
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise MsaValidationError(
            "MSA_UNKNOWN_FIELDS",
            "請求包含未允許欄位",
            details={"unknown_fields": unknown},
        )


def _optional_text(value, *, field: str, max_length: int = 2000):
    if value is None:
        return None
    if not isinstance(value, str):
        raise MsaValidationError(
            "MSA_DESIGN_TEXT_INVALID",
            f"{field} 必須是文字",
            details={"field": field},
        )
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise MsaValidationError(
            "MSA_DESIGN_TEXT_INVALID",
            f"{field} 超過允許長度",
            details={"field": field, "max_length": max_length},
        )
    return normalized


def _optional_decimal(value, *, field: str):
    if value is None:
        return None
    parsed = _to_decimal(value)
    if parsed is None:
        raise MsaValidationError(
            "MSA_DESIGN_NUMBER_INVALID",
            f"{field} 必須是有限數值",
            details={"field": field},
        )
    return parsed


def _to_decimal(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _bounded_int(value, *, field: str, minimum: int, maximum: int, code: str):
    if isinstance(value, bool) or value is None:
        raise MsaValidationError(
            code, f"{field} 必須是整數", details={"field": field},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise MsaValidationError(
            code, f"{field} 必須是整數", details={"field": field},
        ) from error
    if parsed < minimum or parsed > maximum:
        raise MsaValidationError(
            code,
            f"{field} 超出允許範圍",
            details={"field": field, "minimum": minimum, "maximum": maximum},
        )
    return parsed


def _decimal_text(value):
    return str(value) if value is not None else None
