# 出貨檢驗外徑分段量測(前/中/後)實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 出貨檢驗的外徑量測可由檢驗員手動切換為前/中/後三段模式,資料以「測量位置」欄位存於子表,舊紀錄與 API 格式完全相容。

**Architecture:** DB 子表 `出貨巡檢量測明細` 加「測量位置」欄(空字串=未分段),唯一鍵納入位置。API 巢狀 `measurements[組別][鍵]` 以複合鍵 `外徑@前段` 傳輸分段資料,未分段鍵不變。前端 `ShippingItemConfig` 加通用 `segmentable` flag,以純函式將啟用分段的項目展開為三列,既有驗證/違規/tabIndex 機制以 `item.key` 為鍵自動生效;三段共用「外徑」公差(走既有 `toleranceKey` fallback)。

**Tech Stack:** Flask 3.1 + SQLAlchemy(後端,pytest 測試)、React 19 + TypeScript(前端,vitest 測試)、PostgreSQL 16(raw SQL migration)。

**規格:** `docs/superpowers/specs/2026-07-09-shipping-od-segmented-measurement-design.md`

**測試指令慣例:**
- 後端(repo 根目錄、venv 已啟用):`python -m pytest backend/tests/... -v`
- 前端(於 `src_frontend/`):`npx vitest run src/components/shipping/<檔案>`

---

### Task 1: 後端複合鍵 helper 模組

**Files:**
- Create: `backend/services/shipping_measurement_keys.py`
- Test: `backend/tests/test_services/test_shipping_measurement_keys.py`

- [ ] **Step 1: 撰寫失敗測試**

```python
from backend.services.shipping_measurement_keys import (
    SEGMENT_POSITIONS,
    build_measurement_key,
    parse_measurement_key,
)


def test_segment_positions_order():
    assert SEGMENT_POSITIONS == ('前段', '中段', '後段')


def test_parse_plain_key_returns_empty_position():
    assert parse_measurement_key('外徑') == ('外徑', '')


def test_parse_segmented_key():
    assert parse_measurement_key('外徑@前段') == ('外徑', '前段')
    assert parse_measurement_key('外徑@中段') == ('外徑', '中段')
    assert parse_measurement_key('外徑@後段') == ('外徑', '後段')


def test_parse_invalid_position_returns_none():
    # 位置不合法時回傳 (項目, None),供呼叫端略過
    assert parse_measurement_key('外徑@亂段') == ('外徑', None)
    assert parse_measurement_key('外徑@') == ('外徑', None)


def test_build_key_roundtrip():
    assert build_measurement_key('外徑', '') == '外徑'
    assert build_measurement_key('外徑', None) == '外徑'
    assert build_measurement_key('外徑', '前段') == '外徑@前段'
    assert build_measurement_key('外徑', ' 前段 ') == '外徑@前段'
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_shipping_measurement_keys.py -v`
Expected: FAIL(ModuleNotFoundError: shipping_measurement_keys)

- [ ] **Step 3: 實作 helper 模組**

`backend/services/shipping_measurement_keys.py`:

```python
"""出貨檢驗量測複合鍵處理 — 「項目@位置」字串與 (項目, 位置) 之間互轉。

未分段資料的鍵即項目名(位置為空字串);分段資料鍵為「項目@位置」,
位置僅允許 前段/中段/後段(與巡檢子檔用語一致)。
"""

SEGMENT_POSITIONS = ('前段', '中段', '後段')


def parse_measurement_key(key):
    """拆解複合鍵,回傳 (項目, 位置)。

    無 @ 的鍵位置為空字串;位置不合法時回傳 (項目, None) 供呼叫端略過。
    """
    item, sep, position = str(key).partition('@')
    if not sep:
        return item, ''
    position = position.strip()
    if position in SEGMENT_POSITIONS:
        return item, position
    return item, None


def build_measurement_key(item, position):
    """由項目與位置組回複合鍵;位置為空(或 None)時只回項目名。"""
    position = (position or '').strip()
    return f"{item}@{position}" if position else item
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_shipping_measurement_keys.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/shipping_measurement_keys.py backend/tests/test_services/test_shipping_measurement_keys.py
git commit -m "新增出貨檢驗量測複合鍵 helper(項目@位置 互轉)"
```

---

### Task 2: 模型加「測量位置」欄位與 migration SQL

**Files:**
- Modify: `backend/models.py:216-233`(ShippingMeasurement)
- Create: `backend/migration/32_add_shipping_measurement_position.sql`

- [ ] **Step 1: 修改 ShippingMeasurement 模型**

`backend/models.py` 的 `ShippingMeasurement`:唯一鍵納入位置,並在 `item` 欄位後新增 `position` 欄:

```python
class ShippingMeasurement(db.Model):
    """出貨巡檢量測明細 — 每筆對應一個組別的一個量測項目(可含測量位置)"""
    __tablename__ = '出貨巡檢量測明細'
    __table_args__ = (
        db.UniqueConstraint('出貨檢驗_ID', '組別', '量測項目', '測量位置',
                            name='uq_shipping_group_item'),
        db.Index('idx_shipping_meas_shipping_id', '出貨檢驗_ID'),
    )

    id          = db.Column('識別碼',      db.Integer, primary_key=True)
    shipping_id = db.Column('出貨檢驗_ID', db.Integer, db.ForeignKey('出貨檢驗數據.識別碼'), nullable=False)
    group_num   = db.Column('組別',        db.Integer, nullable=False)
    item        = db.Column('量測項目',    db.String(30), nullable=False)
    # 空字串 = 未分段(刻意不用 NULL:PostgreSQL 唯一鍵不比較 NULL,會使重複防護失效)
    position    = db.Column('測量位置',    db.String(10), nullable=False, default='', server_default='')
    lower_limit = db.Column('下限', db.Numeric(12, 4), nullable=True)
    upper_limit = db.Column('上限', db.Numeric(12, 4), nullable=True)
    value_min   = db.Column('量測最小值', db.Numeric(12, 4), nullable=True)
    value_max   = db.Column('量測最大值', db.Numeric(12, 4), nullable=True)
    value_single= db.Column('量測值',     db.Numeric(12, 4), nullable=True)
    is_ng       = db.Column('是否超差',   db.Boolean, default=False, nullable=False)
```

- [ ] **Step 2: 建立 migration SQL**

`backend/migration/32_add_shipping_measurement_position.sql`:

```sql
-- 出貨巡檢量測明細新增「測量位置」欄位(支援外徑前/中/後分段量測)
-- 空字串 = 未分段;唯一鍵納入位置。既有資料不需搬移。
BEGIN;

ALTER TABLE "出貨巡檢量測明細"
    ADD COLUMN IF NOT EXISTS "測量位置" VARCHAR(10) NOT NULL DEFAULT '';

ALTER TABLE "出貨巡檢量測明細"
    DROP CONSTRAINT IF EXISTS uq_shipping_group_item;

ALTER TABLE "出貨巡檢量測明細"
    ADD CONSTRAINT uq_shipping_group_item
    UNIQUE ("出貨檢驗_ID", "組別", "量測項目", "測量位置");

COMMIT;
```

- [ ] **Step 3: 執行既有後端測試確認無迴歸**

Run: `python -m pytest backend/tests/ -q`
Expected: 全數通過(測試用 sqlite `create_all`,新欄位有 default,不影響既有測試)

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/migration/32_add_shipping_measurement_position.sql
git commit -m "出貨巡檢量測明細新增測量位置欄位,唯一鍵納入位置"
```

**注意:** 部署時需對正式 DB 手動執行 `psql -U postgres -d qa_database -f backend/migration/32_add_shipping_measurement_position.sql`(依專案慣例)。

---

### Task 3: shipping_service 寫入與回傳支援複合鍵

**Files:**
- Modify: `backend/services/shipping_service.py:67-79`(`_map_row_to_dict` 回傳)
- Modify: `backend/services/shipping_service.py:464-488`(`save_data` 寫入)
- Test: `backend/tests/test_services/test_shipping_position_roundtrip.py`

- [ ] **Step 1: 撰寫失敗測試**

`backend/tests/test_services/test_shipping_position_roundtrip.py`:

```python
from backend.models import ShippingData, ShippingMeasurement
from backend.services.shipping_service import ShippingService


def _base_payload(measurements):
    return {
        '檢驗日期': '2026-07-09',
        '檢驗人員姓名': 'Test Inspector',
        '廠商中文名稱': 'Test Vendor',
        '檢驗規格': '10*2',
        '材質': '6061',
        '訂單號碼': 'SO-1',
        '組數': 1,
        'measurements': measurements,
    }


def test_segmented_keys_roundtrip(db_session, setup_data):
    """分段複合鍵寫入後,DB 項目欄保持乾淨、回傳時組回複合鍵"""
    payload = _base_payload({
        '1': {
            '外徑@前段': {'value_min': 9.8, 'value_max': 10.1},
            '外徑@中段': {'value_min': 9.9, 'value_max': 10.2},
            '外徑@後段': {'value_min': 9.7, 'value_max': 10.0},
            '硬度': {'value_single': 55},
        },
    })
    ShippingService.save_data(payload)

    rows = ShippingMeasurement.query.filter_by(item='外徑').all()
    assert sorted(r.position for r in rows) == ['中段', '前段', '後段']
    hardness = ShippingMeasurement.query.filter_by(item='硬度').one()
    assert hardness.position == ''

    record = ShippingData.query.first()
    res = ShippingService._map_row_to_dict(record)
    assert set(res['measurements']['1'].keys()) == {'外徑@前段', '外徑@中段', '外徑@後段', '硬度'}
    assert res['measurements']['1']['外徑@中段']['value_max'] == 10.2


def test_invalid_position_skipped(db_session, setup_data):
    """位置不合法的鍵應整筆略過,不寫入子表"""
    payload = _base_payload({'1': {'外徑@亂段': {'value_min': 1}}})
    ShippingService.save_data(payload)
    assert ShippingMeasurement.query.count() == 0


def test_plain_keys_unchanged(db_session, setup_data):
    """未分段資料行為與現行完全相同"""
    payload = _base_payload({'1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}}})
    ShippingService.save_data(payload)

    row = ShippingMeasurement.query.one()
    assert (row.item, row.position) == ('外徑', '')

    record = ShippingData.query.first()
    res = ShippingService._map_row_to_dict(record)
    assert list(res['measurements']['1'].keys()) == ['外徑']
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_shipping_position_roundtrip.py -v`
Expected: `test_segmented_keys_roundtrip` FAIL(`外徑@前段` 不在 VALID_ITEMS 被略過,子表無資料)

- [ ] **Step 3: 修改 save_data 寫入路徑**

`backend/services/shipping_service.py` 檔頭 import 區加入:

```python
from .shipping_measurement_keys import build_measurement_key, parse_measurement_key
```

`save_data` 內迴圈(原 464-488 行)改為:

```python
            for g_str, items in measurements.items():
                try:
                    g = int(g_str)
                except (ValueError, TypeError):
                    continue
                if not (1 <= g <= 10):
                    continue
                for item_key, vals in (items or {}).items():
                    # 複合鍵「項目@位置」拆解;位置不合法(None)時略過
                    item_name, position = parse_measurement_key(item_key)
                    if item_name not in VALID_ITEMS or position is None:
                        continue
                    v_min    = vals.get('value_min')
                    v_max    = vals.get('value_max')
                    v_single = vals.get('value_single')
                    # 僅在有任一量測值時才建立子表明細
                    if v_min is not None or v_max is not None or v_single is not None:
                        shipping_data.measurements.append(ShippingMeasurement(
                            group_num=g,
                            item=item_name,
                            position=position,
                            lower_limit=vals.get('lower_limit'),
                            upper_limit=vals.get('upper_limit'),
                            value_min=v_min,
                            value_max=v_max,
                            value_single=v_single,
                            is_ng=bool(vals.get('is_ng', False)),
                        ))
```

- [ ] **Step 4: 修改 _map_row_to_dict 回傳**

原 69-71 行的迴圈改為(僅 map 的鍵改用 `build_measurement_key`):

```python
        for m in item.measurements:
            g = str(m.group_num)
            meas_map.setdefault(g, {})[build_measurement_key(m.item, m.position)] = {
```

(dict 內容 `lower_limit`…`is_ng` 六行不變)

- [ ] **Step 5: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_shipping_position_roundtrip.py backend/tests/test_services/test_shipping_cache.py -v`
Expected: 全數 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/shipping_service.py backend/tests/test_services/test_shipping_position_roundtrip.py
git commit -m "出貨檢驗寫入/回傳支援外徑分段複合鍵(項目@位置)"
```

---

### Task 4: Excel 匯出分段資料取三段極值

**Files:**
- Modify: `backend/services/shipping_export.py`
- Test: `backend/tests/test_services/test_shipping_export_utils.py`(追加測試)

- [ ] **Step 1: 撰寫失敗測試**

在 `test_shipping_export_utils.py` 檔尾追加:

```python
def test_build_shipping_export_row_segmented_od_uses_extremes():
    """分段紀錄的外徑欄位取三段整體極值,欄位格式不變"""
    row = {
        "識別碼": 8,
        "檢驗日期": "2026-07-09",
        "材質": "6061",
        "檢驗規格": "10*2",
        "訂單號碼": "SO-2",
        "檢驗人員": "檢驗員A",
        "廠商中文名稱": "廠商A",
        "組數": 1,
        "measurements": {
            "1": {
                "外徑@前段": {"value_min": 9.8, "value_max": 10.1},
                "外徑@中段": {"value_min": 9.9, "value_max": 10.2},
                "外徑@後段": {"value_min": 9.7, "value_max": 10.0},
            },
        },
    }

    export_row = build_shipping_export_row(row, max_groups=1)

    assert export_row["外徑1-最小"] == 9.7
    assert export_row["外徑1-最大"] == 10.2
    # 無資料的欄位維持空字串
    assert export_row["內徑1-最小"] == ""
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest backend/tests/test_services/test_shipping_export_utils.py -v`
Expected: 新測試 FAIL(`外徑1-最小` 為 `""`,因鍵是 `外徑@前段` 對不上 `外徑`)

- [ ] **Step 3: 實作極值 helper 並套用到 minmax 項目**

`backend/services/shipping_export.py` 新增 helper(放在 `_measurement_value` 之後):

```python
def _segmented_minmax(measurements: Mapping[str, Any], group_num: int, item_name: str) -> tuple[Any, Any]:
    """取該組該項目所有段(含未分段)的整體最小/最大值。

    分段資料的鍵為「項目@位置」;未分段即項目名。無資料時回傳空字串。
    """
    group = measurements.get(str(group_num), {}) or {}
    mins: list[Any] = []
    maxs: list[Any] = []
    for key, cell in group.items():
        if not cell or key.split('@', 1)[0] != item_name:
            continue
        if cell.get("value_min") is not None:
            mins.append(cell["value_min"])
        if cell.get("value_max") is not None:
            maxs.append(cell["value_max"])
    return (min(mins) if mins else "", max(maxs) if maxs else "")
```

`build_shipping_export_row` 迴圈內,外徑/內徑/厚度改用極值 helper(單一儲存格時結果與原本相同):

```python
    for group_num in range(1, max_groups + 1):
        od_min, od_max = _segmented_minmax(measurements, group_num, "外徑")
        id_min, id_max = _segmented_minmax(measurements, group_num, "內徑")
        th_min, th_max = _segmented_minmax(measurements, group_num, "厚度")
        export_row[f"外徑{group_num}-最小"] = od_min
        export_row[f"外徑{group_num}-最大"] = od_max
        export_row[f"內徑{group_num}-最小"] = id_min
        export_row[f"內徑{group_num}-最大"] = id_max
        export_row[f"真圓度{group_num}"] = _measurement_value(measurements, group_num, "真圓度", "value_single")
        export_row[f"厚度{group_num}-最小"] = th_min
        export_row[f"厚度{group_num}-最大"] = th_max
        export_row[f"同心度{group_num}"] = _measurement_value(measurements, group_num, "同心度", "value_single")
        export_row[f"長度{group_num}"] = _measurement_value(measurements, group_num, "長度", "value_single")
        export_row[f"硬度{group_num}"] = _measurement_value(measurements, group_num, "硬度", "value_single")
        export_row[f"真直度{group_num}"] = _measurement_value(measurements, group_num, "真直度", "value_single")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest backend/tests/test_services/test_shipping_export_utils.py -v`
Expected: 3 passed(含既有 2 個)

- [ ] **Step 5: Commit**

```bash
git add backend/services/shipping_export.py backend/tests/test_services/test_shipping_export_utils.py
git commit -m "Excel 匯出:分段量測取三段極值填入既有外徑欄位"
```

---

### Task 5: 前端型別擴充與分段工具模組

**Files:**
- Modify: `src_frontend/src/components/shipping/shippingMeasurementUtils.ts:5-10`(ShippingItemConfig)
- Modify: `src_frontend/src/components/shipping/shippingInspectionItems.ts:6`(外徑加 segmentable)
- Create: `src_frontend/src/components/shipping/shippingSegmentUtils.ts`
- Test: `src_frontend/src/components/shipping/shippingSegmentUtils.test.ts`

- [ ] **Step 1: 擴充 ShippingItemConfig 型別**

`shippingMeasurementUtils.ts` 的 interface 改為:

```ts
export interface ShippingItemConfig {
  label: string;
  key: string;
  type: 'minmax' | 'single';
  toleranceKey?: string;
  /** 此項目可啟用前/中/後分段量測 */
  segmentable?: boolean;
  /** 展開後的段位置(前段/中段/後段);未分段列為 undefined */
  position?: string;
  /** 展開後回指原始項目 key(如 外徑@前段 → 外徑) */
  baseKey?: string;
}
```

`shippingInspectionItems.ts` 外徑列改為:

```ts
  { label: '外徑', key: '外徑', type: 'minmax', segmentable: true },
```

- [ ] **Step 2: 撰寫失敗測試**

`src_frontend/src/components/shipping/shippingSegmentUtils.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import {
  buildSegmentKey,
  detectSegmentedKeys,
  expandSegmentedItems,
  hasMidRearSegmentValues,
  remapGroupsOnSegmentToggle,
  SEGMENT_POSITIONS,
} from './shippingSegmentUtils';
import type { ShippingItemConfig } from './shippingMeasurementUtils';

const items: ShippingItemConfig[] = [
  { label: '外徑', key: '外徑', type: 'minmax', segmentable: true },
  { label: '硬度', key: '硬度', type: 'single' },
];

describe('expandSegmentedItems', () => {
  it('未啟用分段時原樣回傳', () => {
    expect(expandSegmentedItems(items, new Set())).toEqual(items);
  });

  it('啟用分段的項目展開為前/中/後三列,公差鍵指回原項目', () => {
    const expanded = expandSegmentedItems(items, new Set(['外徑']));

    expect(expanded).toHaveLength(4);
    expect(expanded[0]).toMatchObject({
      label: '外徑(前)', key: '外徑@前段', toleranceKey: '外徑',
      baseKey: '外徑', position: '前段', type: 'minmax',
    });
    expect(expanded[1].key).toBe('外徑@中段');
    expect(expanded[2].key).toBe('外徑@後段');
    expect(expanded[3].key).toBe('硬度');
  });

  it('未標記 segmentable 的項目即使在集合中也不展開', () => {
    expect(expandSegmentedItems(items, new Set(['硬度']))).toEqual(items);
  });
});

describe('detectSegmentedKeys', () => {
  it('量測資料含「基鍵@」開頭的鍵即視為已分段', () => {
    const result = detectSegmentedKeys(
      { '1': { '外徑@前段': { value_min: 9.8, is_ng: false }, 硬度: { is_ng: false } } },
      items,
    );
    expect(result).toEqual(new Set(['外徑']));
  });

  it('無分段鍵時回傳空集合', () => {
    expect(detectSegmentedKeys({ '1': { 外徑: { is_ng: false } } }, items)).toEqual(new Set());
  });
});

describe('remapGroupsOnSegmentToggle', () => {
  it('開啟分段:單段值搬到前段,中/後段為空', () => {
    const groups = { '1': { 外徑: { value_min: '9.8', value_max: '10.2', is_ng: false }, 硬度: { is_ng: false } } };

    const next = remapGroupsOnSegmentToggle(groups, '外徑', true);

    expect(next['1']['外徑']).toBeUndefined();
    expect(next['1']['外徑@前段']).toEqual({ value_min: '9.8', value_max: '10.2', is_ng: false });
    expect(next['1']['外徑@中段']).toEqual({ is_ng: false });
    expect(next['1']['外徑@後段']).toEqual({ is_ng: false });
    expect(next['1']['硬度']).toEqual({ is_ng: false });
  });

  it('關閉分段:只保留前段值,中/後段捨棄', () => {
    const groups = {
      '1': {
        '外徑@前段': { value_min: '9.8', is_ng: false },
        '外徑@中段': { value_min: '9.9', is_ng: false },
        '外徑@後段': { value_min: '9.7', is_ng: false },
      },
    };

    const next = remapGroupsOnSegmentToggle(groups, '外徑', false);

    expect(next['1']['外徑']).toEqual({ value_min: '9.8', is_ng: false });
    expect(next['1']['外徑@前段']).toBeUndefined();
    expect(next['1']['外徑@中段']).toBeUndefined();
    expect(next['1']['外徑@後段']).toBeUndefined();
  });
});

describe('hasMidRearSegmentValues', () => {
  it('中段或後段有值時回傳 true', () => {
    expect(hasMidRearSegmentValues(
      { '1': { '外徑@中段': { value_min: '9.9', is_ng: false } } }, '外徑',
    )).toBe(true);
  });

  it('僅前段有值時回傳 false', () => {
    expect(hasMidRearSegmentValues(
      { '1': { '外徑@前段': { value_min: '9.8', is_ng: false }, '外徑@中段': { is_ng: false } } }, '外徑',
    )).toBe(false);
  });
});

describe('buildSegmentKey', () => {
  it('組出複合鍵', () => {
    expect(SEGMENT_POSITIONS).toEqual(['前段', '中段', '後段']);
    expect(buildSegmentKey('外徑', '前段')).toBe('外徑@前段');
  });
});
```

- [ ] **Step 3: 執行測試確認失敗**

Run(於 `src_frontend/`): `npx vitest run src/components/shipping/shippingSegmentUtils.test.ts`
Expected: FAIL(找不到模組 shippingSegmentUtils)

- [ ] **Step 4: 實作 shippingSegmentUtils.ts**

```ts
import type { ShippingGroupMeasurements, ShippingItemConfig } from './shippingMeasurementUtils';

export const SEGMENT_POSITIONS = ['前段', '中段', '後段'] as const;
export type SegmentPosition = (typeof SEGMENT_POSITIONS)[number];

const SEGMENT_SHORT_LABELS: Record<SegmentPosition, string> = {
  前段: '前',
  中段: '中',
  後段: '後',
};

/** 組出複合鍵「基鍵@位置」(與後端 shipping_measurement_keys 對應) */
export const buildSegmentKey = (baseKey: string, position: SegmentPosition) => `${baseKey}@${position}`;

/** 將啟用分段的項目展開為前/中/後三列;其餘項目原樣保留 */
export const expandSegmentedItems = (
  items: ShippingItemConfig[],
  segmentedKeys: Set<string>,
): ShippingItemConfig[] =>
  items.flatMap(item => {
    if (!item.segmentable || !segmentedKeys.has(item.key)) return [item];
    return SEGMENT_POSITIONS.map(position => ({
      ...item,
      key: buildSegmentKey(item.key, position),
      label: `${item.label}(${SEGMENT_SHORT_LABELS[position]})`,
      toleranceKey: item.toleranceKey ?? item.key,
      baseKey: item.key,
      position,
    }));
  });

/** 從已載入的量測資料偵測哪些可分段項目已啟用分段(存在「基鍵@」開頭的鍵) */
export const detectSegmentedKeys = (
  measurements: Record<string, ShippingGroupMeasurements>,
  items: ShippingItemConfig[],
): Set<string> => {
  const segmentableKeys = new Set(items.filter(i => i.segmentable).map(i => i.key));
  const found = new Set<string>();
  for (const groupData of Object.values(measurements ?? {})) {
    for (const key of Object.keys(groupData ?? {})) {
      const [base, position] = key.split('@');
      if (position && segmentableKeys.has(base)) found.add(base);
    }
  }
  return found;
};

/** 分段的中段/後段已有量測值時回傳 true(關閉分段前需使用者確認) */
export const hasMidRearSegmentValues = (
  groups: Record<string, ShippingGroupMeasurements>,
  baseKey: string,
): boolean =>
  Object.values(groups).some(groupData =>
    (['中段', '後段'] as const).some(pos => {
      const meas = groupData[buildSegmentKey(baseKey, pos)];
      return meas != null && (meas.value_min != null || meas.value_max != null);
    }),
  );

/** 切換分段時搬移量測值:開啟時單段值搬到前段;關閉時只保留前段值 */
export const remapGroupsOnSegmentToggle = (
  groups: Record<string, ShippingGroupMeasurements>,
  baseKey: string,
  enable: boolean,
): Record<string, ShippingGroupMeasurements> =>
  Object.fromEntries(
    Object.entries(groups).map(([gKey, groupData]) => {
      const next = { ...groupData };
      if (enable) {
        const single = next[baseKey];
        delete next[baseKey];
        next[buildSegmentKey(baseKey, '前段')] = single ?? { is_ng: false };
        next[buildSegmentKey(baseKey, '中段')] = { is_ng: false };
        next[buildSegmentKey(baseKey, '後段')] = { is_ng: false };
      } else {
        const front = next[buildSegmentKey(baseKey, '前段')];
        for (const pos of SEGMENT_POSITIONS) delete next[buildSegmentKey(baseKey, pos)];
        next[baseKey] = front ?? { is_ng: false };
      }
      return [gKey, next];
    }),
  );
```

- [ ] **Step 5: 執行測試確認通過**

Run: `npx vitest run src/components/shipping/shippingSegmentUtils.test.ts`
Expected: 全數 PASS

- [ ] **Step 6: 執行既有 shipping 前端測試確認無迴歸**

Run: `npx vitest run src/components/shipping`
Expected: 全數 PASS(型別為選填欄位,不影響既有測試)

- [ ] **Step 7: Commit**

```bash
git add src_frontend/src/components/shipping/shippingMeasurementUtils.ts src_frontend/src/components/shipping/shippingInspectionItems.ts src_frontend/src/components/shipping/shippingSegmentUtils.ts src_frontend/src/components/shipping/shippingSegmentUtils.test.ts
git commit -m "前端新增分段量測工具模組與通用 segmentable 設定"
```

---

### Task 6: 量測表格加分段切換 switch

**Files:**
- Modify: `src_frontend/src/components/shipping/ShippingMeasurementTable.tsx`
- Test: `src_frontend/src/components/shipping/ShippingMeasurementTable.test.tsx`

- [ ] **Step 1: 撰寫失敗測試**

在 `ShippingMeasurementTable.test.tsx` 追加(既有兩個測試的 render 也需補上 `onToggleSegment={vi.fn()}`):

```tsx
  it('可分段項目顯示切換 switch 並回報基鍵', () => {
    const onToggleSegment = vi.fn();
    render(
      <ShippingMeasurementTable
        items={[{ label: '外徑', key: '外徑', type: 'minmax' as const, segmentable: true }]}
        groupKeys={['1']}
        groups={{ '1': {} }}
        itemOffsets={[0]}
        totalInputsPerGroup={2}
        fieldErrors={{}}
        violations={{}}
        onMeasurementChange={vi.fn()}
        onAddGroup={vi.fn()}
        onRemoveGroup={vi.fn()}
        onToggleSegment={onToggleSegment}
      />,
    );

    fireEvent.click(screen.getByTitle('分段量測(前/中/後)'));
    expect(onToggleSegment).toHaveBeenCalledWith('外徑');
  });

  it('分段展開後 switch 僅出現在前段列且為勾選狀態', () => {
    const segItems = [
      { label: '外徑(前)', key: '外徑@前段', type: 'minmax' as const, segmentable: true, baseKey: '外徑', position: '前段' },
      { label: '外徑(中)', key: '外徑@中段', type: 'minmax' as const, segmentable: true, baseKey: '外徑', position: '中段' },
      { label: '外徑(後)', key: '外徑@後段', type: 'minmax' as const, segmentable: true, baseKey: '外徑', position: '後段' },
    ];
    render(
      <ShippingMeasurementTable
        items={segItems}
        groupKeys={['1']}
        groups={{ '1': {} }}
        itemOffsets={[0, 2, 4]}
        totalInputsPerGroup={6}
        fieldErrors={{}}
        violations={{}}
        onMeasurementChange={vi.fn()}
        onAddGroup={vi.fn()}
        onRemoveGroup={vi.fn()}
        onToggleSegment={vi.fn()}
      />,
    );

    const switches = screen.getAllByTitle('分段量測(前/中/後)');
    expect(switches).toHaveLength(1);
    expect(switches[0]).toBeChecked();
  });
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `npx vitest run src/components/shipping/ShippingMeasurementTable.test.tsx`
Expected: 新測試 FAIL(TS 編譯錯誤:不存在 onToggleSegment prop)

- [ ] **Step 3: 實作 switch UI**

`ShippingMeasurementTable.tsx`:

Props interface 加一行:

```ts
    onToggleSegment: (baseKey: string) => void;
```

元件參數解構加 `onToggleSegment`。項目標題格(原 76 行)改為:

```tsx
                            <th className="bg-light text-nowrap">
                                <div className="d-flex align-items-center justify-content-between gap-1">
                                    <span>{item.label}</span>
                                    {item.segmentable && (!item.position || item.position === '前段') && (
                                        <Form.Check
                                            type="switch"
                                            id={`segment-switch-${item.baseKey ?? item.key}`}
                                            title="分段量測(前/中/後)"
                                            checked={Boolean(item.position)}
                                            onChange={() => onToggleSegment(item.baseKey ?? item.key)}
                                        />
                                    )}
                                </div>
                            </th>
```

- [ ] **Step 4: 執行測試確認通過**

Run: `npx vitest run src/components/shipping/ShippingMeasurementTable.test.tsx`
Expected: 4 passed(既有 2 + 新增 2)

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/shipping/ShippingMeasurementTable.tsx src_frontend/src/components/shipping/ShippingMeasurementTable.test.tsx
git commit -m "量測表格:可分段項目加前/中/後切換 switch"
```

---

### Task 7: ShippingModal 整合分段狀態

**Files:**
- Modify: `src_frontend/src/components/shipping/ShippingModal.tsx`
- Test: `src_frontend/src/components/shipping/ShippingModal.test.tsx`

- [ ] **Step 1: 撰寫失敗測試**

`ShippingModal.test.tsx` 修改:`useShippingDetail` mock 改為可變變數,並追加載入偵測測試。

mock 區(原 29-36 行)改為:

```tsx
let shippingDetail: Record<string, unknown> | null = null;

vi.mock('../../hooks/useShipping', () => ({
  useInspectors: () => ({ data: [{ id: 1, name: '檢驗員A' }] }),
  useVendors: () => ({ data: [{ id: 10, name: '廠商A' }] }),
  useShippingDetail: () => ({ data: shippingDetail, isLoading: false }),
  useCreateShipping: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateShipping: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCheckTolerance: () => ({ mutateAsync: checkToleranceMutate }),
}));
```

`beforeEach` 加 `shippingDetail = null;`。describe 內追加:

```tsx
  it('載入含分段鍵的紀錄時自動展開外徑三列', async () => {
    shippingDetail = {
      識別碼: 5,
      檢驗日期: '2026-07-01',
      檢驗人員: '檢驗員A',
      廠商中文名稱: '廠商A',
      材質: 'A6061',
      檢驗規格: '10*2',
      組數: 1,
      measurements: {
        '1': {
          '外徑@前段': { value_min: 9.8, value_max: 10.1, is_ng: false },
          '外徑@中段': { value_min: 9.9, value_max: 10.2, is_ng: false },
          '外徑@後段': { value_min: 9.7, value_max: 10.0, is_ng: false },
        },
      },
    };

    render(
      <ShippingModal show editId={5} handleClose={() => undefined} onSuccess={() => undefined} />,
    );

    await waitFor(() => expect(screen.getByText('外徑(前)')).toBeInTheDocument());
    expect(screen.getByText('外徑(中)')).toBeInTheDocument();
    expect(screen.getByText('外徑(後)')).toBeInTheDocument();
    expect(screen.getByDisplayValue('9.9')).toBeInTheDocument();
  });
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `npx vitest run src/components/shipping/ShippingModal.test.tsx`
Expected: 新測試 FAIL(找不到「外徑(前)」;另因 Task 6 已加必填 prop,Modal 未傳 onToggleSegment 會有 TS 錯誤——本步驟一併確認)

- [ ] **Step 3: 實作 Modal 整合**

`ShippingModal.tsx` 修改點:

(a) import 加:

```tsx
import {
    detectSegmentedKeys,
    expandSegmentedItems,
    hasMidRearSegmentValues,
    remapGroupsOnSegmentToggle,
} from './shippingSegmentUtils';
```

(b) state 區(65 行附近)加:

```tsx
    // 已啟用分段量測的項目基鍵(如 '外徑')
    const [segmentedKeys, setSegmentedKeys] = useState<Set<string>>(new Set());
```

(c) `ITEMS` useMemo(76 行)之後加展開後清單,並將後續所有使用點改用 `ACTIVE_ITEMS`:

```tsx
    // 依分段狀態展開後的實際渲染項目清單
    const ACTIVE_ITEMS = useMemo(() => expandSegmentedItems(ITEMS, segmentedKeys), [ITEMS, segmentedKeys]);
```

使用點逐一替換:
- tab offsets useMemo(80 行):`getShippingItemInputOffsets(ACTIVE_ITEMS)`,依賴改 `[ACTIVE_ITEMS]`
- 違規偵測 effect(199 行):`items: ACTIVE_ITEMS`,依賴改 `[groups, tolerance, spec, ACTIVE_ITEMS]`
- `addGroup`(239 行):`emptyShippingGroup(ACTIVE_ITEMS)`
- `handleSubmit` 的 `validateShippingForm` 與 `buildShippingPayload`(259、281 行):`items: ACTIVE_ITEMS`
- `<ShippingMeasurementTable items={ACTIVE_ITEMS} ...>`(373 行)

(d) `resetForm`(84 行)內加:

```tsx
        setSegmentedKeys(new Set());
```

(e) 載入編輯資料 effect:`setGroups(loaded);`(130 行)之前加:

```tsx
                setSegmentedKeys(detectSegmentedKeys(nested, BASE_SHIPPING_ITEMS));
```

(f) 廠商變更 effect(141 行)的 `setGroups(...)` 前加:

```tsx
            setSegmentedKeys(new Set());
```

(g) `removeGroup` 之後加切換 handler:

```tsx
    /** 切換項目的分段量測模式(開啟:單段值搬到前段;關閉:只保留前段) */
    const toggleSegment = (baseKey: string) => {
        const enabled = segmentedKeys.has(baseKey);
        if (enabled && hasMidRearSegmentValues(groups, baseKey)) {
            if (!window.confirm('關閉分段後將只保留前段數據,確定要關閉嗎?')) return;
        }
        setGroups(prev => remapGroupsOnSegmentToggle(prev, baseKey, !enabled));
        setSegmentedKeys(prev => {
            const next = new Set(prev);
            if (enabled) next.delete(baseKey);
            else next.add(baseKey);
            return next;
        });
    };
```

(h) 表格加 prop:

```tsx
                            onToggleSegment={toggleSegment}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `npx vitest run src/components/shipping/ShippingModal.test.tsx`
Expected: 2 passed

- [ ] **Step 5: 手動驗證切換行為(dev server)**

於 `src_frontend/` 執行 `npm run dev`,後端 venv 啟動 `python backend/app.py`(或依專案慣例)。開啟出貨檢驗 → 新增紀錄:
1. 外徑列顯示 switch,輸入外徑 Min 後開啟 → 值出現在「外徑(前)」,中/後為空
2. 在中段輸入值後關閉 switch → 出現確認對話框;確認後只剩前段值的單列
3. 儲存分段紀錄後重新編輯 → 自動展開三列且值正確

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/components/shipping/ShippingModal.tsx src_frontend/src/components/shipping/ShippingModal.test.tsx
git commit -m "出貨檢驗表單整合外徑分段量測切換與載入偵測"
```

---

### Task 8: 列表頁違規偵測支援複合鍵

**Files:**
- Modify: `src_frontend/src/components/shipping/shippingViolationUtils.ts:27-49`
- Test: `src_frontend/src/components/shipping/shippingViolationUtils.test.ts`(追加測試)

- [ ] **Step 1: 撰寫失敗測試**

`shippingViolationUtils.test.ts` 追加:

```ts
  it('分段複合鍵套用基礎項目公差判定 NG', () => {
    const result = evaluateShippingViolation({
      ...baseInspection,
      measurements: {
        '1': {
          '外徑@中段': { value_min: 8.9, value_max: 9.5, is_ng: false },
        },
      },
    } as ShippingInspection, {
      '6061|||10mm|||A廠': {
        外徑: { lsl: 9, usl: 10 },
      },
    });

    expect(result).toEqual({ found: true, hasViolation: true });
  });

  it('分段量測皆在公差內時判合格', () => {
    const result = evaluateShippingViolation({
      ...baseInspection,
      measurements: {
        '1': {
          '外徑@前段': { value_min: 9.2, value_max: 9.8, is_ng: false },
          '外徑@後段': { value_min: 9.1, value_max: 9.9, is_ng: false },
        },
      },
    } as ShippingInspection, {
      '6061|||10mm|||A廠': {
        外徑: { lsl: 9, usl: 10 },
      },
    });

    expect(result).toEqual({ found: true, hasViolation: false });
  });
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `npx vitest run src/components/shipping/shippingViolationUtils.test.ts`
Expected: 第一個新測試 FAIL(`外徑@中段` 不在 ALL_ITEMS,被略過而判合格)

- [ ] **Step 3: 改寫比對迴圈**

`shippingViolationUtils.ts`:`ALL_ITEMS` 改為 Set,迴圈改為以量測資料的鍵驅動、拆出基礎項目名比對公差:

```ts
const MINMAX_ITEMS = new Set(['外徑', '內徑', '厚度']);
const ALL_ITEMS = new Set(['外徑', '內徑', '真圓度', '厚度', '同心度', '長度', '硬度', '真直度', '韋伯氏硬度']);
```

`evaluateShippingViolation` 內層迴圈(原 28-48 行)改為:

```ts
    if (item.measurements && Object.keys(item.measurements).length > 0) {
        for (const groupData of Object.values(item.measurements)) {
            for (const [measKey, measItem] of Object.entries(groupData)) {
                // 分段複合鍵(如 外徑@中段)以基礎項目名比對公差
                const itemName = measKey.split('@')[0];
                if (!ALL_ITEMS.has(itemName) || !measItem) continue;
                const tol = std[itemName];
                if (!tol) continue;

                if (MINMAX_ITEMS.has(itemName)) {
                    if (isMeasurementOutOfTolerance(measItem.value_min, tol)) {
                        return { hasViolation: true, found: true };
                    }
                    if (isMeasurementOutOfTolerance(measItem.value_max, tol)) {
                        return { hasViolation: true, found: true };
                    }
                } else {
                    if (isMeasurementOutOfTolerance(measItem.value_single, tol)) {
                        return { hasViolation: true, found: true };
                    }
                }
            }
        }
    }
```

- [ ] **Step 4: 執行測試確認通過**

Run: `npx vitest run src/components/shipping/shippingViolationUtils.test.ts`
Expected: 5 passed(既有 3 + 新增 2)

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/components/shipping/shippingViolationUtils.ts src_frontend/src/components/shipping/shippingViolationUtils.test.ts
git commit -m "列表違規偵測:分段複合鍵套用基礎項目公差"
```

---

### Task 9: 全量驗證

**Files:** 無新增(驗證與收尾)

- [ ] **Step 1: 後端全套測試**

Run(repo 根目錄): `python -m pytest backend/tests/ -q`
Expected: 全數通過

- [ ] **Step 2: 前端全套測試 + lint + build**

Run(於 `src_frontend/`):

```bash
npm test
npm run lint
npm run build
```

Expected: 測試全過、lint 無錯誤、tsc + vite build 成功

- [ ] **Step 3: 修正發現的問題並 commit**

若上述任一步驟失敗,修正後重跑;全部通過後若有未提交的修正:

```bash
git add -A
git commit -m "修正外徑分段量測整合的迴歸問題"
```

(無問題則略過此 commit)

---

## Spec 對照檢查

| 規格章節 | 對應任務 |
|----------|----------|
| 1. 資料層(位置欄位、唯一鍵、migration) | Task 2 |
| 2. API 複合鍵格式(解析/組回) | Task 1、3 |
| 3. 前端通用 config 與展開函式 | Task 5 |
| 4. 表格 switch 與切換行為、載入偵測 | Task 6、7 |
| 5. 違規偵測(表單內走 toleranceKey 既有機制;列表複合鍵) | Task 5(toleranceKey)、8 |
| 6. 匯出取三段極值;compute_is_ng/SPC/匯入不動 | Task 4(匯出);其餘由 Task 3 round-trip 測試佐證 item 欄位乾淨 |
| 7. 測試範圍 | 各任務 TDD 步驟 + Task 9 全量驗證 |
