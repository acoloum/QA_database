# -*- coding: utf-8 -*-
"""重算既有巡檢紀錄的「是否超差」旗標。

背景：與出貨檢驗相同，巡檢的 is_ng 是存檔當下依當時的公差算出後凍結的，公差之後
才建立或修改都不會回頭補判。公差異動自動重判的機制（services/tolerance_recompute.py）
上線後這種落差不會再累積，但機制上線前既有的落差仍要一次清掉——否則會夾在某次
公差存檔裡無聲翻動。

判定邏輯直接複用 tolerance_recompute.recompute_patrol，與線上自動重判走同一條路，
避免兩份實作各自漂移。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_patrol_is_ng          # dry-run
    .\\venv\\Scripts\\python.exe -m backend.scripts.recompute_patrol_is_ng --apply  # 實際寫入
"""
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import PatrolMain, Vendor
from ..services.tolerance_recompute import recompute_patrol


def main(apply_changes: bool):
    with app.app_context():
        total = PatrolMain.query.count()
        changed_ids = recompute_patrol()

        print('=' * 72)
        print(f'  巡檢總筆數：{total}　需更新筆數：{len(changed_ids)}')
        print('=' * 72)

        for pid in changed_ids:
            record = db.session.get(PatrolMain, pid)
            vendor = db.session.get(Vendor, record.customer_id) if record.customer_id else None
            # recompute_patrol 已把新值寫進 record.is_ng，故此處顯示的是翻動後的結果
            print(f'  #{record.id}  {record.date}  '
                  f'{vendor.name.strip() if vendor else "(無客戶)"}  '
                  f'{record.material}  {record.spec}  '
                  f'：{"合格" if record.is_ng else "超差"} → {"超差" if record.is_ng else "合格"}')

        if apply_changes:
            db.session.commit()
            print('\n  ✅ 已寫入資料庫。')
        else:
            db.session.rollback()
            print('\n  ℹ️  DRY-RUN，未寫入。確認無誤後加 --apply 實際更新。')
        return 0


if __name__ == '__main__':
    sys.exit(main(apply_changes='--apply' in sys.argv))
