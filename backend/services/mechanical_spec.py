"""機械性質規格撈取與 NG 判定。

規格為單邊下限（只有下限、沒有上限）：量測值 < 下限 → NG。
規格值直接讀取既有「廠商公差」，依（材質 + 產品尺寸）比對，
量測項目對應廠商公差項目採 MECH_ITEM_TO_TOLERANCE 映射。EC 無規格。
"""
from decimal import Decimal
import re
from typing import Any, Dict, Optional

from ..models import VendorToleranceMain, VendorToleranceDetail
from .extrusion_tolerance_service import ExtrusionToleranceService

# 機械性質判定項目 → 廠商公差「測量項目」
MECH_ITEM_TO_TOLERANCE: Dict[str, str] = {
    "硬度": "洛氏硬度",
    "抗拉強度": "抗拉強度",
    "降伏強度": "降伏強度",
    "伸長率": "伸長率",
}


def lookup_lower_limits(
    material: str, product_size: str, vendor_id: Optional[int] = None
) -> Dict[str, float]:
    """回傳 {機械性質項目: 下限}，查無則不含該項；EC 不查。

    候選優先序依序為：材質完全相同、規格正規化後完全相同、
    規格僅前兩段相同（_match_spec 的相近匹配）；相同層級再依 id
    由小到大取第一筆，避免依賴資料庫回傳順序。
    """
    if not material or not product_size or vendor_id is None:
        return {}

    match_material = ExtrusionToleranceService._match_material
    match_spec = ExtrusionToleranceService._match_spec
    normalize_spec = ExtrusionToleranceService._normalize_spec

    query = VendorToleranceMain.query.filter(
        VendorToleranceMain.material.isnot(None),
        VendorToleranceMain.vendor_id == vendor_id,
    )
    mains = query.order_by(VendorToleranceMain.id.asc()).all()

    normalize_compact = lambda value: re.sub(r"\s+", "", normalize_spec(value))
    normalized_input = normalize_compact(product_size)
    normalized_material = material.strip().lower()
    candidates = []
    for m in mains:
        if not match_material(material, m.material):
            continue
        m_spec = m.spec or ""
        compact_spec = normalize_compact(m_spec)
        if not match_spec(normalized_input, compact_spec):
            continue
        candidates.append((
            0 if (m.material or "").strip().lower() == normalized_material else 1,
            0 if compact_spec == normalized_input else 1,
            m.id,
            m,
        ))

    candidate_entry = min(candidates, default=None, key=lambda entry: entry[:3])
    candidate = candidate_entry[3] if candidate_entry else None
    if candidate is None:
        return {}

    # 反查：廠商公差項目 → 機械性質項目
    tol_to_mech = {v: k for k, v in MECH_ITEM_TO_TOLERANCE.items()}
    result: Dict[str, float] = {}
    details = VendorToleranceDetail.query.filter_by(main_id=candidate.id).all()
    for d in details:
        mech_item = tol_to_mech.get(d.item)
        if not mech_item:
            continue
        # 優先使用尺寸下限（廠商公差頁面填寫下限的慣用欄位），
        # 沒有尺寸下限時退而使用公差下限（視為絕對下限值）。
        lower = d.dim_min if d.dim_min is not None else d.tolerance_min
        if lower is not None:
            result[mech_item] = lower
    return result


def resolve_material_by_spec(
    product_size: str, vendor_id: Optional[int]
) -> Dict[str, Any]:
    """依（廠商 + 產品尺寸）反查廠商公差內建檔登錄的材質。

    來源 Excel 沒有材質欄位，而同一廠商不同規格可能是不同材質，
    整批套用單一材質會誤標；此處以規格反查公差主檔還原正確材質。

    比對分兩層，且**精確層有解就不看模糊層**（避免精確唯一解被模糊層的
    其他材質拖成 ambiguous）：
      1. exact：規格正規化後完全相同
      2. fuzzy：規格僅前兩段相同（_match_spec 的相近匹配）
    同層若去重後只有一個材質即為 resolved；有多個則為 ambiguous
    （不擅自挑選，交由呼叫端回報候選供人工判斷）。

    回傳 {"status": "resolved"|"ambiguous"|"not_found",
          "material": 材質或 None, "candidates": 候選材質清單,
          "match": "exact"|"fuzzy"|None}
    """
    if not product_size or vendor_id is None:
        return {"status": "not_found", "material": None, "candidates": [], "match": None}

    normalize_spec = ExtrusionToleranceService._normalize_spec
    match_spec = ExtrusionToleranceService._match_spec
    normalize_compact = lambda value: re.sub(r"\s+", "", normalize_spec(value))
    normalized_input = normalize_compact(product_size)

    mains = VendorToleranceMain.query.filter(
        VendorToleranceMain.material.isnot(None),
        VendorToleranceMain.vendor_id == vendor_id,
    ).order_by(VendorToleranceMain.id.asc()).all()

    exact: Dict[str, str] = {}
    fuzzy: Dict[str, str] = {}
    for main in mains:
        material = (main.material or "").strip()
        if not material:
            continue
        compact_spec = normalize_compact(main.spec or "")
        if not compact_spec:
            continue
        # 大小寫不同視為同一材質；保留公差檔 id 最小者的原始寫法
        key = material.lower()
        if compact_spec == normalized_input:
            exact.setdefault(key, material)
        elif match_spec(normalized_input, compact_spec):
            fuzzy.setdefault(key, material)

    for level, bucket in (("exact", exact), ("fuzzy", fuzzy)):
        if not bucket:
            continue
        candidates = sorted(bucket.values())
        if len(candidates) == 1:
            return {
                "status": "resolved",
                "material": candidates[0],
                "candidates": candidates,
                "match": level,
            }
        return {
            "status": "ambiguous",
            "material": None,
            "candidates": candidates,
            "match": level,
        }

    return {"status": "not_found", "material": None, "candidates": [], "match": None}


def compute_measurement_ng(value: Optional[float], lower_limit: Optional[float]) -> bool:
    """單邊下限判定：有值且有下限且值 < 下限 → True，其餘 False。"""
    if value is None or lower_limit is None:
        return False
    return Decimal(str(value)) < Decimal(str(lower_limit))
