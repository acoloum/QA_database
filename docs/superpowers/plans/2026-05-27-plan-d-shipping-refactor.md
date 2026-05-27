# Plan D — ShippingData 表重構 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 ShippingData 的 120 個平鋪量測欄位重構為正規化的 `ShippingMeasurement` 子表，並新增 `SPCCache` 快取表，前端改為動態組數表單。

**Architecture:** 後端新增兩個模型（ShippingMeasurement、SPCCache），shipping_service.py 重寫序列化與查詢邏輯，API 回傳格式維持相容。前端 ShippingPage 的量測區塊改為動態新增/刪除組數。

**Tech Stack:** Flask 3.1、SQLAlchemy、Flask-Migrate、React 19、TypeScript

**執行前提：** Plan A 已完成

**量測項目對照：**

| 項目代碼 | 中文名 | 類型 |
|---------|--------|------|
| `od` | 外徑 | 範圍（min/max）|
| `id` | 內徑 | 範圍（min/max）|
| `th` | 厚度 | 範圍（min/max）|
| `concentricity` | 同心度 | 單值 |
| `length` | 長度 | 單值 |
| `hardness` | 硬度 | 單值 |
| `vickers` | 韋伯氏硬度 | 單值 |
| `straightness` | 真直度 | 單值 |
| `roundness` | 真圓度 | 單值 |

---

### Task 1：新增 ShippingMeasurement 和 SPCCache 模型

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1：在 ShippingData 關聯之後新增 ShippingMeasurement**

在 `backend/models.py` 中，`ShippingData` 類別結尾的 `inspector`/`vendor` relationship 之後插入：

```python
# 在 ShippingData 類別內新增 relationship
measurements = db.relationship('ShippingMeasurement', backref='shipping',
                                cascade='all, delete-orphan',
                                order_by='ShippingMeasurement.group_num, ShippingMeasurement.item')
```

接著在 `ShippingData` 類別定義結束後（`VendorToleranceMain` 之前）新增：

```python
class ShippingMeasurement(db.Model):
    """出貨巡檢量測明細 — 每筆對應一個組別的一個量測項目"""
    __tablename__ = '出貨巡檢量測明細'
    __table_args__ = (
        db.UniqueConstraint('出貨檢驗_ID', '組別', '量測項目', name='uq_shipping_group_item'),
        db.Index('idx_shipping_meas_shipping_id', '出貨檢驗_ID'),
    )

    id          = db.Column('識別碼',      db.Integer, primary_key=True)
    shipping_id = db.Column('出貨檢驗_ID', db.Integer, db.ForeignKey('出貨檢驗數據.識別碼'), nullable=False)
    group_num   = db.Column('組別',        db.Integer, nullable=False)
    item        = db.Column('量測項目',    db.String(30), nullable=False)
    # 下限 / 上限（來自公差表或手動輸入）
    lower_limit = db.Column('下限', db.Numeric(12, 4), nullable=True)
    upper_limit = db.Column('上限', db.Numeric(12, 4), nullable=True)
    # 量測值：範圍型用 value_min/value_max，單值型用 value_single
    value_min   = db.Column('量測最小值', db.Numeric(12, 4), nullable=True)
    value_max   = db.Column('量測最大值', db.Numeric(12, 4), nullable=True)
    value_single= db.Column('量測值',     db.Numeric(12, 4), nullable=True)
    is_ng       = db.Column('是否超差',   db.Boolean, default=False, nullable=False)


class SPCCache(db.Model):
    """SPC 計算快取"""
    __tablename__ = 'SPC快取'
    __table_args__ = (
        db.Index('idx_spc_cache_key', '快取鍵'),
    )

    id         = db.Column('識別碼', db.Integer, primary_key=True)
    cache_key  = db.Column('快取鍵',  db.String(255), unique=True, nullable=False)
    result     = db.Column('計算結果', JsonType, nullable=False)
    created_at = db.Column('建立時間', db.DateTime, default=datetime.utcnow)
    expires_at = db.Column('過期時間', db.DateTime, nullable=False)
```

- [ ] **Step 2：產生並套用遷移**

```powershell
cd C:\QC_Database\backend
$env:FLASK_APP = "app.py"
flask db migrate -m "新增出貨巡檢量測明細和SPC快取表"
flask db upgrade
```

- [ ] **Step 3：Commit**

```powershell
git add backend/models.py backend/migrations/
git commit -m "feat(models): 新增 ShippingMeasurement、SPCCache 資料表"
```

---

### Task 2：資料遷移腳本（舊欄位 → 新表）

**Files:**
- Create: `backend/migration/12_migrate_shipping_measurements.py`

- [ ] **Step 1：撰寫遷移腳本**

建立 `backend/migration/12_migrate_shipping_measurements.py`：

```python
"""
將 ShippingData 舊平鋪欄位資料遷移至 ShippingMeasurement 子表
執行方式：python -m backend.migration.12_migrate_shipping_measurements
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.app import create_app
from backend.extensions import db
from backend.models import ShippingData, ShippingMeasurement
from decimal import Decimal, InvalidOperation

RANGE_ITEMS = ['od', 'id', 'th']
SINGLE_ITEMS = ['concentricity', 'length', 'hardness', 'vickers', 'straightness', 'roundness']

ITEM_LABEL_MAP = {
    'od': '外徑', 'id': '內徑', 'th': '厚度',
    'concentricity': '同心度', 'length': '長度',
    'hardness': '硬度', 'vickers': '韋伯氏硬度',
    'straightness': '真直度', 'roundness': '真圓度',
}

def safe_decimal(v):
    try:
        return Decimal(str(v)) if v not in (None, '', 'None') else None
    except InvalidOperation:
        return None

def migrate():
    app = create_app()
    with app.app_context():
        records = ShippingData.query.all()
        print(f'共 {len(records)} 筆出貨巡檢記錄待遷移')
        migrated = 0

        for rec in records:
            gc = rec.group_count or 5
            for g in range(1, int(gc) + 1):
                for item in RANGE_ITEMS:
                    v_min = safe_decimal(getattr(rec, f'{item}{g}_min', None))
                    v_max = safe_decimal(getattr(rec, f'{item}{g}_max', None))
                    if v_min is None and v_max is None:
                        continue
                    is_ng = False
                    m = ShippingMeasurement(
                        shipping_id=rec.id,
                        group_num=g,
                        item=ITEM_LABEL_MAP[item],
                        value_min=v_min,
                        value_max=v_max,
                        is_ng=is_ng,
                    )
                    db.session.add(m)

                for item in SINGLE_ITEMS:
                    v = safe_decimal(getattr(rec, f'{item}{g}', None))
                    if v is None:
                        continue
                    m = ShippingMeasurement(
                        shipping_id=rec.id,
                        group_num=g,
                        item=ITEM_LABEL_MAP[item],
                        value_single=v,
                        is_ng=False,
                    )
                    db.session.add(m)

            migrated += 1
            if migrated % 50 == 0:
                db.session.flush()
                print(f'  已處理 {migrated} 筆...')

        db.session.commit()
        print(f'遷移完成，共處理 {migrated} 筆記錄')

if __name__ == '__main__':
    migrate()
```

- [ ] **Step 2：執行遷移腳本**

```powershell
cd C:\QC_Database
..\venv\Scripts\Activate.ps1  # 或 venv\Scripts\Activate.ps1
python -m backend.migration.12_migrate_shipping_measurements
```

預期輸出：`遷移完成，共處理 N 筆記錄`

- [ ] **Step 3：Commit**

```powershell
git add backend/migration/12_migrate_shipping_measurements.py
git commit -m "script: 出貨巡檢量測資料遷移腳本（舊欄位→明細表）"
```

---

### Task 3：重寫 shipping_service.py 序列化與查詢

**Files:**
- Modify: `backend/services/shipping_service.py`

- [ ] **Step 1：重寫 `_to_dict` 方法**

找到 `_to_dict`（或相等的序列化方法），將量測部分替換為從 `measurements` relationship 讀取並重組為前端相容格式：

```python
@staticmethod
def _to_dict(rec: ShippingData) -> dict:
    from ..models import ShippingMeasurement
    # 重組量測資料為巢狀格式：{group_num: {item: {value_min, value_max, value_single, lower_limit, upper_limit, is_ng}}}
    meas_map: dict = {}
    for m in rec.measurements:
        g = str(m.group_num)
        if g not in meas_map:
            meas_map[g] = {}
        meas_map[g][m.item] = {
            'lower_limit':   float(m.lower_limit)   if m.lower_limit   is not None else None,
            'upper_limit':   float(m.upper_limit)   if m.upper_limit   is not None else None,
            'value_min':     float(m.value_min)     if m.value_min     is not None else None,
            'value_max':     float(m.value_max)     if m.value_max     is not None else None,
            'value_single':  float(m.value_single)  if m.value_single  is not None else None,
            'is_ng':         m.is_ng,
        }

    return {
        'id':          rec.id,
        'date':        rec.date.isoformat() if rec.date else None,
        'material':    rec.material,
        'spec':        rec.spec,
        'order_num':   rec.order_num,
        'group_count': rec.group_count,
        'inspector_id':   rec.inspector_id,
        'inspector_name': rec.inspector.name if rec.inspector else None,
        'vendor_id':      rec.vendor_id,
        'vendor_name':    rec.vendor.name if rec.vendor else None,
        'is_ng':          rec.is_ng,
        'measurements':   meas_map,
    }
```

- [ ] **Step 2：重寫 create 方法以儲存明細**

在 create 方法中，處理完主檔後遍歷前端傳入的 `measurements` 建立明細：

```python
@staticmethod
def create(data: dict, creator_id=None) -> dict:
    from ..models import ShippingData, ShippingMeasurement

    rec = ShippingData(
        date=data.get('date'),
        material=data.get('material'),
        spec=data.get('spec'),
        order_num=data.get('order_num'),
        inspector_id=data.get('inspector_id'),
        vendor_id=data.get('vendor_id'),
        group_count=data.get('group_count', 1),
        is_ng=False,
    )
    db.session.add(rec)
    db.session.flush()  # 取得 rec.id

    # measurements 格式：{group_num: {item: {lower_limit, upper_limit, value_min, value_max, value_single}}}
    any_ng = False
    for g_str, items in (data.get('measurements') or {}).items():
        for item_name, vals in items.items():
            lower = vals.get('lower_limit')
            upper = vals.get('upper_limit')
            v_min = vals.get('value_min')
            v_max = vals.get('value_max')
            v_single = vals.get('value_single')

            # 計算 is_ng
            item_ng = False
            if lower is not None and upper is not None:
                if v_min is not None and (float(v_min) < float(lower) or float(v_min) > float(upper)):
                    item_ng = True
                if v_max is not None and (float(v_max) < float(lower) or float(v_max) > float(upper)):
                    item_ng = True
                if v_single is not None and (float(v_single) < float(lower) or float(v_single) > float(upper)):
                    item_ng = True

            if item_ng:
                any_ng = True

            m = ShippingMeasurement(
                shipping_id=rec.id,
                group_num=int(g_str),
                item=item_name,
                lower_limit=lower,
                upper_limit=upper,
                value_min=v_min,
                value_max=v_max,
                value_single=v_single,
                is_ng=item_ng,
            )
            db.session.add(m)

    rec.is_ng = any_ng
    db.session.commit()
    return ShippingService._to_dict(rec)
```

- [ ] **Step 3：重寫 update 方法**

update 時刪除原有明細再重建：

```python
@staticmethod
def update(shipping_id: int, data: dict) -> dict:
    from ..models import ShippingData, ShippingMeasurement

    rec = ShippingData.query.get(shipping_id)
    if not rec:
        raise ValueError('記錄不存在')

    # 更新主檔欄位
    for field in ('date', 'material', 'spec', 'order_num', 'inspector_id', 'vendor_id', 'group_count'):
        if field in data:
            setattr(rec, field, data[field])

    # 重建明細
    if 'measurements' in data:
        ShippingMeasurement.query.filter_by(shipping_id=rec.id).delete()
        any_ng = False
        for g_str, items in data['measurements'].items():
            for item_name, vals in items.items():
                lower = vals.get('lower_limit')
                upper = vals.get('upper_limit')
                v_min = vals.get('value_min')
                v_max = vals.get('value_max')
                v_single = vals.get('value_single')
                item_ng = False
                if lower is not None and upper is not None:
                    for v in filter(None, [v_min, v_max, v_single]):
                        if float(v) < float(lower) or float(v) > float(upper):
                            item_ng = True
                if item_ng:
                    any_ng = True
                db.session.add(ShippingMeasurement(
                    shipping_id=rec.id, group_num=int(g_str),
                    item=item_name, lower_limit=lower, upper_limit=upper,
                    value_min=v_min, value_max=v_max, value_single=v_single, is_ng=item_ng,
                ))
        rec.is_ng = any_ng

    db.session.commit()
    return ShippingService._to_dict(rec)
```

- [ ] **Step 4：列表查詢加入 joinedload measurements**

```python
from sqlalchemy.orm import joinedload

items = ShippingData.query\
    .options(
        joinedload(ShippingData.inspector),
        joinedload(ShippingData.vendor),
        joinedload(ShippingData.measurements),
    )\
    .order_by(ShippingData.date.desc())\
    .all()
```

- [ ] **Step 5：Commit**

```powershell
git add backend/services/shipping_service.py
git commit -m "refactor(shipping): 切換至 ShippingMeasurement 子表讀寫"
```

---

### Task 4：前端 TypeScript 類型更新

**Files:**
- Modify: `src_frontend/src/types/index.ts`

- [ ] **Step 1：新增量測相關類型**

在 `index.ts` 中新增：

```typescript
export interface ShippingMeasurementItem {
    lower_limit?: number | null;
    upper_limit?: number | null;
    value_min?: number | null;
    value_max?: number | null;
    value_single?: number | null;
    is_ng: boolean;
}

// key: group_num (string), value: { [itemName]: ShippingMeasurementItem }
export type ShippingMeasurements = Record<string, Record<string, ShippingMeasurementItem>>;
```

- [ ] **Step 2：更新 ShippingData interface**

找到 `ShippingData`（或 `ShippingInspection`）interface，移除舊的 `od1_min`、`od1_max`… 等平鋪欄位，替換為：

```typescript
export interface ShippingInspection {
    id: number;
    date: string;
    material?: string;
    spec?: string;
    order_num?: string;
    group_count: number;
    inspector_id?: number;
    inspector_name?: string;
    vendor_id?: number;
    vendor_name?: string;
    is_ng: boolean;
    measurements: ShippingMeasurements;
}
```

- [ ] **Step 3：Commit**

```powershell
git add src_frontend/src/types/index.ts
git commit -m "types(shipping): 更新 ShippingInspection 使用新量測明細結構"
```

---

### Task 5：前端 ShippingPage 動態組數表單

**Files:**
- Modify: `src_frontend/src/pages/shipping/ShippingPage.tsx`（或含表單的 Modal 元件）
- Modify: `src_frontend/src/hooks/useShipping.ts`（若存在）

- [ ] **Step 1：找到出貨巡檢表單元件**

```powershell
Get-ChildItem src_frontend/src/pages/shipping -Recurse | Select-Object Name
Get-ChildItem src_frontend/src/components/shipping -Recurse -ErrorAction SilentlyContinue | Select-Object Name
```

- [ ] **Step 2：新增動態組數狀態**

在表單元件的狀態定義處，新增：

```typescript
const ITEM_NAMES = ['外徑', '內徑', '厚度', '同心度', '長度', '硬度', '韋伯氏硬度', '真直度', '真圓度'];
const RANGE_ITEMS = new Set(['外徑', '內徑', '厚度']);

// 初始化一組空量測
const emptyGroup = (): Record<string, Partial<ShippingMeasurementItem>> =>
    Object.fromEntries(ITEM_NAMES.map(name => [name, { is_ng: false }]));

const [groups, setGroups] = useState<Record<string, Record<string, Partial<ShippingMeasurementItem>>>>({
    '1': emptyGroup(),
});
```

- [ ] **Step 3：新增「新增量測組」按鈕與刪除邏輯**

```typescript
const addGroup = () => {
    const nextNum = String(Math.max(...Object.keys(groups).map(Number)) + 1);
    setGroups(prev => ({ ...prev, [nextNum]: emptyGroup() }));
};

const removeGroup = (gNum: string) => {
    if (Object.keys(groups).length <= 1) return; // 至少保留一組
    setGroups(prev => {
        const next = { ...prev };
        delete next[gNum];
        return next;
    });
};

const updateMeasValue = (gNum: string, item: string, field: string, value: string) => {
    setGroups(prev => ({
        ...prev,
        [gNum]: {
            ...prev[gNum],
            [item]: { ...prev[gNum][item], [field]: value === '' ? null : Number(value) },
        },
    }));
};
```

- [ ] **Step 4：渲染量測組表格**

在表單 JSX 中，將原本固定組數的量測區塊替換為：

```tsx
{/* 量測組 */}
{Object.entries(groups).map(([gNum, items]) => (
    <div key={gNum} className="border rounded p-3 mb-3">
        <div className="d-flex justify-content-between align-items-center mb-2">
            <strong>第 {gNum} 組</strong>
            <Button variant="outline-danger" size="sm" onClick={() => removeGroup(gNum)}>✕ 移除</Button>
        </div>
        <Table size="sm" bordered>
            <thead>
                <tr>
                    <th>項目</th>
                    <th>下限</th>
                    <th>上限</th>
                    <th>量測值 (min)</th>
                    <th>量測值 (max)</th>
                    <th>單值</th>
                </tr>
            </thead>
            <tbody>
                {ITEM_NAMES.map(itemName => (
                    <tr key={itemName}>
                        <td>{itemName}</td>
                        <td>
                            <Form.Control size="sm" type="number" step="0.001"
                                value={items[itemName]?.lower_limit ?? ''}
                                onChange={e => updateMeasValue(gNum, itemName, 'lower_limit', e.target.value)} />
                        </td>
                        <td>
                            <Form.Control size="sm" type="number" step="0.001"
                                value={items[itemName]?.upper_limit ?? ''}
                                onChange={e => updateMeasValue(gNum, itemName, 'upper_limit', e.target.value)} />
                        </td>
                        {RANGE_ITEMS.has(itemName) ? (
                            <>
                                <td>
                                    <Form.Control size="sm" type="number" step="0.001"
                                        value={items[itemName]?.value_min ?? ''}
                                        onChange={e => updateMeasValue(gNum, itemName, 'value_min', e.target.value)} />
                                </td>
                                <td>
                                    <Form.Control size="sm" type="number" step="0.001"
                                        value={items[itemName]?.value_max ?? ''}
                                        onChange={e => updateMeasValue(gNum, itemName, 'value_max', e.target.value)} />
                                </td>
                                <td>—</td>
                            </>
                        ) : (
                            <>
                                <td>—</td>
                                <td>—</td>
                                <td>
                                    <Form.Control size="sm" type="number" step="0.001"
                                        value={items[itemName]?.value_single ?? ''}
                                        onChange={e => updateMeasValue(gNum, itemName, 'value_single', e.target.value)} />
                                </td>
                            </>
                        )}
                    </tr>
                ))}
            </tbody>
        </Table>
    </div>
))}
<Button variant="outline-primary" className="mb-3" onClick={addGroup}>
    ＋ 新增量測組
</Button>
```

- [ ] **Step 5：buildPayload 改為傳 measurements**

```typescript
const buildPayload = () => ({
    date: inspectionDate,
    material,
    spec,
    order_num: orderNum,
    inspector_id: inspectorId,
    vendor_id: vendorId,
    group_count: Object.keys(groups).length,
    measurements: groups,
});
```

- [ ] **Step 6：編輯模式載入舊資料**

在 `useEffect` 填入 editData 的地方，將舊 measurements 填入 groups 狀態：

```typescript
if (editData?.measurements) {
    setGroups(editData.measurements as Record<string, Record<string, Partial<ShippingMeasurementItem>>>);
}
```

- [ ] **Step 7：TypeScript build 驗證**

```powershell
cd C:\QC_Database\src_frontend
npm run build
```

預期：無 TypeScript 錯誤

- [ ] **Step 8：Commit**

```powershell
git add src_frontend/src/
git commit -m "feat(shipping-ui): 動態量測組數表單，支援新增/刪除組"
```

---

### Task 6：SPC 服務整合快取

**Files:**
- Modify: `backend/services/spc_report.py`（或對應的 SPC 計算服務）

- [ ] **Step 1：找到 SPC 計算入口**

```powershell
grep -r "Cpk\|xbar\|spc" backend/services/ --include="*.py" -l
```

- [ ] **Step 2：在計算函數前後加入快取讀寫**

```python
from datetime import datetime, timedelta
from ..models import SPCCache

def get_spc_stats(material: str, spec: str, item: str, date_from=None, date_to=None) -> dict:
    cache_key = f"spc|{material}|{spec}|{item}|{date_from}|{date_to}"

    # 讀快取
    cached = SPCCache.query.filter_by(cache_key=cache_key).first()
    if cached and cached.expires_at > datetime.utcnow():
        return cached.result

    # 計算（原有邏輯）
    result = _compute_spc(material, spec, item, date_from, date_to)

    # 寫快取（1 小時過期）
    if cached:
        cached.result = result
        cached.created_at = datetime.utcnow()
        cached.expires_at = datetime.utcnow() + timedelta(hours=1)
    else:
        db.session.add(SPCCache(
            cache_key=cache_key,
            result=result,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        ))
    db.session.commit()

    return result
```

- [ ] **Step 3：Commit**

```powershell
git add backend/services/spc_report.py
git commit -m "perf(spc): 加入 SPCCache DB 快取，1 小時過期"
```

---

### Task 7：推送

- [ ] **Push to GitHub**

```powershell
cd C:\QC_Database
git push origin master
```
