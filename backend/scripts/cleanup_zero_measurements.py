# -*- coding: utf-8 -*-
"""清理歷史「未量測卻存成 0」的量測值 → 改為 NULL。

背景：扁平欄位時代，外徑/內徑/厚度/長度/硬度等空白量測被存成 0.0。現行匯入與遷移
腳本已正確寫 NULL/跳過，但既有資料仍殘留大量 0。這些 0：
  1. 被 SPC 統計納入計算（_measurement_value 只排除 None，不排除 0）→ 污染均值與管制界限。
  2. 曾造成 is_ng 假性超差（compute_is_ng 已修正為 0 視為未量測，但資料面仍宜清乾淨）。

處理項目（值為 0 即代表未量測）：外徑/內徑/厚度/長度/硬度/韋伯氏硬度。
  真圓度/同心度/真直度的 0 是理想值(真實好值)，不在清理範圍。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.cleanup_zero_measurements          # dry-run，只統計
    .\\venv\\Scripts\\python.exe -m backend.scripts.cleanup_zero_measurements --apply  # 實際寫入
"""
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import ShippingMeasurement
from ..services.shipping_service import ShippingService

# 值為 0 代表未量測的項目（與 compute_is_ng 一致）
ZERO_MEANS_UNMEASURED = ('外徑', '內徑', '厚度', '長度', '硬度', '韋伯氏硬度')

FIELDS = (
    ('量測最小值', ShippingMeasurement.value_min),
    ('量測最大值', ShippingMeasurement.value_max),
    ('量測值', ShippingMeasurement.value_single),
)


def main(apply: bool):
    with app.app_context():
        base = ShippingMeasurement.query.filter(
            ShippingMeasurement.item.in_(ZERO_MEANS_UNMEASURED)
        )

        print("=" * 60)
        print("  將 0 值改為 NULL 的欄位統計（依項目分列於下）：")
        total = 0
        for label, col in FIELDS:
            cnt = base.filter(col == 0).count()
            total += cnt
            print(f"    {label:8s}= 0 → NULL：{cnt} 筆")
        print(f"  合計欄位更新數：{total}")
        print("=" * 60)

        if apply:
            updated = 0
            for _label, col in FIELDS:
                updated += base.filter(col == 0).update(
                    {col: None}, synchronize_session=False
                )
            # 統計值已變動，清除 SPC 快取避免圖表讀到舊結果
            ShippingService._invalidate_spc_cache()
            db.session.commit()
            print(f"  ✅ 已寫入資料庫，更新 {updated} 個欄位，並清除 SPC 快取。")
        else:
            db.session.rollback()
            print("  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際更新。")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
