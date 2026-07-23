"""機械性質規格撈取與 NG 判定。

規格為單邊下限（只有下限、沒有上限）：量測值 < 下限 → NG。
規格值直接讀取既有「廠商公差」，依（材質 + 產品尺寸）比對，
量測項目對應廠商公差項目採 MECH_ITEM_TO_TOLERANCE 映射。EC 無規格。
"""
from decimal import Decimal
from typing import Dict, Optional

from ..models import VendorToleranceMain, VendorToleranceDetail
from .extrusion_tolerance_service import ExtrusionToleranceService

# 機械性質判定項目 → 廠商公差「測量項目」
MECH_ITEM_TO_TOLERANCE: Dict[str, str] = {
    "硬度": "洛氏硬度",
    "抗拉強度": "抗拉強度",
    "降伏強度": "降伏強度",
    "伸長率": "伸長率",
}


def lookup_lower_limits(material: str, product_size: str) -> Dict[str, Decimal]:
    """回傳 {機械性質項目: 下限}，查無則不含該項；EC 不查。"""
    if not material or not product_size:
        return {}

    match_material = ExtrusionToleranceService._match_material
    match_spec = ExtrusionToleranceService._match_spec

    mains = VendorToleranceMain.query.filter(
        VendorToleranceMain.material.isnot(None)
    ).all()
    candidate = None
    for m in mains:
        if match_material(material, m.material) and match_spec(product_size, m.spec or ""):
            candidate = m
            break
    if candidate is None:
        return {}

    # 反查：廠商公差項目 → 機械性質項目
    tol_to_mech = {v: k for k, v in MECH_ITEM_TO_TOLERANCE.items()}
    result: Dict[str, Decimal] = {}
    details = VendorToleranceDetail.query.filter_by(main_id=candidate.id).all()
    for d in details:
        mech_item = tol_to_mech.get(d.item)
        if mech_item and d.tolerance_min is not None:
            result[mech_item] = d.tolerance_min
    return result


def compute_measurement_ng(value: Optional[float], lower_limit: Optional[float]) -> bool:
    """單邊下限判定：有值且有下限且值 < 下限 → True，其餘 False。"""
    if value is None or lower_limit is None:
        return False
    return Decimal(str(value)) < Decimal(str(lower_limit))
