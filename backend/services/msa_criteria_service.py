"""版本化 MSA 判定準則、核准指標與完整快照服務。"""

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import math

from sqlalchemy import func
from sqlalchemy.exc import DataError, IntegrityError

from ..extensions import db
from ..models import MsaCriteriaProfile, MsaCriteriaVersion
from ..utils import log_audit
from .msa_errors import (
    MsaConflict,
    MsaNotFound,
    MsaServiceError,
    MsaValidationError,
)


DEFAULT_THRESHOLDS = {
    "grr_accept_max": 10.0,
    "grr_conditional_max": 30.0,
    "ndc_min": 5,
    "alpha": 0.05,
    "kappa_min": 0.75,
    "effectiveness_min": 90.0,
    "false_accept_max": 5.0,
    "false_reject_max": 5.0,
}

DEFAULT_STABILITY_RULES = {
    "rule_set": "WECO",
    "enabled_rules": [1, 2, 3, 4],
}

DEFAULT_CONDITIONAL_ACTIONS = [
    "記錄條件接受理由",
    "依特性風險、用途及顧客要求建立改善或監控措施",
]

DEFAULT_BASIS = "AIAG MSA 第四版及經核准之組織判定準則"

_PROFILE_FIELDS = {
    "name",
    "customer_scope",
    "product_scope",
    "product_family_scope",
    "characteristic_scope",
    "characteristic_importance",
    "applicable_study_types",
}
_PROFILE_TEXT_LIMITS = {
    "name": 160,
    "customer_scope": 200,
    "product_scope": 200,
    "product_family_scope": 200,
    "characteristic_scope": 200,
    "characteristic_importance": 40,
}
_VERSION_FIELDS = {
    "method_version",
    "effective_date",
    "thresholds",
    "stability_rules",
    "conditional_actions",
    "basis",
}
_THRESHOLD_FIELDS = frozenset(DEFAULT_THRESHOLDS)
_STABILITY_FIELDS = {"rule_set", "enabled_rules"}
_LIST_QUERY_FIELDS = {"page", "page_size", "sort", "order"}
_SORT_FIELDS = {
    "id": MsaCriteriaProfile.id,
    "name": MsaCriteriaProfile.name,
}


class MsaCriteriaService:
    """維護不可變準則版本，並以 optimistic state 加雙 row lock 核准。"""

    @staticmethod
    def default_thresholds() -> dict:
        """回傳互不共享參照的第四版完整預設門檻。"""
        return deepcopy(DEFAULT_THRESHOLDS)

    @staticmethod
    def default_stability_rules() -> dict:
        """回傳互不共享參照的 WECO 預設規則。"""
        return deepcopy(DEFAULT_STABILITY_RULES)

    @staticmethod
    def create_profile(payload, actor_id: int) -> MsaCriteriaProfile:
        """建立適用範圍 profile，並在同一交易保存稽核紀錄。"""
        data = MsaCriteriaService._require_object(payload)
        MsaCriteriaService._reject_unknown_fields(data, _PROFILE_FIELDS)
        name = MsaCriteriaService._required_text(
            data,
            "name",
            max_length=_PROFILE_TEXT_LIMITS["name"],
            code="MSA_CRITERIA_PROFILE_INVALID",
        )
        scopes = {
            field: MsaCriteriaService._optional_text(
                data.get(field),
                field=field,
                max_length=limit,
                code="MSA_CRITERIA_PROFILE_INVALID",
            )
            for field, limit in _PROFILE_TEXT_LIMITS.items()
            if field != "name"
        }
        study_types = MsaCriteriaService._validate_study_types(
            data.get("applicable_study_types", [])
        )
        profile = MsaCriteriaProfile(
            name=name,
            applicable_study_types=study_types,
            **scopes,
        )
        try:
            db.session.add(profile)
            db.session.flush()
            log_audit(
                actor_id,
                "create_profile",
                "msa_criteria",
                profile.id,
                new_val=MsaCriteriaService.serialize_profile(
                    profile,
                    include_versions=False,
                ),
            )
            db.session.commit()
            return profile
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_CRITERIA_PROFILE_INVALID",
                "判定準則設定超過資料庫限制",
                details={},
            ) from error
        except IntegrityError as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_CRITERIA_PROFILE_CONFLICT",
                "判定準則設定與既有資料衝突",
                details={},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def create_version(
        profile_id: int,
        payload,
        actor_id: int,
    ) -> MsaCriteriaVersion:
        """鎖定 profile 後配置下一版號，建立完整 draft 快照。"""
        data = MsaCriteriaService._require_object(payload)
        MsaCriteriaService._reject_unknown_fields(data, _VERSION_FIELDS)
        criteria_snapshot = MsaCriteriaService._criteria_snapshot(data)
        method_version = MsaCriteriaService._optional_text(
            data.get("method_version", "MSA4-1.0"),
            field="method_version",
            max_length=80,
            code="MSA_CRITERIA_VERSION_INVALID",
        )
        if method_version is None:
            raise MsaValidationError(
                "MSA_CRITERIA_VERSION_INVALID",
                "method_version 不可為空白",
                details={"field": "method_version"},
            )
        effective_date = MsaCriteriaService._parse_iso_date(
            data.get("effective_date", date.today()),
            field="effective_date",
        )

        try:
            profile = MsaCriteriaService._lock_profile(profile_id)
            if profile is None:
                raise MsaNotFound(
                    "MSA_CRITERIA_PROFILE_NOT_FOUND",
                    "找不到判定準則設定",
                    details={"profile_id": profile_id},
                )
            latest_revision = db.session.execute(
                db.select(func.max(MsaCriteriaVersion.version_no)).where(
                    MsaCriteriaVersion.profile_id == profile.id
                )
            ).scalar_one()
            version = MsaCriteriaVersion(
                profile_id=profile.id,
                version_no=(latest_revision or 0) + 1,
                method_version=method_version,
                effective_date=effective_date,
                thresholds=criteria_snapshot["thresholds"],
                stability_rules=criteria_snapshot["stability_rules"],
                conditional_actions=criteria_snapshot["conditional_actions"],
                basis=criteria_snapshot["basis"],
                status="draft",
                created_by=actor_id,
            )
            db.session.add(version)
            db.session.flush()
            log_audit(
                actor_id,
                "create_version",
                "msa_criteria",
                version.id,
                new_val={
                    "profile_id": profile.id,
                    "version_id": version.id,
                    "version_no": version.version_no,
                    "status": "draft",
                    "criteria_snapshot": criteria_snapshot,
                },
            )
            db.session.commit()
            return version
        except MsaServiceError:
            db.session.rollback()
            raise
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_CRITERIA_VERSION_INVALID",
                "判定準則版本超過資料庫限制",
                details={},
            ) from error
        except IntegrityError as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_VERSION_CONFLICT",
                "判定準則版號已被其他人建立，請重新載入",
                details={"profile_id": profile_id},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def approve_version(
        version_id: int,
        actor_id: int,
        expected_status=None,
        *,
        payload=None,
    ) -> MsaCriteriaVersion:
        """以 version/profile 雙 row lock 原子核准完整準則快照。"""
        if payload is not None:
            approval_data = MsaCriteriaService._require_object(payload)
            MsaCriteriaService._reject_unknown_fields(
                approval_data,
                {"expected_status"},
            )
            expected_status = approval_data.get("expected_status")
        if expected_status != "draft":
            raise MsaValidationError(
                "MSA_EXPECTED_STATUS_INVALID",
                "expected_status 必須是 draft",
                details={"expected_status": expected_status},
            )

        try:
            preliminary = db.session.execute(
                db.select(
                    MsaCriteriaVersion.profile_id,
                    MsaCriteriaVersion.status,
                ).where(MsaCriteriaVersion.id == version_id)
            ).one_or_none()
            if preliminary is None:
                raise MsaNotFound(
                    "MSA_CRITERIA_VERSION_NOT_FOUND",
                    "找不到判定準則版本",
                    details={"version_id": version_id},
                )
            observed_current_version_id = db.session.execute(
                db.select(MsaCriteriaProfile.current_version_id).where(
                    MsaCriteriaProfile.id == preliminary.profile_id
                )
            ).scalar_one_or_none()

            version = MsaCriteriaService._lock_version(version_id)
            if version is None:
                raise MsaNotFound(
                    "MSA_CRITERIA_VERSION_NOT_FOUND",
                    "找不到判定準則版本",
                    details={"version_id": version_id},
                )
            profile = MsaCriteriaService._lock_profile(
                preliminary.profile_id
            )
            if profile is None:
                raise MsaConflict(
                    "MSA_CRITERIA_PROFILE_CONFLICT",
                    "判定準則版本所屬設定已不存在",
                    details={"profile_id": preliminary.profile_id},
                )
            if version.profile_id != profile.id:
                raise MsaConflict(
                    "MSA_CRITERIA_PROFILE_CONFLICT",
                    "鎖定的判定準則版本與設定不一致",
                    details={
                        "version_profile_id": version.profile_id,
                        "locked_profile_id": profile.id,
                    },
                )
            if version.status != expected_status or version.status != "draft":
                raise MsaConflict(
                    "MSA_VERSION_CONFLICT",
                    "判定準則版本已被其他人更新",
                    details={
                        "expected_status": expected_status,
                        "actual_status": version.status,
                    },
                )
            if profile.current_version_id != observed_current_version_id:
                raise MsaConflict(
                    "MSA_CRITERIA_PROFILE_CONFLICT",
                    "目前啟用版本已被其他人更新，請重新載入",
                    details={
                        "expected_current_version_id": (
                            observed_current_version_id
                        ),
                        "actual_current_version_id": profile.current_version_id,
                    },
                )

            criteria_snapshot = MsaCriteriaService._criteria_snapshot(
                {
                    "thresholds": version.thresholds,
                    "stability_rules": version.stability_rules,
                    "conditional_actions": version.conditional_actions,
                    "basis": version.basis,
                }
            )
            old_current_version_id = profile.current_version_id
            version.thresholds = criteria_snapshot["thresholds"]
            version.stability_rules = criteria_snapshot["stability_rules"]
            version.conditional_actions = criteria_snapshot[
                "conditional_actions"
            ]
            version.basis = criteria_snapshot["basis"]
            version.status = "approved"
            version.approved_by = actor_id
            version.approved_at = datetime.now(timezone.utc)
            profile.current_version_id = version.id
            db.session.flush()
            log_audit(
                actor_id,
                "approve_version",
                "msa_criteria",
                version.id,
                old_val={
                    "profile_id": profile.id,
                    "current_version_id": old_current_version_id,
                    "version_status": "draft",
                },
                new_val={
                    "profile_id": profile.id,
                    "version_id": version.id,
                    "current_version_id": version.id,
                    "version_status": "approved",
                    "approved_by": actor_id,
                    "criteria_snapshot": criteria_snapshot,
                },
            )
            db.session.commit()
            return version
        except MsaServiceError:
            db.session.rollback()
            raise
        except DataError as error:
            db.session.rollback()
            raise MsaValidationError(
                "MSA_CRITERIA_VERSION_INVALID",
                "判定準則版本超過資料庫限制",
                details={},
            ) from error
        except (IntegrityError, ValueError) as error:
            db.session.rollback()
            raise MsaConflict(
                "MSA_VERSION_CONFLICT",
                "判定準則版本已被其他人更新",
                details={"reason": str(error)},
            ) from error
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list(args) -> dict:
        """以有界分頁及白名單排序列出 profile 與歷史版本。"""
        values = args or {}
        unknown = set(values.keys()) - _LIST_QUERY_FIELDS
        if unknown:
            MsaCriteriaService._reject_unknown_fields(
                {field: values.get(field) for field in unknown},
                set(),
            )
        page = MsaCriteriaService._parse_bounded_int(
            values.get("page", 1),
            field="page",
            minimum=1,
            maximum=None,
            code="MSA_CRITERIA_PAGE_INVALID",
        )
        page_size = MsaCriteriaService._parse_bounded_int(
            values.get("page_size", 25),
            field="page_size",
            minimum=1,
            maximum=100,
            code="MSA_CRITERIA_PAGE_SIZE_INVALID",
        )
        sort_name = values.get("sort", "name")
        sort_column = _SORT_FIELDS.get(sort_name)
        if sort_column is None:
            raise MsaValidationError(
                "MSA_CRITERIA_SORT_INVALID",
                "不支援的判定準則排序欄位",
                details={"sort": sort_name, "allowed": sorted(_SORT_FIELDS)},
            )
        order = values.get("order", "asc")
        if order not in {"asc", "desc"}:
            raise MsaValidationError(
                "MSA_CRITERIA_SORT_ORDER_INVALID",
                "排序方向只允許 asc 或 desc",
                details={"order": order},
            )
        ordering = sort_column.asc() if order == "asc" else sort_column.desc()
        tie_breaker = (
            MsaCriteriaProfile.id.asc()
            if order == "asc"
            else MsaCriteriaProfile.id.desc()
        )
        query = MsaCriteriaProfile.query
        total = query.count()
        profiles = (
            query.order_by(ordering, tie_breaker)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                MsaCriteriaService.serialize_profile(profile)
                for profile in profiles
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def serialize_profile(
        profile: MsaCriteriaProfile,
        *,
        include_versions: bool = True,
    ) -> dict:
        """將 profile 轉為不共享 ORM JSON 參照的 API 快照。"""
        data = {
            "id": profile.id,
            "name": profile.name,
            "customer_scope": profile.customer_scope,
            "product_scope": profile.product_scope,
            "product_family_scope": profile.product_family_scope,
            "characteristic_scope": profile.characteristic_scope,
            "characteristic_importance": profile.characteristic_importance,
            "applicable_study_types": MsaCriteriaService._canonical_json(
                profile.applicable_study_types or [],
                field="applicable_study_types",
            ),
            "current_version_id": profile.current_version_id,
        }
        if include_versions:
            data["versions"] = [
                MsaCriteriaService.serialize_version(version)
                for version in sorted(
                    profile.versions,
                    key=lambda item: item.version_no,
                    reverse=True,
                )
            ]
        return data

    @staticmethod
    def serialize_version(version: MsaCriteriaVersion) -> dict:
        """將版本轉為 deterministic、禁止非有限數值的完整快照。"""
        return {
            "id": version.id,
            "profile_id": version.profile_id,
            "version_no": version.version_no,
            "method_version": version.method_version,
            "effective_date": (
                version.effective_date.isoformat()
                if version.effective_date
                else None
            ),
            "thresholds": MsaCriteriaService._canonical_json(
                version.thresholds,
                field="thresholds",
            ),
            "stability_rules": MsaCriteriaService._canonical_json(
                version.stability_rules,
                field="stability_rules",
            ),
            "conditional_actions": MsaCriteriaService._canonical_json(
                version.conditional_actions,
                field="conditional_actions",
            ),
            "basis": version.basis,
            "status": version.status,
            "is_current": bool(
                version.profile
                and version.profile.current_version_id == version.id
            ),
            "created_by": version.created_by,
            "created_at": (
                version.created_at.isoformat() if version.created_at else None
            ),
            "approved_by": version.approved_by,
            "approved_at": (
                version.approved_at.isoformat()
                if version.approved_at
                else None
            ),
        }

    @staticmethod
    def _lock_version(version_id: int) -> MsaCriteriaVersion | None:
        return (
            db.session.execute(
                db.select(MsaCriteriaVersion)
                .where(MsaCriteriaVersion.id == version_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            .scalar_one_or_none()
        )

    @staticmethod
    def _lock_profile(profile_id: int) -> MsaCriteriaProfile | None:
        return (
            db.session.execute(
                db.select(MsaCriteriaProfile)
                .where(MsaCriteriaProfile.id == profile_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            .scalar_one_or_none()
        )

    @staticmethod
    def _criteria_snapshot(payload: dict) -> dict:
        thresholds = MsaCriteriaService._validate_thresholds(
            payload.get("thresholds")
            if "thresholds" in payload
            else MsaCriteriaService.default_thresholds()
        )
        stability_rules = MsaCriteriaService._validate_stability_rules(
            payload.get("stability_rules")
            if "stability_rules" in payload
            else MsaCriteriaService.default_stability_rules()
        )
        conditional_actions = (
            MsaCriteriaService._validate_conditional_actions(
                payload.get("conditional_actions")
                if "conditional_actions" in payload
                else DEFAULT_CONDITIONAL_ACTIONS
            )
        )
        basis = MsaCriteriaService._optional_text(
            payload.get("basis", DEFAULT_BASIS),
            field="basis",
            max_length=10000,
            code="MSA_CRITERIA_BASIS_INVALID",
        )
        if basis is None:
            raise MsaValidationError(
                "MSA_CRITERIA_BASIS_INVALID",
                "basis 不可為空白",
                details={"field": "basis"},
            )
        return MsaCriteriaService._canonical_json(
            {
                "thresholds": thresholds,
                "stability_rules": stability_rules,
                "conditional_actions": conditional_actions,
                "basis": basis,
            },
            field="criteria_snapshot",
        )

    @staticmethod
    def _validate_thresholds(value) -> dict:
        if not isinstance(value, dict):
            raise MsaValidationError(
                "MSA_CRITERIA_THRESHOLDS_INVALID",
                "thresholds 必須是 JSON 物件",
                details={"field": "thresholds"},
            )
        unknown = set(value) - _THRESHOLD_FIELDS
        if unknown:
            MsaCriteriaService._reject_unknown_fields(value, _THRESHOLD_FIELDS)
        merged = MsaCriteriaService.default_thresholds()
        merged.update(value)
        numbers = {}
        for field in _THRESHOLD_FIELDS - {"ndc_min"}:
            numbers[field] = MsaCriteriaService._finite_number(
                merged.get(field),
                field=field,
            )
        ndc_min = merged.get("ndc_min")
        if (
            isinstance(ndc_min, bool)
            or not isinstance(ndc_min, int)
            or ndc_min < 2
        ):
            MsaCriteriaService._threshold_error(
                "ndc_min",
                "ndc_min 必須是大於或等於 2 的整數",
            )
        accept = numbers["grr_accept_max"]
        conditional = numbers["grr_conditional_max"]
        if accept < 0 or accept > 100:
            MsaCriteriaService._threshold_error(
                "grr_accept_max",
                "grr_accept_max 必須介於 0 到 100",
            )
        if conditional < 0 or conditional > 100:
            MsaCriteriaService._threshold_error(
                "grr_conditional_max",
                "grr_conditional_max 必須介於 0 到 100",
            )
        if accept >= conditional:
            accept_changed = accept != DEFAULT_THRESHOLDS["grr_accept_max"]
            conditional_changed = (
                conditional != DEFAULT_THRESHOLDS["grr_conditional_max"]
            )
            field = (
                "grr_conditional_max"
                if conditional_changed and not accept_changed
                else "grr_accept_max"
            )
            MsaCriteriaService._threshold_error(
                field,
                "門檻順序必須為 0 <= accept < conditional <= 100",
            )
        alpha = numbers["alpha"]
        if not 0 < alpha < 1:
            MsaCriteriaService._threshold_error(
                "alpha",
                "alpha 必須大於 0 且小於 1",
            )
        kappa = numbers["kappa_min"]
        if not 0 <= kappa <= 1:
            MsaCriteriaService._threshold_error(
                "kappa_min",
                "kappa_min 必須介於 0 到 1",
            )
        for field in (
            "effectiveness_min",
            "false_accept_max",
            "false_reject_max",
        ):
            if not 0 <= numbers[field] <= 100:
                MsaCriteriaService._threshold_error(
                    field,
                    f"{field} 必須介於 0 到 100",
                )
        return {
            "grr_accept_max": accept,
            "grr_conditional_max": conditional,
            "ndc_min": ndc_min,
            "alpha": alpha,
            "kappa_min": kappa,
            "effectiveness_min": numbers["effectiveness_min"],
            "false_accept_max": numbers["false_accept_max"],
            "false_reject_max": numbers["false_reject_max"],
        }

    @staticmethod
    def _validate_stability_rules(value) -> dict:
        if not isinstance(value, dict):
            raise MsaValidationError(
                "MSA_CRITERIA_STABILITY_RULES_INVALID",
                "stability_rules 必須是 JSON 物件",
                details={"field": "stability_rules"},
            )
        unknown = set(value) - _STABILITY_FIELDS
        if unknown:
            MsaCriteriaService._reject_unknown_fields(
                value,
                _STABILITY_FIELDS,
            )
        merged = MsaCriteriaService.default_stability_rules()
        merged.update(value)
        rule_set = merged.get("rule_set")
        rules = merged.get("enabled_rules")
        if rule_set != "WECO":
            raise MsaValidationError(
                "MSA_CRITERIA_STABILITY_RULES_INVALID",
                "rule_set 目前只允許 WECO",
                details={"field": "rule_set", "value": rule_set},
            )
        if (
            not isinstance(rules, list)
            or not rules
            or any(
                isinstance(rule, bool)
                or not isinstance(rule, int)
                or rule not in {1, 2, 3, 4}
                for rule in rules
            )
            or len(set(rules)) != len(rules)
        ):
            raise MsaValidationError(
                "MSA_CRITERIA_STABILITY_RULES_INVALID",
                "enabled_rules 必須是由 1 到 4 組成且不重複的非空陣列",
                details={"field": "enabled_rules"},
            )
        return {"rule_set": rule_set, "enabled_rules": list(rules)}

    @staticmethod
    def _validate_conditional_actions(value) -> list[str]:
        if (
            not isinstance(value, list)
            or not value
            or len(value) > 20
        ):
            raise MsaValidationError(
                "MSA_CRITERIA_CONDITIONAL_ACTIONS_INVALID",
                "conditional_actions 必須是 1 到 20 項的非空陣列",
                details={"field": "conditional_actions"},
            )
        actions = []
        for index, action in enumerate(value):
            if (
                not isinstance(action, str)
                or not action.strip()
                or len(action.strip()) > 1000
            ):
                raise MsaValidationError(
                    "MSA_CRITERIA_CONDITIONAL_ACTIONS_INVALID",
                    "conditional_actions 每一項必須是非空白文字",
                    details={
                        "field": "conditional_actions",
                        "index": index,
                    },
                )
            actions.append(action.strip())
        if len(set(actions)) != len(actions):
            raise MsaValidationError(
                "MSA_CRITERIA_CONDITIONAL_ACTIONS_INVALID",
                "conditional_actions 不可包含重複項目",
                details={"field": "conditional_actions"},
            )
        return actions

    @staticmethod
    def _validate_study_types(value) -> list[str]:
        if not isinstance(value, list):
            raise MsaValidationError(
                "MSA_CRITERIA_PROFILE_INVALID",
                "applicable_study_types 必須是陣列",
                details={"field": "applicable_study_types"},
            )
        normalized = []
        for index, study_type in enumerate(value):
            if (
                not isinstance(study_type, str)
                or not study_type.strip()
                or len(study_type.strip()) > 80
            ):
                raise MsaValidationError(
                    "MSA_CRITERIA_PROFILE_INVALID",
                    "研究類型必須是非空白文字",
                    details={
                        "field": "applicable_study_types",
                        "index": index,
                    },
                )
            normalized.append(study_type.strip())
        if len(set(normalized)) != len(normalized):
            raise MsaValidationError(
                "MSA_CRITERIA_PROFILE_INVALID",
                "研究類型不可重複",
                details={"field": "applicable_study_types"},
            )
        return normalized

    @staticmethod
    def _canonical_json(value, *, field: str):
        try:
            encoded = json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            return json.loads(encoded)
        except (OverflowError, TypeError, ValueError) as error:
            raise MsaValidationError(
                "MSA_CRITERIA_JSON_INVALID",
                f"{field} 必須是可重現且僅含有限數值的 JSON",
                details={"field": field},
            ) from error

    @staticmethod
    def _require_object(payload) -> dict:
        if not isinstance(payload, dict):
            raise MsaValidationError(
                "MSA_PAYLOAD_INVALID",
                "請求內容必須是 JSON 物件",
                details={},
            )
        return payload

    @staticmethod
    def _reject_unknown_fields(payload: dict, allowed: set) -> None:
        unknown = sorted(set(payload) - set(allowed))
        if unknown:
            raise MsaValidationError(
                "MSA_UNKNOWN_FIELDS",
                "請求包含未允許欄位",
                details={"unknown_fields": unknown},
            )

    @staticmethod
    def _required_text(
        payload: dict,
        field: str,
        *,
        max_length: int,
        code: str,
    ) -> str:
        value = payload.get(field)
        normalized = MsaCriteriaService._optional_text(
            value,
            field=field,
            max_length=max_length,
            code=code,
        )
        if normalized is None:
            raise MsaValidationError(
                code,
                f"{field} 為必填欄位",
                details={"field": field},
            )
        return normalized

    @staticmethod
    def _optional_text(
        value,
        *,
        field: str,
        max_length: int,
        code: str,
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise MsaValidationError(
                code,
                f"{field} 必須是文字",
                details={"field": field},
            )
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > max_length:
            raise MsaValidationError(
                code,
                f"{field} 超過允許長度",
                details={"field": field, "max_length": max_length},
            )
        return normalized

    @staticmethod
    def _parse_iso_date(value, *, field: str) -> date:
        if isinstance(value, datetime):
            raise MsaValidationError(
                "MSA_CRITERIA_DATE_INVALID",
                f"{field} 必須是 ISO 日期",
                details={"field": field},
            )
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            raise MsaValidationError(
                "MSA_CRITERIA_DATE_INVALID",
                f"{field} 必須是 ISO 日期",
                details={"field": field},
            )
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise MsaValidationError(
                "MSA_CRITERIA_DATE_INVALID",
                f"{field} 必須是 ISO 日期",
                details={"field": field, "value": value},
            ) from error

    @staticmethod
    def _finite_number(value, *, field: str) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            MsaCriteriaService._threshold_error(
                field,
                f"{field} 必須是有限數值",
            )
        return float(value)

    @staticmethod
    def _threshold_error(field: str, message: str):
        raise MsaValidationError(
            "MSA_CRITERIA_THRESHOLDS_INVALID",
            message,
            details={"field": field},
        )

    @staticmethod
    def _parse_bounded_int(
        value,
        *,
        field: str,
        minimum: int,
        maximum: int | None,
        code: str,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise MsaValidationError(
                code,
                f"{field} 必須是整數",
                details={"field": field, "value": value},
            ) from error
        if isinstance(value, bool) or str(parsed) != str(value):
            raise MsaValidationError(
                code,
                f"{field} 必須是整數",
                details={"field": field, "value": value},
            )
        if parsed < minimum or (
            maximum is not None and parsed > maximum
        ):
            raise MsaValidationError(
                code,
                f"{field} 超出允許範圍",
                details={
                    "field": field,
                    "minimum": minimum,
                    "maximum": maximum,
                },
            )
        return parsed


def serialize_criteria_profile(
    profile: MsaCriteriaProfile,
    *,
    include_versions: bool = True,
) -> dict:
    """提供 route 與後續研究模組共用的 profile 序列化入口。"""
    return MsaCriteriaService.serialize_profile(
        profile,
        include_versions=include_versions,
    )


def serialize_criteria_version(version: MsaCriteriaVersion) -> dict:
    """提供 route 與後續研究模組共用的完整版本快照入口。"""
    return MsaCriteriaService.serialize_version(version)
