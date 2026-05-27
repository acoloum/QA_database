# QMS 系統優化設計規格
日期：2026-05-27  
範圍：高優先級 + 中優先級改善項目

---

## 背景

系統目前處於開發階段，尚未上線。本次優化目標為在正式上線前完成架構層面的技術債清理，同時補齊專業 QMS 系統所需的功能模組。

---

## 子專案 A — 快速改善

### A1. DB 複合索引

新增以下索引，改善常用查詢效能：

| 表格 | 索引欄位 | 用途 |
|------|---------|------|
| 不合格品單 | `(status, date)` | 狀態篩選 + 日期排序 |
| 異常矯正單 | `(source_type, source_id)` | 來源關聯查詢 |
| 異常矯正單 | `(status, d0_deadline)` | 逾期警示查詢 |
| 重工申請單 | `(status, created_at)` | 狀態統計 |
| 客訴紀錄 | `(is_repeat, complaint_date)` | 重複客訴報表 |

透過 `__table_args__` 在 `models.py` 定義，Flask-Migrate 產生遷移腳本。

### A2. 統一 API 回傳格式

在 `backend/utils.py` 新增 `api_success` / `api_error` helper：

```python
def api_success(data=None, message="操作成功", code=200):
    return jsonify({"success": True, "data": data, "message": message}), code

def api_error(message, code=400, detail=None):
    return jsonify({"success": False, "error": message, "detail": detail}), code
```

所有路由逐步切換至此格式（本次優化範圍內的新路由強制使用，現有路由不強制改，避免影響前端）。

### A3. N+1 查詢修正

以下 service 的列表查詢改用 `joinedload` 預載入關聯：

- `shipping_service.py` — 預載 `inspector`、`vendor`
- `patrol_service.py` — 預載 `inspector`
- `ncmr_service.py` — 預載 `inspector`
- `complaint_service.py` — 預載 `creator`

---

## 子專案 B — NCMR→CAPA→重工 狀態機 + 軟刪除

### B1. 狀態轉移規則

各模組合法狀態轉移（代碼層強制）：

**NCMR：**
```
新建 → 處理中 → 已驗證 → 已結案
新建 → 已結案（直接結案，無需 CAPA）
```

**CAPA：**
```
進行中 → 已結案
```

**重工申請單：**
```
申請中 → 執行中 → 已完成 → 已結案
申請中 → 撤銷
```

實作：`backend/utils.py` 新增 `validate_status_transition(model_name, current, new)` 函數；各 service update 方法呼叫此函數，非法轉移拋出 `ValueError`。

### B2. 跨模組自動同步

| 觸發事件 | 自動動作 |
|---------|---------|
| NCMR 開立 CAPA | NCMR.status → 處理中 |
| CAPA 結案 | 若來源為 NCMR，NCMR.status → 已驗證 |
| 重工完成（無關聯CAPA）| 關聯 NCMR.status → 已驗證 |
| NCMR 手動結案 | 檢查關聯 CAPA/重工是否皆完成，否則拋錯 |

同步邏輯集中於各 service 層，不在路由層處理。

### B3. 軟刪除

在 `models.py` 新增抽象基底類別：

```python
class SoftDeleteMixin:
    deleted_at = db.Column('刪除時間', db.DateTime, nullable=True, index=True)

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
```

套用範圍：`NCMR`、`CorrectiveAction`、`ReworkRequest`、`CustomerComplaint`。

所有 service 的查詢自動加上 `.filter(Model.deleted_at.is_(None))`，DELETE 路由改為呼叫 `soft_delete()`。

---

## 子專案 D — ShippingData 表重構

### D1. 新資料表設計

#### 出貨巡檢主檔（ShippingData，重構現有表）

保留現有欄位，移除所有動態量測欄位（od1_min ~ od10_5 等），新增：
- `group_count` — 實際量測組數（Integer）

#### 出貨巡檢量測明細（ShippingMeasurement，新增）

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| shipping_id | Integer FK | 關聯主檔 |
| group_num | Integer | 組別（1-N，動態） |
| item | String(20) | 量測項目：od/id/thickness/concentricity/length/hardness/roundness |
| lower_limit | Numeric(10,4) | 下限 |
| upper_limit | Numeric(10,4) | 上限 |
| sample_1~5 | Numeric(10,4) | 樣本值（允許 NULL）|
| is_ng | Boolean | 本組本項是否超規 |

索引：`(shipping_id, group_num, item)` 唯一複合索引。

#### SPC 快取（SPCCache，新增）

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| cache_key | String(255) unique | 由 material+spec+item+date_range 組成 |
| result | JSONB | Cpk、XBar、R 等計算結果 |
| created_at | DateTime | |
| expires_at | DateTime | 預設建立後 1 小時過期 |

### D2. API 回傳格式（維持相容）

後端將 `ShippingMeasurement` 明細重組為現有巡檢頁面預期的巢狀格式：

```json
{
  "measurements": {
    "1": {
      "od":  {"lower": 40.00, "upper": 40.10, "samples": [40.02, 40.03, null, null, null], "is_ng": false},
      "id":  {"lower": 35.00, "upper": 35.08, "samples": [35.04, 35.05, null, null, null], "is_ng": false}
    },
    "2": { ... }
  }
}
```

前端接收格式不變，僅 shipping_service.py 內部重構。

### D3. 前端表單動態組數

**新增量測組：** 表單底部「＋ 新增量測組」按鈕，每按一次新增一組量測行。  
**刪除量測組：** 每組右上角「✕」按鈕刪除該組。  
**組別上限：** 不設上限（由使用者自行決定）。  
**量測項目：** 每組固定顯示：外徑、內徑、厚度、同心度、長度、硬度、圓度（可留空）。

### D4. 遷移策略

1. 建立 `ShippingMeasurement` 和 `SPCCache` 新表
2. 執行資料遷移腳本：讀取舊表 od1_1~od10_5 等欄位，轉換插入明細表
3. 舊量測欄位以 Flask-Migrate DROP COLUMN 移除
4. shipping_service.py 切換查詢邏輯
5. SPC 計算改從明細表聚合

---

## 子專案 C — 廠商績效模組

### C1. 新資料表

#### 廠商績效（VendorPerformance）

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| vendor_id | Integer FK | 關聯廠商資料 |
| period | String(7) | 格式：YYYY-MM |
| inspection_count | Integer | 檢驗批次數 |
| defect_count | Integer | 不良批次數（is_ng=True）|
| defect_rate | Float | 缺陷率（%）|
| capa_count | Integer | CAPA 件數 |
| avg_capa_days | Float | 平均 CAPA 結案天數 |
| complaint_count | Integer | 客訴件數 |
| score | Float | 績效評分（0-100）|
| calculated_at | DateTime | 計算時間戳 |

唯一約束：`(vendor_id, period)`。

### C2. 評分公式

```
score = 100
  - min(defect_rate * 2, 40)      # 最多扣 40 分
  - min(avg_capa_days * 1, 30)    # 最多扣 30 分
  - min(complaint_count * 5, 30)  # 最多扣 30 分
score = max(score, 0)
```

### C3. 前端新頁面

路由：`/vendor-performance`

- **頁頭**：月份選擇器（預設當月）
- **表格**：廠商名稱、評分（色碼：≥80綠/60-79黃/<60紅）、缺陷率、CAPA件數、客訴件數
- **點擊廠商**：展開趨勢圖（折線圖，最近 6 個月評分走勢）
- **計算時機**：進入頁面或切換月份時即時計算，結果存入 `VendorPerformance` 表快取

---

## 子專案 E — 角色系統 + 操作審計日誌

### E1. 角色定義

| 角色代碼 | 名稱 | 說明 |
|---------|------|------|
| `inspector` | 檢驗員 | 建立/編輯自己的巡檢、NCMR；查看 CAPA、重工 |
| `qa_supervisor` | QA主管 | 上述全部 + 審核重工、開立CAPA、編輯客訴 |
| `qc_manager` | 品管經理 | 全部操作 + 結案CAPA、管理廠商、查看報表 |
| `admin` | 系統管理員 | 使用者管理、系統設定（維持現有）|

### E2. 新增資料表

#### 角色（Role）

| 欄位 | 類型 |
|------|------|
| id | Integer PK |
| code | String(30) unique |
| name | String(50) |
| permissions | JSONB |

範例 permissions：
```json
{
  "ncmr.create": true,
  "ncmr.delete": false,
  "capa.close": false,
  "rework.approve": false,
  "vendor.manage": false
}
```

#### 操作審計日誌（AuditLog）

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| user_id | Integer FK | |
| action | String(20) | create / update / delete |
| module | String(30) | NCMR / CAPA / 重工 / 客訴… |
| record_id | Integer | 被操作的資料 id |
| old_value | JSONB | 操作前快照（update/delete 時填入）|
| new_value | JSONB | 操作後快照（create/update 時填入）|
| created_at | DateTime | |

索引：`(module, record_id)`、`(user_id, created_at)`。

### E3. 後端實作

`backend/utils.py` 新增：

```python
def require_permission(perm: str):
    """裝飾器：檢查當前用戶是否具備指定權限"""
    def decorator(f):
        @wraps(f)
        @token_required
        def wrapped(current_user, *args, **kwargs):
            role = Role.query.filter_by(code=current_user.role_code).first()
            if not role or not role.permissions.get(perm):
                return api_error("權限不足", 403)
            return f(current_user, *args, **kwargs)
        return wrapped
    return decorator

def log_audit(user_id, action, module, record_id, old_val=None, new_val=None):
    """寫入操作審計日誌"""
    entry = AuditLog(
        user_id=user_id, action=action, module=module,
        record_id=record_id, old_value=old_val, new_value=new_val
    )
    db.session.add(entry)
```

審計日誌在各 service 的 create/update/delete 方法中呼叫 `log_audit()`。

### E4. 前端調整

- `User` 型別新增 `role: string` 欄位（現有）→ 改為 `role_code: string`
- `AuthContext` 新增 `hasPermission(perm: string): boolean` 方法
- 各頁面按鈕依 `hasPermission` 顯示/隱藏（不是刪除 DOM，是 `disabled` + 隱藏）
- 現有使用者管理頁新增「指派角色」下拉選單

---

## 實施順序

```
A（1-2天）→ B（2-3天）→ D（3-5天）→ C（2-3天）→ E（3-4天）
```

A 先做因為修正基礎問題；D 先於 C 因為廠商績效報表依賴重構後的 ShippingData。

## 不在本次範圍

- API 版本控制（/api/v1/）
- Redis 快取
- Docker 安全加固
- 自動 email 通知
- Marshmallow schema 驗證
