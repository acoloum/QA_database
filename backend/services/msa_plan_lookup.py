"""MSA 計畫版本的共用查詢：確認存在且已凍結。"""

from ..extensions import db
from ..models import MsaPlanVersion
from .msa_errors import MsaConflict, MsaNotFound


def require_frozen_plan(
    plan_id: int, *, message: str, for_update: bool = False,
) -> MsaPlanVersion:
    """取得計畫版本並確認已凍結；未凍結時以呼叫端提供的訊息報錯。"""
    if for_update:
        plan = (
            MsaPlanVersion.query
            .filter_by(id=plan_id)
            .with_for_update()
            .one_or_none()
        )
    else:
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
            message,
            details={"plan_id": plan_id},
        )
    return plan
