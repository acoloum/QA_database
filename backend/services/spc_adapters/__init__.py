"""出貨與巡檢資料轉成 SPC 共用研究輸入的轉接器。"""

from .patrol import build_patrol_study_input
from .shipping import build_shipping_study_input

__all__ = ["build_patrol_study_input", "build_shipping_study_input"]
