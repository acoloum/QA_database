# 機械性質檢驗獨立追溯編號實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將機械性質檢驗的「擠製編號／爐具編號成對批次」改為「擠製編號」與「T4爐號」兩份互不配對的有序清單，同時安全搬移既有資料並保留舊 `batches` API 的過渡相容性。

**Architecture:** 沿用 routes → services → models 三層架構。資料庫以單一 `機械性質追溯編號` 子表儲存兩種受控類型，service 統一負責新版／舊版 payload 正規化、資料庫寫入與新舊 response 序列化；前端只使用新版兩清單契約，並以獨立面板元件處理新增、刪除、重新編號與可存取的重複值錯誤。

**Tech Stack:** Flask 3.1、SQLAlchemy、PostgreSQL 16（單元測試使用 SQLite in-memory）、React 19、TypeScript、React Bootstrap、TanStack React Query、Vitest、Testing Library。

**參考 spec：** `docs/superpowers/specs/2026-07-23-mechanical-independent-trace-numbers-design.md`

## 全域約束

- 保留中文資料表與欄位命名；本次把舊稱「爐具編號」在新版資料模型、API 與畫面統一為「T4爐號」。
- `擠製編號` 與 `T4爐號` 僅是同一主檔下的兩份清單，不建立、推論或顯示彼此配對。
- 同一類型內以 `trim` 後的精確字串判斷重複，大小寫不同視為不同值。
- 新版 create/update payload 必須同時含 `extrusion_numbers`、`t4_furnace_numbers`；兩者皆可為空陣列。
- 過渡期只接受「完整新版」或「單獨舊 `batches`」；混用一律回傳 400。
- detail 過渡期保留 deprecated `batches`，但每列只能有一種編號，絕不重新配對。
- Migration 42 要在單一 transaction 內完成，雙向集合與筆數核對成功後才能刪除舊表。
- 不修改機械量測、規格快照、NG 判定、排除統計及權限流程。
- 不加入 `.codex-remote-attachments/`，也不碰工作區中與本功能無關的既有變更。

---

## Task 1：以測試鎖定新 ORM 與 Migration 42 安全契約

**Files:**

- Modify: `backend/models.py`
- Modify: `backend/tests/test_services/test_mechanical_models.py`
- Create: `backend/migration/42_split_mechanical_trace_numbers.sql`
- Create: `backend/tests/test_migration_42.py`

- [ ] **Step 1：先把模型測試改成獨立追溯編號，確認會失敗**

將舊 `MechanicalBatch` 測試改為匯入尚不存在的 `MechanicalTraceNumber`，至少覆蓋級聯刪除、兩個唯一鍵、類型／序號／編號 check constraint 與欄位長度：

```python
import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import MechanicalTest, MechanicalTraceNumber


def test_create_mechanical_test_with_independent_trace_numbers(db_session):
    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.trace_numbers.extend([
        MechanicalTraceNumber(trace_type="擠製編號", seq=1, number="E001"),
        MechanicalTraceNumber(trace_type="T4爐號", seq=1, number="T4-01"),
        MechanicalTraceNumber(trace_type="T4爐號", seq=2, number="T4-02"),
    ])
    db_session.add(test)
    db_session.commit()

    loaded = db_session.get(MechanicalTest, test.id)
    rows = sorted(
        loaded.trace_numbers,
        key=lambda row: (row.trace_type == "T4爐號", row.seq),
    )
    assert [(row.trace_type, row.seq, row.number) for row in rows] == [
        ("擠製編號", 1, "E001"),
        ("T4爐號", 1, "T4-01"),
        ("T4爐號", 2, "T4-02"),
    ]

    db_session.delete(loaded)
    db_session.commit()
    assert db_session.query(MechanicalTraceNumber).count() == 0


@pytest.mark.parametrize(
    ("rows", "expected_constraint"),
    [
        (
            [
                ("擠製編號", 1, "E001"),
                ("擠製編號", 1, "E002"),
            ],
            "uq_mech_trace_seq",
        ),
        (
            [
                ("T4爐號", 1, "T4-01"),
                ("T4爐號", 2, "T4-01"),
            ],
            "uq_mech_trace_value",
        ),
    ],
)
def test_trace_number_unique_constraints(db_session, rows, expected_constraint):
    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.trace_numbers.extend([
        MechanicalTraceNumber(trace_type=trace_type, seq=seq, number=number)
        for trace_type, seq, number in rows
    ])
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert expected_constraint in {
        constraint.name
        for constraint in MechanicalTraceNumber.__table__.constraints
        if constraint.name
    }


def test_trace_number_schema_contract():
    constraints = {
        constraint.name
        for constraint in MechanicalTraceNumber.__table__.constraints
        if constraint.name
    }
    assert {
        "uq_mech_trace_seq",
        "uq_mech_trace_value",
        "ck_mech_trace_type",
        "ck_mech_trace_seq_positive",
        "ck_mech_trace_number",
    }.issubset(constraints)
    assert MechanicalTraceNumber.trace_type.type.length == 20
    assert MechanicalTraceNumber.number.type.length == 100


@pytest.mark.parametrize(
    ("trace_type", "seq", "number"),
    [
        ("其他編號", 1, "X001"),
        ("擠製編號", 0, "E001"),
        ("T4爐號", 1, "   "),
    ],
)
def test_trace_number_check_constraints(
    db_session, trace_type, seq, number
):
    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.trace_numbers.append(
        MechanicalTraceNumber(
            trace_type=trace_type,
            seq=seq,
            number=number,
        )
    )
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Step 2：執行窄測試，確認因新模型不存在而失敗**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_mechanical_models.py -q
```

Expected: collection 階段出現 `ImportError: cannot import name 'MechanicalTraceNumber'`。

- [ ] **Step 3：實作新 ORM，移除舊配對關聯**

在 `MechanicalTest` 把 `batches` 換成：

```python
trace_numbers = db.relationship(
    "MechanicalTraceNumber",
    backref="test",
    cascade="all, delete-orphan",
    order_by="MechanicalTraceNumber.trace_type, MechanicalTraceNumber.seq",
)
```

以新模型取代 `MechanicalBatch`：

```python
class MechanicalTraceNumber(db.Model):
    """機械性質追溯編號；兩種類型各自排序，不保存彼此配對。"""

    __tablename__ = "機械性質追溯編號"
    __table_args__ = (
        db.UniqueConstraint(
            "機械性質檢驗_ID", "類型", "序號", name="uq_mech_trace_seq"
        ),
        db.UniqueConstraint(
            "機械性質檢驗_ID", "類型", "編號", name="uq_mech_trace_value"
        ),
        db.CheckConstraint(
            "\"類型\" IN ('擠製編號', 'T4爐號')",
            name="ck_mech_trace_type",
        ),
        db.CheckConstraint("\"序號\" >= 1", name="ck_mech_trace_seq_positive"),
        db.CheckConstraint(
            "length(trim(\"編號\")) BETWEEN 1 AND 100",
            name="ck_mech_trace_number",
        ),
        db.Index("ix_mech_trace_test_id", "機械性質檢驗_ID"),
    )

    id = db.Column("識別碼", db.Integer, primary_key=True)
    test_id = db.Column(
        "機械性質檢驗_ID",
        db.Integer,
        db.ForeignKey("機械性質檢驗.識別碼", ondelete="CASCADE"),
        nullable=False,
    )
    trace_type = db.Column("類型", db.String(20), nullable=False)
    seq = db.Column("序號", db.Integer, nullable=False)
    number = db.Column("編號", db.String(100), nullable=False)
```

- [ ] **Step 4：先寫 Migration 42 靜態安全測試**

Create `backend/tests/test_migration_42.py`：

```python
"""機械性質 migration 42 的安全搬移契約測試。"""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migration"
    / "42_split_mechanical_trace_numbers.sql"
)


def test_migration_42_has_state_guards_and_transaction():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "to_regclass" in sql
    assert "新舊追溯編號資料表同時存在" in sql
    assert "新表已存在且舊表已移除" in sql


def test_migration_42_deduplicates_each_type_and_resequences():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "DISTINCT ON" in sql
    assert 'btrim("擠製編號")' in sql
    assert 'btrim("爐具編號")' in sql
    assert "ROW_NUMBER() OVER" in sql
    assert "'擠製編號'" in sql
    assert "'T4爐號'" in sql


def test_migration_42_verifies_both_directions_before_drop():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.count("EXCEPT") >= 4
    assert "distinct_count" in sql
    assert "migrated_count" in sql
    assert sql.index("EXCEPT") < sql.index('DROP TABLE "機械性質批次"')
```

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_migration_42.py -q
```

Expected: 因 migration 檔案不存在而 FAIL。

- [ ] **Step 5：建立單一 transaction、可重跑且會驗證集合的 Migration 42**

Create `backend/migration/42_split_mechanical_trace_numbers.sql`，使用一個 `DO` block 處理三種起始狀態，所有對尚未建立資料表的 SQL 都用 `EXECUTE` 延後解析：

```sql
BEGIN;

DO $migration$
DECLARE
    old_exists BOOLEAN := to_regclass('"機械性質批次"') IS NOT NULL;
    new_exists BOOLEAN := to_regclass('"機械性質追溯編號"') IS NOT NULL;
    mismatch_count BIGINT;
    distinct_count BIGINT;
    migrated_count BIGINT;
    trace_index INTEGER;
BEGIN
    IF new_exists AND NOT old_exists THEN
        RAISE NOTICE '新表已存在且舊表已移除，Migration 42 已完成';
        RETURN;
    END IF;

    IF new_exists AND old_exists THEN
        RAISE EXCEPTION '新舊追溯編號資料表同時存在，請人工確認後再執行';
    END IF;

    IF NOT old_exists THEN
        RAISE EXCEPTION '找不到舊機械性質批次資料表，無法安全搬移';
    END IF;

    EXECUTE $sql$
        CREATE TABLE "機械性質追溯編號" (
            "識別碼" SERIAL PRIMARY KEY,
            "機械性質檢驗_ID" INTEGER NOT NULL
                REFERENCES "機械性質檢驗" ("識別碼") ON DELETE CASCADE,
            "類型" VARCHAR(20) NOT NULL,
            "序號" INTEGER NOT NULL,
            "編號" VARCHAR(100) NOT NULL,
            CONSTRAINT uq_mech_trace_seq
                UNIQUE ("機械性質檢驗_ID", "類型", "序號"),
            CONSTRAINT uq_mech_trace_value
                UNIQUE ("機械性質檢驗_ID", "類型", "編號"),
            CONSTRAINT ck_mech_trace_type
                CHECK ("類型" IN ('擠製編號', 'T4爐號')),
            CONSTRAINT ck_mech_trace_seq_positive CHECK ("序號" >= 1),
            CONSTRAINT ck_mech_trace_number
                CHECK (length(btrim("編號")) BETWEEN 1 AND 100)
        )
    $sql$;
    EXECUTE $sql$
        CREATE INDEX ix_mech_trace_test_id
        ON "機械性質追溯編號" ("機械性質檢驗_ID")
    $sql$;

    EXECUTE $sql$
        WITH first_values AS (
            SELECT DISTINCT ON ("機械性質檢驗_ID", btrim("擠製編號"))
                "機械性質檢驗_ID" AS test_id,
                btrim("擠製編號") AS number,
                "序號" AS old_seq,
                "識別碼" AS old_id
            FROM "機械性質批次"
            WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
            ORDER BY "機械性質檢驗_ID", btrim("擠製編號"), "序號", "識別碼"
        ),
        resequenced AS (
            SELECT test_id, number,
                CAST(
                    ROW_NUMBER() OVER (
                        PARTITION BY test_id ORDER BY old_seq, old_id
                    )
                    AS INTEGER
                ) AS new_seq
            FROM first_values
        )
        INSERT INTO "機械性質追溯編號"
            ("機械性質檢驗_ID", "類型", "序號", "編號")
        SELECT test_id, '擠製編號', new_seq, number
        FROM resequenced
    $sql$;

    EXECUTE $sql$
        WITH first_values AS (
            SELECT DISTINCT ON ("機械性質檢驗_ID", btrim("爐具編號"))
                "機械性質檢驗_ID" AS test_id,
                btrim("爐具編號") AS number,
                "序號" AS old_seq,
                "識別碼" AS old_id
            FROM "機械性質批次"
            WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
            ORDER BY "機械性質檢驗_ID", btrim("爐具編號"), "序號", "識別碼"
        ),
        resequenced AS (
            SELECT test_id, number,
                CAST(
                    ROW_NUMBER() OVER (
                        PARTITION BY test_id ORDER BY old_seq, old_id
                    )
                    AS INTEGER
                ) AS new_seq
            FROM first_values
        )
        INSERT INTO "機械性質追溯編號"
            ("機械性質檢驗_ID", "類型", "序號", "編號")
        SELECT test_id, 'T4爐號', new_seq, number
        FROM resequenced
    $sql$;

    EXECUTE $sql$
        SELECT COUNT(*) FROM (
            (
                SELECT "機械性質檢驗_ID", btrim("擠製編號") AS number
                FROM "機械性質批次"
                WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("擠製編號")
                EXCEPT
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號" WHERE "類型" = '擠製編號'
            )
            UNION ALL
            (
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號" WHERE "類型" = '擠製編號'
                EXCEPT
                SELECT "機械性質檢驗_ID", btrim("擠製編號")
                FROM "機械性質批次"
                WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("擠製編號")
            )
        ) AS differences
    $sql$ INTO mismatch_count;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION '擠製編號搬移集合不一致';
    END IF;

    EXECUTE $sql$
        SELECT COUNT(*) FROM (
            (
                SELECT "機械性質檢驗_ID", btrim("爐具編號") AS number
                FROM "機械性質批次"
                WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("爐具編號")
                EXCEPT
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號" WHERE "類型" = 'T4爐號'
            )
            UNION ALL
            (
                SELECT "機械性質檢驗_ID", "編號"
                FROM "機械性質追溯編號" WHERE "類型" = 'T4爐號'
                EXCEPT
                SELECT "機械性質檢驗_ID", btrim("爐具編號")
                FROM "機械性質批次"
                WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
                GROUP BY "機械性質檢驗_ID", btrim("爐具編號")
            )
        ) AS differences
    $sql$ INTO mismatch_count;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION 'T4爐號搬移集合不一致';
    END IF;

    FOREACH trace_index IN ARRAY ARRAY[0, 1] LOOP
        IF trace_index = 0 THEN
            EXECUTE $sql$
                SELECT COUNT(*) FROM (
                    SELECT "機械性質檢驗_ID", btrim("擠製編號")
                    FROM "機械性質批次"
                    WHERE NULLIF(btrim("擠製編號"), '') IS NOT NULL
                    GROUP BY "機械性質檢驗_ID", btrim("擠製編號")
                ) AS values
            $sql$ INTO distinct_count;
            EXECUTE $sql$
                SELECT COUNT(*) FROM "機械性質追溯編號"
                WHERE "類型" = '擠製編號'
            $sql$ INTO migrated_count;
        ELSE
            EXECUTE $sql$
                SELECT COUNT(*) FROM (
                    SELECT "機械性質檢驗_ID", btrim("爐具編號")
                    FROM "機械性質批次"
                    WHERE NULLIF(btrim("爐具編號"), '') IS NOT NULL
                    GROUP BY "機械性質檢驗_ID", btrim("爐具編號")
                ) AS values
            $sql$ INTO distinct_count;
            EXECUTE $sql$
                SELECT COUNT(*) FROM "機械性質追溯編號"
                WHERE "類型" = 'T4爐號'
            $sql$ INTO migrated_count;
        END IF;
        IF distinct_count <> migrated_count THEN
            RAISE EXCEPTION
                '追溯編號筆數不一致：舊表 %，新表 %',
                distinct_count, migrated_count;
        END IF;
    END LOOP;

    EXECUTE 'DROP TABLE "機械性質批次"';
END
$migration$;

COMMIT;
```

實作時保留上述狀態判斷、四個 `EXCEPT` 與逐類型筆數核對；可只針對 PostgreSQL 語法修正，不可弱化驗證。

- [ ] **Step 6：執行模型與 migration 測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_mechanical_models.py backend\tests\test_migration_42.py -q
```

Expected: PASS；測試輸出不得有舊 `MechanicalBatch` import。

- [ ] **Step 7：提交資料模型與 migration**

```powershell
git add backend/models.py backend/migration/42_split_mechanical_trace_numbers.sql backend/tests/test_services/test_mechanical_models.py backend/tests/test_migration_42.py
git commit -m "功能：新增機械性質獨立追溯編號資料模型"
```

---

## Task 2：後端正規化新版與舊版 payload

**Files:**

- Modify: `backend/services/mechanical_service.py`
- Modify: `backend/tests/test_services/test_mechanical_service.py`

- [ ] **Step 1：新增會失敗的 service 驗證測試**

保留 `_payload()` 的量測與主檔欄位，把預設追溯資料改為：

```python
"extrusion_numbers": [
    {"序號": 1, "編號": "010761 D35"},
],
"t4_furnace_numbers": [
    {"序號": 1, "編號": "011313T42"},
    {"序號": 2, "編號": "011314T42"},
],
```

新增下列案例：

```python
def test_create_accepts_one_extrusion_and_two_t4_furnace_numbers(app, db_session):
    payload = _payload()
    test_id = MechanicalService.create(payload, user_id=None)

    detail = MechanicalService.get_detail(test_id)
    assert [row["編號"] for row in detail["extrusion_numbers"]] == ["010761 D35"]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "011313T42",
        "011314T42",
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"extrusion_numbers": {}}),
        lambda payload: payload.update({"t4_furnace_numbers": ["bad"]}),
        lambda payload: payload.update(
            {"extrusion_numbers": [{"序號": 0, "編號": "E1"}]}
        ),
        lambda payload: payload.update(
            {"t4_furnace_numbers": [{"序號": 2, "編號": "T4-1"}]}
        ),
        lambda payload: payload.update(
            {
                "extrusion_numbers": [
                    {"序號": 1, "編號": " E1 "},
                    {"序號": 2, "編號": "E1"},
                ]
            }
        ),
        lambda payload: payload.update(
            {"t4_furnace_numbers": [{"序號": 1, "編號": " "}]}
        ),
        lambda payload: payload.update(
            {"extrusion_numbers": [{"序號": 1, "編號": "x" * 101}]}
        ),
    ],
)
def test_new_trace_number_payload_rejects_invalid_values(
    app, db_session, mutate
):
    payload = _payload()
    mutate(payload)
    with pytest.raises(MechanicalValidationError):
        MechanicalService.create(payload, user_id=None)


def test_new_and_legacy_trace_payload_cannot_be_mixed(app, db_session):
    payload = _payload()
    payload["batches"] = []
    with pytest.raises(
        MechanicalValidationError,
        match="不得同時提供新版追溯編號與 batches",
    ):
        MechanicalService.create(payload, user_id=None)


def test_legacy_batches_split_trim_deduplicate_and_resequence(app, db_session):
    payload = _payload()
    payload.pop("extrusion_numbers")
    payload.pop("t4_furnace_numbers")
    payload["batches"] = [
        {"序號": 2, "擠製編號": " E1 ", "爐具編號": "T4-02"},
        {"序號": 1, "擠製編號": "E1", "爐具編號": "T4-01"},
    ]

    test_id = MechanicalService.create(payload, user_id=None)
    detail = MechanicalService.get_detail(test_id)
    assert [
        (row["序號"], row["編號"])
        for row in detail["extrusion_numbers"]
    ] == [(1, "E1")]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "T4-01",
        "T4-02",
    ]
```

- [ ] **Step 2：執行窄測試，確認仍依賴 `batches` 而失敗**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_mechanical_service.py -q
```

Expected: 新版欄位案例 FAIL，錯誤會指出 detail 缺少 `extrusion_numbers` 或資料未被保存。

- [ ] **Step 3：新增統一 parser，讓驗證與寫入共用同一份正規化結果**

在 `mechanical_service.py` 定義：

```python
TRACE_TYPE_EXTRUSION = "擠製編號"
TRACE_TYPE_T4_FURNACE = "T4爐號"
NEW_TRACE_FIELDS = {
    "extrusion_numbers": TRACE_TYPE_EXTRUSION,
    "t4_furnace_numbers": TRACE_TYPE_T4_FURNACE,
}
NormalizedTraceNumbers = Dict[str, list[tuple[int, str]]]
```

新增新版清單驗證：

```python
def _parse_trace_list(value: Any, field: str) -> list[tuple[int, str]]:
    if not isinstance(value, list):
        raise MechanicalValidationError(f"{field} 必須為陣列")

    parsed: list[tuple[int, str]] = []
    seen_numbers: set[str] = set()
    for expected_sequence, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            raise MechanicalValidationError(f"{field} 的項目必須為物件")
        sequence = row.get("序號")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence != expected_sequence
        ):
            raise MechanicalValidationError(f"{field} 序號必須從 1 連續排列")
        number = row.get("編號")
        if not isinstance(number, str):
            raise MechanicalValidationError(f"{field} 編號必須為字串")
        number = number.strip()
        if not number:
            raise MechanicalValidationError(f"{field} 編號不得為空")
        if len(number) > 100:
            raise MechanicalValidationError(f"{field} 編號不得超過 100 字元")
        if number in seen_numbers:
            raise MechanicalValidationError(f"{field} 編號不可重複")
        seen_numbers.add(number)
        parsed.append((sequence, number))
    return parsed
```

新增舊格式轉換；先驗證舊 `序號` 為不重複正整數，再依 `(序號, 原陣列位置)` 排序，各類型分別 trim、略過空值、保留第一次、重新編號：

```python
def _parse_legacy_batches(value: Any) -> NormalizedTraceNumbers:
    if not isinstance(value, list):
        raise MechanicalValidationError("batches 必須為陣列")

    ordered: list[tuple[int, int, dict[str, Any]]] = []
    seen_sequences: set[int] = set()
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise MechanicalValidationError("批次必須為物件")
        sequence = row.get("序號")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise MechanicalValidationError("批次序號必須為正整數")
        if sequence in seen_sequences:
            raise MechanicalValidationError("批次序號不可重複")
        seen_sequences.add(sequence)
        for field in ("擠製編號", "爐具編號"):
            raw = row.get(field)
            if raw is not None and not isinstance(raw, str):
                raise MechanicalValidationError(f"{field}必須為字串")
            if isinstance(raw, str) and len(raw.strip()) > 100:
                raise MechanicalValidationError(f"{field}不得超過 100 字元")
        ordered.append((sequence, index, row))

    output: NormalizedTraceNumbers = {
        TRACE_TYPE_EXTRUSION: [],
        TRACE_TYPE_T4_FURNACE: [],
    }
    for source_field, trace_type in (
        ("擠製編號", TRACE_TYPE_EXTRUSION),
        ("爐具編號", TRACE_TYPE_T4_FURNACE),
    ):
        values: list[str] = []
        seen: set[str] = set()
        for _, _, row in sorted(ordered):
            number = (row.get(source_field) or "").strip()
            if number and number not in seen:
                seen.add(number)
                values.append(number)
        output[trace_type] = [
            (sequence, number)
            for sequence, number in enumerate(values, start=1)
        ]
    return output
```

以單一入口區分格式：

```python
def _parse_trace_numbers(data: Dict[str, Any]) -> NormalizedTraceNumbers:
    new_present = any(field in data for field in NEW_TRACE_FIELDS)
    legacy_present = "batches" in data
    if new_present and legacy_present:
        raise MechanicalValidationError("不得同時提供新版追溯編號與 batches")
    if new_present:
        missing = [field for field in NEW_TRACE_FIELDS if field not in data]
        if missing:
            raise MechanicalValidationError("新版追溯編號兩個欄位都必須提供")
        return {
            trace_type: _parse_trace_list(data[field], field)
            for field, trace_type in NEW_TRACE_FIELDS.items()
        }
    if legacy_present:
        return _parse_legacy_batches(data["batches"])
    raise MechanicalValidationError(
        "必須提供 extrusion_numbers、t4_furnace_numbers 或 batches"
    )
```

把 `_validate_payload` 回傳型別改為：

```python
def _validate_payload(
    data: Dict[str, Any],
) -> tuple[Optional[int], NormalizedTraceNumbers]:
    # 原有主檔、日期、量測、廠商驗證保持不變
    trace_numbers = _parse_trace_numbers(data)
    # ...
    return vendor_id, trace_numbers
```

- [ ] **Step 4：以正規化結果重建追溯編號**

匯入 `MechanicalTraceNumber`，以新方法取代 `_apply_batches`：

```python
@staticmethod
def _apply_trace_numbers(
    test: MechanicalTest,
    values: NormalizedTraceNumbers,
) -> None:
    test.trace_numbers.clear()
    db.session.flush()
    for trace_type in (TRACE_TYPE_EXTRUSION, TRACE_TYPE_T4_FURNACE):
        for sequence, number in values[trace_type]:
            test.trace_numbers.append(
                MechanicalTraceNumber(
                    trace_type=trace_type,
                    seq=sequence,
                    number=number,
                )
            )
```

create/update 改為一次取得正規化結果：

```python
vendor_id, trace_numbers = _validate_payload(data)
# 設定主檔後：
MechanicalService._apply_trace_numbers(test, trace_numbers)
```

保留原本 `try/except` 的 `db.session.rollback()` 行為。

- [ ] **Step 5：執行 service 測試並提交**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_mechanical_service.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/mechanical_service.py backend/tests/test_services/test_mechanical_service.py
git commit -m "功能：支援機械性質兩份獨立追溯編號"
```

---

## Task 3：完成新版 response、deprecated response 與 route 驗證

**Files:**

- Modify: `backend/services/mechanical_service.py`
- Modify: `backend/tests/test_services/test_mechanical_service.py`
- Modify: `backend/tests/test_mechanical_route.py`

- [ ] **Step 1：先寫清單與明細 response 失敗測試**

service 測試明確鎖定不配對：

```python
def test_detail_returns_new_lists_and_unpaired_legacy_rows(app, db_session):
    test_id = MechanicalService.create(_payload(), user_id=None)
    detail = MechanicalService.get_detail(test_id)

    assert [row["編號"] for row in detail["extrusion_numbers"]] == ["010761 D35"]
    assert [row["編號"] for row in detail["t4_furnace_numbers"]] == [
        "011313T42",
        "011314T42",
    ]
    assert detail["batches"] == [
        {
            "序號": 1,
            "擠製編號": "010761 D35",
            "爐具編號": None,
        },
        {
            "序號": 2,
            "擠製編號": None,
            "爐具編號": "011313T42",
        },
        {
            "序號": 3,
            "擠製編號": None,
            "爐具編號": "011314T42",
        },
    ]


def test_list_has_independent_trace_summaries(app, db_session):
    MechanicalService.create(_payload(), user_id=None)
    listed = MechanicalService.list({})["data"][0]
    assert listed["擠製編號"] == "010761 D35"
    assert listed["T4爐號"] == "011313T42、011314T42"
```

將既有 `test_create_and_list_via_api` 的有效 payload 改成新版格式，並在同一測試鎖定 detail：

```python
def test_create_and_list_via_api(client, db_session):
    headers = _auth_headers(db_session, "qc", {
        "mechanical.create": True,
        "mechanical.edit": True,
        "mechanical.delete": True,
    })
    db_session.commit()
    payload = {
        "產品尺寸": "36x25.2",
        "材質": "6061-T651",
        "測試日期": "2026-01-20",
        "extrusion_numbers": [{"序號": 1, "編號": "E1"}],
        "t4_furnace_numbers": [
            {"序號": 1, "編號": "T4-01"},
            {"序號": 2, "編號": "T4-02"},
        ],
        "measurements": [
            {
                "量測項目": "硬度",
                "測量位置": "爐門",
                "取樣序": 1,
                "量測值": 70,
            }
        ],
    }
    created = client.post(
        "/api/mechanical/tests", json=payload, headers=headers
    )
    assert created.status_code == 200
    new_id = created.get_json()["id"]

    detail = client.get(
        f"/api/mechanical/tests/{new_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.get_json()["extrusion_numbers"][0]["編號"] == "E1"
    assert len(detail.get_json()["t4_furnace_numbers"]) == 2

    payload["batches"] = []
    invalid = client.post(
        "/api/mechanical/tests", json=payload, headers=headers
    )
    assert invalid.status_code == 400
```

保留原測試既有的 list 與材質 detail 斷言，並把其他「預期成功」的
create/update payload 一併補上兩個新版空陣列；原本專門驗證 400 的
payload 不必補，避免改變其測試意圖。

- [ ] **Step 2：執行窄測試，確認 response 尚未完成**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_mechanical_service.py backend\tests\test_mechanical_route.py -q
```

Expected: `T4爐號` 或新版 detail 欄位斷言 FAIL。

- [ ] **Step 3：建立共用排序與序列化方法**

在 service 新增：

```python
def _trace_rows(test: MechanicalTest, trace_type: str) -> list[MechanicalTraceNumber]:
    return sorted(
        (
            row
            for row in test.trace_numbers
            if row.trace_type == trace_type
        ),
        key=lambda row: row.seq,
    )


def _serialize_trace_rows(
    test: MechanicalTest,
    trace_type: str,
) -> list[Dict[str, Any]]:
    return [
        {"識別碼": row.id, "序號": row.seq, "編號": row.number}
        for row in _trace_rows(test, trace_type)
    ]
```

list item 改為：

```python
"擠製編號": "、".join(
    row.number for row in _trace_rows(t, TRACE_TYPE_EXTRUSION)
),
"T4爐號": "、".join(
    row.number for row in _trace_rows(t, TRACE_TYPE_T4_FURNACE)
),
```

detail 新欄位：

```python
extrusion_numbers = _serialize_trace_rows(t, TRACE_TYPE_EXTRUSION)
t4_furnace_numbers = _serialize_trace_rows(t, TRACE_TYPE_T4_FURNACE)
```

deprecated `batches` 使用全域連續序號，每列只有一種編號：

```python
batches = []
for row in extrusion_numbers:
    batches.append({
        "序號": len(batches) + 1,
        "擠製編號": row["編號"],
        "爐具編號": None,
    })
for row in t4_furnace_numbers:
    batches.append({
        "序號": len(batches) + 1,
        "擠製編號": None,
        "爐具編號": row["編號"],
    })

return {
    "success": True,
    "main": main,
    "extrusion_numbers": extrusion_numbers,
    "t4_furnace_numbers": t4_furnace_numbers,
    "batches": batches,
    "measurements": measurements,
}
```

不要把兩清單用 `zip`、索引或空白補列重新湊成對。

- [ ] **Step 4：執行後端機械性質測試並提交**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_mechanical_models.py backend\tests\test_services\test_mechanical_service.py backend\tests\test_mechanical_route.py backend\tests\test_migration_42.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/mechanical_service.py backend/tests/test_services/test_mechanical_service.py backend/tests/test_mechanical_route.py
git commit -m "功能：回傳機械性質獨立追溯編號摘要"
```

---

## Task 4：更新前端型別與純資料 helper

**Files:**

- Modify: `src_frontend/src/types/mechanical.ts`
- Modify: `src_frontend/src/pages/mechanical/mechanicalPayload.ts`
- Modify: `src_frontend/src/pages/mechanical/mechanicalPayload.test.ts`

- [ ] **Step 1：先寫 helper 的失敗測試**

在 `mechanicalPayload.test.ts` 新增：

```typescript
import {
  buildTraceNumbers,
  duplicateTraceNumberIndexes,
  emptyTraceNumber,
  hydrateTraceNumbers,
  removeTraceNumber,
} from './mechanicalPayload';

describe('機械性質追溯編號 helper', () => {
  it('移除空白、trim 並重新編為連續序號', () => {
    expect(buildTraceNumbers([
      { 序號: 1, 編號: ' E001 ' },
      { 序號: 2, 編號: ' ' },
      { 序號: 3, 編號: 'E002' },
    ])).toEqual([
      { 序號: 1, 編號: 'E001' },
      { 序號: 2, 編號: 'E002' },
    ]);
  });

  it('同清單 trim 後相同值標示所有重複列', () => {
    expect([...duplicateTraceNumberIndexes([
      { 序號: 1, 編號: ' E001' },
      { 序號: 2, 編號: 'E001 ' },
      { 序號: 3, 編號: 'e001' },
    ])]).toEqual([0, 1]);
  });

  it('hydrate 空陣列時保留一列空白輸入', () => {
    expect(hydrateTraceNumbers([])).toEqual([emptyTraceNumber(1)]);
  });

  it('刪除後只重排該份清單且至少保留一列', () => {
    const current = [
      { 序號: 1, 編號: 'A' },
      { 序號: 2, 編號: 'B' },
    ];
    expect(removeTraceNumber(current, 0)).toEqual([{ 序號: 1, 編號: 'B' }]);
    expect(removeTraceNumber([{ 序號: 1, 編號: 'A' }], 0)).toEqual([
      { 序號: 1, 編號: '' },
    ]);
  });
});
```

- [ ] **Step 2：執行 helper 測試，確認函式不存在**

Run:

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/mechanicalPayload.test.ts
```

Expected: TypeScript/測試因缺少 export 而 FAIL。

- [ ] **Step 3：更新型別契約**

在 `mechanical.ts` 新增並套用：

```typescript
export interface MechanicalTraceNumber {
  識別碼?: number;
  序號: number;
  編號: string;
}

/** @deprecated 僅供舊 detail response 相容，新增前端不得使用。 */
export interface MechanicalBatch {
  序號: number;
  擠製編號: string | null;
  爐具編號: string | null;
}
```

此 Task 只新增 `MechanicalTraceNumber` 與 helper 所需 import；先保留
`MechanicalTestListItem`、`MechanicalTestDetail`、`MechanicalTestPayload`
的既有欄位，避免在表單尚未同步前留下不能 build 的中間 commit。detail/payload
在 Task 5 與表單一起切換，list item 在 Task 6 與清單一起切換。

- [ ] **Step 4：實作純 helper**

在 `mechanicalPayload.ts`：

```typescript
import type {
  MechItem,
  MechLocation,
  MechanicalMeasurement,
  MechanicalTraceNumber,
} from '../../types';

export const emptyTraceNumber = (sequence: number): MechanicalTraceNumber => ({
  序號: sequence,
  編號: '',
});

export function buildTraceNumbers(
  values: MechanicalTraceNumber[],
): MechanicalTraceNumber[] {
  return values
    .map((value) => value.編號.trim())
    .filter(Boolean)
    .map((編號, index) => ({ 序號: index + 1, 編號 }));
}

export function hydrateTraceNumbers(
  values: MechanicalTraceNumber[],
): MechanicalTraceNumber[] {
  const hydrated = [...values]
    .sort((left, right) => left.序號 - right.序號)
    .map((value, index) => ({ 序號: index + 1, 編號: value.編號 }));
  return hydrated.length > 0 ? hydrated : [emptyTraceNumber(1)];
}

export function duplicateTraceNumberIndexes(
  values: MechanicalTraceNumber[],
): Set<number> {
  const byNumber = new Map<string, number[]>();
  values.forEach((value, index) => {
    const number = value.編號.trim();
    if (!number) return;
    byNumber.set(number, [...(byNumber.get(number) ?? []), index]);
  });
  return new Set(
    [...byNumber.values()]
      .filter((indexes) => indexes.length > 1)
      .flat(),
  );
}

export function removeTraceNumber(
  values: MechanicalTraceNumber[],
  removeIndex: number,
): MechanicalTraceNumber[] {
  const remaining = values
    .filter((_, index) => index !== removeIndex)
    .map((value, index) => ({ ...value, 序號: index + 1 }));
  return remaining.length > 0 ? remaining : [emptyTraceNumber(1)];
}
```

- [ ] **Step 5：執行 helper 測試與 TypeScript build，然後提交**

Run:

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/mechanicalPayload.test.ts
npm run build
```

Expected: helper 測試與 build 都 PASS。

Commit:

```powershell
Set-Location ..
git add src_frontend/src/types/mechanical.ts src_frontend/src/pages/mechanical/mechanicalPayload.ts src_frontend/src/pages/mechanical/mechanicalPayload.test.ts
git commit -m "重構：建立機械性質追溯編號前端契約"
```

---

## Task 5：建立兩個獨立面板並改寫新增／編輯表單

**Files:**

- Create: `src_frontend/src/pages/mechanical/MechanicalTraceNumberPanel.tsx`
- Create: `src_frontend/src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx`
- Modify: `src_frontend/src/pages/mechanical/MechanicalTestForm.tsx`
- Modify: `src_frontend/src/pages/mechanical/MechanicalTestForm.test.tsx`
- Modify: `src_frontend/src/types/mechanical.ts`

- [ ] **Step 1：先寫獨立面板元件失敗測試**

Create `MechanicalTraceNumberPanel.test.tsx`：

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import MechanicalTraceNumberPanel from './MechanicalTraceNumberPanel';

describe('MechanicalTraceNumberPanel', () => {
  it('顯示標題、序號，並把輸入與新增事件交給上層', () => {
    const onChange = vi.fn();
    const onAdd = vi.fn();
    render(
      <MechanicalTraceNumberPanel
        idPrefix="extrusion"
        title="擠製編號"
        addLabel="新增擠製編號"
        values={[{ 序號: 1, 編號: '' }]}
        duplicateIndexes={new Set()}
        onChange={onChange}
        onAdd={onAdd}
        onRemove={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('擠製編號 1'), {
      target: { value: 'E001' },
    });
    fireEvent.click(screen.getByRole('button', { name: '新增擠製編號' }));
    expect(onChange).toHaveBeenCalledWith(0, 'E001');
    expect(onAdd).toHaveBeenCalledOnce();
  });

  it('重複列有可存取錯誤關聯', () => {
    render(
      <MechanicalTraceNumberPanel
        idPrefix="t4-furnace"
        title="T4爐號"
        addLabel="新增T4爐號"
        values={[
          { 序號: 1, 編號: 'T4-01' },
          { 序號: 2, 編號: 'T4-01' },
        ]}
        duplicateIndexes={new Set([0, 1])}
        onChange={vi.fn()}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    const first = screen.getByLabelText('T4爐號 1');
    expect(first).toHaveAttribute('aria-invalid', 'true');
    expect(first).toHaveAttribute(
      'aria-describedby',
      'mechanical-t4-furnace-1-duplicate-error',
    );
    expect(screen.getAllByText('同一清單內的編號不可重複')).toHaveLength(2);
  });
});
```

- [ ] **Step 2：在表單測試先鎖定兩清單不互相影響、payload 與儲存阻擋**

新增／更新測試：

```tsx
it('可獨立新增一個擠製編號與兩個 T4爐號後送出新版 payload', async () => {
  renderForm();
  fireEvent.change(screen.getByLabelText('產品尺寸'), {
    target: { value: '36x25.2' },
  });
  fireEvent.change(screen.getByLabelText('擠製編號 1'), {
    target: { value: ' E001 ' },
  });
  fireEvent.change(screen.getByLabelText('T4爐號 1'), {
    target: { value: 'T4-01' },
  });
  fireEvent.click(screen.getByRole('button', { name: '新增T4爐號' }));
  fireEvent.change(screen.getByLabelText('T4爐號 2'), {
    target: { value: 'T4-02' },
  });
  fireEvent.click(screen.getByRole('button', { name: '儲存' }));

  await waitFor(() => expect(mechanicalApi.create).toHaveBeenCalledWith(
    expect.objectContaining({
      extrusion_numbers: [{ 序號: 1, 編號: 'E001' }],
      t4_furnace_numbers: [
        { 序號: 1, 編號: 'T4-01' },
        { 序號: 2, 編號: 'T4-02' },
      ],
    }),
  ));
  expect(mechanicalApi.create).not.toHaveBeenCalledWith(
    expect.objectContaining({ batches: expect.anything() }),
  );
});

it('同一清單重複時顯示錯誤且禁止儲存', async () => {
  renderForm();
  fireEvent.change(screen.getByLabelText('產品尺寸'), {
    target: { value: '36x25.2' },
  });
  fireEvent.click(screen.getByRole('button', { name: '新增擠製編號' }));
  fireEvent.change(screen.getByLabelText('擠製編號 1'), {
    target: { value: 'E001' },
  });
  fireEvent.change(screen.getByLabelText('擠製編號 2'), {
    target: { value: ' E001 ' },
  });
  fireEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(await screen.findByText('請移除重複的追溯編號')).toBeInTheDocument();
  expect(mechanicalApi.create).not.toHaveBeenCalled();
});

it('編輯時只讀新版兩份清單，不讀 deprecated batches', async () => {
  vi.mocked(mechanicalApi.getDetail).mockResolvedValue({
    ...editDetail,
    extrusion_numbers: [{ 識別碼: 1, 序號: 1, 編號: 'E001' }],
    t4_furnace_numbers: [
      { 識別碼: 2, 序號: 1, 編號: 'T4-01' },
      { 識別碼: 3, 序號: 2, 編號: 'T4-02' },
    ],
    batches: [
      { 序號: 1, 擠製編號: '不應顯示', 爐具編號: null },
    ],
  });
  renderForm(8);

  expect(await screen.findByDisplayValue('E001')).toBeInTheDocument();
  expect(screen.getByDisplayValue('T4-01')).toBeInTheDocument();
  expect(screen.getByDisplayValue('T4-02')).toBeInTheDocument();
  expect(screen.queryByDisplayValue('不應顯示')).not.toBeInTheDocument();
});
```

同時把檔案頂端 `editDetail` fixture 改成新版兩清單，保留一份 deprecated
`batches` 作「新前端不讀取」的防回歸證據；其餘編輯測試沿用同一 fixture。

- [ ] **Step 3：執行兩個元件測試，確認因元件與 UI 尚不存在而失敗**

Run:

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx src/pages/mechanical/MechanicalTestForm.test.tsx
```

Expected: 缺少 `MechanicalTraceNumberPanel` 或找不到新欄位而 FAIL。

- [ ] **Step 4：實作獨立面板元件**

`MechanicalTraceNumberPanel.tsx` props：

```tsx
interface MechanicalTraceNumberPanelProps {
  idPrefix: 'extrusion' | 't4-furnace';
  title: '擠製編號' | 'T4爐號';
  addLabel: string;
  values: MechanicalTraceNumber[];
  duplicateIndexes: Set<number>;
  onChange: (index: number, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}
```

元件主體沿用 React Bootstrap，確保 label 與錯誤 ID 唯一：

```tsx
export default function MechanicalTraceNumberPanel({
  idPrefix,
  title,
  addLabel,
  values,
  duplicateIndexes,
  onChange,
  onAdd,
  onRemove,
}: MechanicalTraceNumberPanelProps) {
  return (
    <section className="border rounded p-3 h-100" aria-labelledby={`mechanical-${idPrefix}-title`}>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 id={`mechanical-${idPrefix}-title`} className="h6 mb-0">{title}</h3>
        <Button type="button" size="sm" variant="outline-primary" onClick={onAdd}>
          {addLabel}
        </Button>
      </div>
      <div className="d-grid gap-2">
        {values.map((value, index) => {
          const inputId = `mechanical-${idPrefix}-${value.序號}`;
          const errorId = `${inputId}-duplicate-error`;
          const isDuplicate = duplicateIndexes.has(index);
          return (
            <div key={value.序號}>
              <div className="d-flex gap-2 align-items-start">
                <span className="pt-2" aria-hidden="true">{value.序號}</span>
                <Form.Group className="flex-grow-1" controlId={inputId}>
                  <Form.Label className="visually-hidden">{`${title} ${value.序號}`}</Form.Label>
                  <Form.Control
                    maxLength={100}
                    value={value.編號}
                    aria-invalid={isDuplicate}
                    aria-describedby={isDuplicate ? errorId : undefined}
                    isInvalid={isDuplicate}
                    onChange={(event) => onChange(index, event.target.value)}
                  />
                  {isDuplicate && (
                    <Form.Control.Feedback id={errorId} type="invalid">
                      同一清單內的編號不可重複
                    </Form.Control.Feedback>
                  )}
                </Form.Group>
                <Button
                  type="button"
                  variant="outline-danger"
                  aria-label={`刪除${title} ${value.序號}`}
                  onClick={() => onRemove(index)}
                >
                  刪除
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 5：改寫表單狀態、hydrate、儲存與版面**

先在 `mechanical.ts` 完成主契約切換。在既有 `MechanicalTestDetail`
刪除必填的 `batches: MechanicalBatch[]`，改加：

```typescript
extrusion_numbers: MechanicalTraceNumber[];
t4_furnace_numbers: MechanicalTraceNumber[];
/** @deprecated 舊前端相容欄位。 */
batches?: MechanicalBatch[];
```

在既有 `MechanicalTestPayload` 刪除 `batches: MechanicalBatch[]`，改加：

```typescript
extrusion_numbers: MechanicalTraceNumber[];
t4_furnace_numbers: MechanicalTraceNumber[];
```

移除 `MechanicalBatch`、`emptyBatch`、`batches` 與舊 setter，新增：

```tsx
const [extrusionNumbers, setExtrusionNumbers] = useState<MechanicalTraceNumber[]>([
  emptyTraceNumber(1),
]);
const [t4FurnaceNumbers, setT4FurnaceNumbers] = useState<MechanicalTraceNumber[]>([
  emptyTraceNumber(1),
]);

const extrusionDuplicateIndexes = duplicateTraceNumberIndexes(extrusionNumbers);
const t4FurnaceDuplicateIndexes = duplicateTraceNumberIndexes(t4FurnaceNumbers);
const hasDuplicateTraceNumbers =
  extrusionDuplicateIndexes.size > 0 || t4FurnaceDuplicateIndexes.size > 0;
```

新增通用 state 操作：

```tsx
const setTraceValue = (
  setter: Dispatch<SetStateAction<MechanicalTraceNumber[]>>,
  index: number,
  value: string,
) => {
  setter((current) => current.map((row, rowIndex) => (
    rowIndex === index ? { ...row, 編號: value } : row
  )));
  setValidationError('');
};

const addTraceValue = (
  setter: Dispatch<SetStateAction<MechanicalTraceNumber[]>>,
) => setter((current) => [...current, emptyTraceNumber(current.length + 1)]);
```

把 React import 改為：

```tsx
import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from 'react';
```

reset 與 detail hydrate 分別使用：

```tsx
setExtrusionNumbers(hydrateTraceNumbers(detail.extrusion_numbers));
setT4FurnaceNumbers(hydrateTraceNumbers(detail.t4_furnace_numbers));
```

save 在主檔必填與量測格式檢查後加入：

```tsx
if (hasDuplicateTraceNumbers) {
  const message = '請移除重複的追溯編號';
  setValidationError(message);
  toast.error(message);
  return;
}
```

payload 改為：

```tsx
extrusion_numbers: buildTraceNumbers(extrusionNumbers),
t4_furnace_numbers: buildTraceNumbers(t4FurnaceNumbers),
```

把舊 paired table 換成響應式格線：

```tsx
<Row className="g-3 mt-1">
  <Col md={6}>
    <MechanicalTraceNumberPanel
      idPrefix="extrusion"
      title="擠製編號"
      addLabel="新增擠製編號"
      values={extrusionNumbers}
      duplicateIndexes={extrusionDuplicateIndexes}
      onChange={(index, value) => setTraceValue(setExtrusionNumbers, index, value)}
      onAdd={() => addTraceValue(setExtrusionNumbers)}
      onRemove={(index) => setExtrusionNumbers(
        (current) => removeTraceNumber(current, index),
      )}
    />
  </Col>
  <Col md={6}>
    <MechanicalTraceNumberPanel
      idPrefix="t4-furnace"
      title="T4爐號"
      addLabel="新增T4爐號"
      values={t4FurnaceNumbers}
      duplicateIndexes={t4FurnaceDuplicateIndexes}
      onChange={(index, value) => setTraceValue(setT4FurnaceNumbers, index, value)}
      onAdd={() => addTraceValue(setT4FurnaceNumbers)}
      onRemove={(index) => setT4FurnaceNumbers(
        (current) => removeTraceNumber(current, index),
      )}
    />
  </Col>
</Row>
```

- [ ] **Step 6：執行表單測試、lint 與 build**

Run:

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx src/pages/mechanical/MechanicalTestForm.test.tsx src/pages/mechanical/mechanicalPayload.test.ts
npm run lint -- --max-warnings=0
npm run build
```

Expected: 全部 PASS。

- [ ] **Step 7：提交表單功能**

```powershell
Set-Location ..
git add src_frontend/src/types/mechanical.ts src_frontend/src/pages/mechanical/MechanicalTraceNumberPanel.tsx src_frontend/src/pages/mechanical/MechanicalTraceNumberPanel.test.tsx src_frontend/src/pages/mechanical/MechanicalTestForm.tsx src_frontend/src/pages/mechanical/MechanicalTestForm.test.tsx
git commit -m "功能：機械性質表單分開新增擠製編號與T4爐號"
```

---

## Task 6：更新清單欄位與避免舊稱殘留

**Files:**

- Modify: `src_frontend/src/pages/mechanical/MechanicalTestListPage.tsx`
- Modify: `src_frontend/src/pages/mechanical/MechanicalTestListPage.test.tsx`
- Modify: `src_frontend/src/types/mechanical.ts`
- Modify: `docs/superpowers/specs/2026-07-23-mechanical-properties-inspection-design.md`

- [ ] **Step 1：先寫清單失敗測試**

在 list mock item 增加 `T4爐號`，新增斷言：

```tsx
it('分欄顯示兩種追溯摘要並使用完整溫度時間標題', async () => {
  renderPage();

  expect(await screen.findByRole('columnheader', { name: '擠製編號' })).toBeInTheDocument();
  expect(screen.getByRole('columnheader', { name: 'T4爐號' })).toBeInTheDocument();
  expect(screen.getByRole('columnheader', { name: 'T4溫度/時間' })).toBeInTheDocument();
  expect(screen.getByRole('columnheader', { name: 'T6溫度/時間' })).toBeInTheDocument();
  expect(screen.getByText('E001')).toBeInTheDocument();
  expect(screen.getByText('T4-01、T4-02')).toBeInTheDocument();
});
```

在 `beforeEach` 的 list mock item 把擠製編號改為 `E001` 並新增
`T4爐號: 'T4-01、T4-02'`。若檔案內存在 loading/empty row 的
`colSpan={8}`，對應斷言改為 9；現況若沒有 table empty row，不為測試新增
不必要的 markup。

- [ ] **Step 2：執行 list 測試，確認新欄與標題尚不存在**

Run:

```powershell
Set-Location src_frontend
npm test -- --run src/pages/mechanical/MechanicalTestListPage.test.tsx
```

Expected: 找不到 `T4爐號` column header 而 FAIL。

- [ ] **Step 3：更新清單**

欄位順序固定為：

```tsx
<th>產品尺寸</th>
<th>材質</th>
<th>測試日期</th>
<th>擠製編號</th>
<th>T4爐號</th>
<th>T4溫度/時間</th>
<th>T6溫度/時間</th>
<th>判定</th>
<th>操作</th>
```

row 增加：

```tsx
<td>{item.T4爐號 || '—'}</td>
```

若實作檔案中確有 loading/empty table row，該 row 的 `colSpan` 從 8 改為 9；
現況以 table 外的 `<p>` 呈現時維持原結構。

在 `MechanicalTestListItem` 增加必填欄位：

```typescript
T4爐號: string;
```

- [ ] **Step 4：同步 Phase 1 歷史 spec 的替代說明**

在舊 `2026-07-23-mechanical-properties-inspection-design.md` 開頭狀態後新增明確說明，避免後續把舊成對模型當成現況：

```markdown
> **Phase 1.1 更新：** 本文件中的「擠製編號／爐具編號成對批次」設計，
> 已由 `2026-07-23-mechanical-independent-trace-numbers-design.md` 取代。
> 現行設計為「擠製編號」與「T4爐號」兩份獨立清單。
```

歷史文件其餘內容保留，不重寫已完成 Phase 1 的紀錄。

- [ ] **Step 5：執行 list 與全前端驗證後提交**

Run:

```powershell
Set-Location src_frontend
npm test -- --run
npm run lint -- --max-warnings=0
npm run build
```

Expected: 全部 PASS，lint 0 warnings。

Commit:

```powershell
Set-Location ..
git add src_frontend/src/types/mechanical.ts src_frontend/src/pages/mechanical/MechanicalTestListPage.tsx src_frontend/src/pages/mechanical/MechanicalTestListPage.test.tsx docs/superpowers/specs/2026-07-23-mechanical-properties-inspection-design.md
git commit -m "介面：顯示機械性質T4爐號獨立摘要"
```

---

## Task 7：在 PostgreSQL 驗證 Migration 42 與整體回歸

**Files:**

- Verify only unless a failing test reveals an in-scope defect

- [ ] **Step 1：備份並查核 migration 前狀態**

先讀 `.env` 所指向的本機開發資料庫連線；輸出中不可顯示密碼。對開發資料庫執行：

```powershell
$qcDbEnv = @{}
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        $qcDbEnv[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$qcDbHost = $qcDbEnv.DB_HOST
$qcDbPort = $qcDbEnv.DB_PORT
$qcDbName = $qcDbEnv.DB_NAME
$qcDbUser = $qcDbEnv.DB_USER
$env:PGPASSWORD = $qcDbEnv.DB_PASSWORD
$qcBackupPath = Join-Path $env:TEMP (
    "qa_database_before_migration_42_{0}.dump" -f (Get-Date -Format "yyyyMMdd_HHmmss")
)
pg_dump -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -Fc -f $qcBackupPath
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT to_regclass('\"機械性質批次\"'), to_regclass('\"機械性質追溯編號\"');"
```

Expected: 備份成功；第一次執行前只有舊表存在。若新舊兩表同時存在，停止套用並調查，不可刪表繞過 guard。

- [ ] **Step 2：建立可辨識的舊模型搬移 fixture**

在套用 migration 前加入一筆專用主檔與三列舊批次，其中同一擠製編號
搭配兩個 T4爐號，第三列驗證空白會被略過：

```powershell
@'
WITH inserted_test AS (
    INSERT INTO "機械性質檢驗" ("產品尺寸", "材質", "備註")
    VALUES ('MIGRATION42-TEST', 'MIGRATION42-TEST', 'Migration 42 驗證，完成後刪除')
    RETURNING "識別碼"
)
INSERT INTO "機械性質批次"
    ("機械性質檢驗_ID", "序號", "擠製編號", "爐具編號")
SELECT "識別碼", source."序號", source."擠製編號", source."爐具編號"
FROM inserted_test
CROSS JOIN (
    VALUES
        (1, ' E-M42 ', 'T4-M42-01'),
        (2, 'E-M42', ' T4-M42-02 '),
        (3, '   ', NULL)
) AS source ("序號", "擠製編號", "爐具編號");
'@ | psql -v ON_ERROR_STOP=1 -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName
```

Expected: `INSERT 0 3`。

- [ ] **Step 3：套用 Migration 42 並重跑一次**

```powershell
psql -v ON_ERROR_STOP=1 -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -f backend\migration\42_split_mechanical_trace_numbers.sql
psql -v ON_ERROR_STOP=1 -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -f backend\migration\42_split_mechanical_trace_numbers.sql
```

Expected:

- 第一次成功建立新表、核對資料並移除舊表。
- 第二次輸出「Migration 42 已完成」notice 並成功結束。
- 任一次錯誤都不得繼續後續驗證。

- [ ] **Step 4：查核資料表、fixture、約束、索引、連續序號與重複值**

```powershell
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT to_regclass('\"機械性質批次\"') AS old_table, to_regclass('\"機械性質追溯編號\"') AS new_table;"
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT trace.\"類型\", array_agg(trace.\"序號\" ORDER BY trace.\"序號\") AS sequences, array_agg(trace.\"編號\" ORDER BY trace.\"序號\") AS numbers FROM \"機械性質追溯編號\" AS trace JOIN \"機械性質檢驗\" AS test ON test.\"識別碼\" = trace.\"機械性質檢驗_ID\" WHERE test.\"產品尺寸\" = 'MIGRATION42-TEST' GROUP BY trace.\"類型\" ORDER BY trace.\"類型\";"
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT conname FROM pg_constraint WHERE conrelid = '\"機械性質追溯編號\"'::regclass ORDER BY conname;"
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT indexname FROM pg_indexes WHERE tablename = '機械性質追溯編號' ORDER BY indexname;"
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT \"機械性質檢驗_ID\", \"類型\", MIN(\"序號\"), MAX(\"序號\"), COUNT(*), COUNT(DISTINCT \"序號\") FROM \"機械性質追溯編號\" GROUP BY 1, 2 HAVING MIN(\"序號\") <> 1 OR MAX(\"序號\") <> COUNT(*) OR COUNT(DISTINCT \"序號\") <> COUNT(*);"
psql -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "SELECT \"機械性質檢驗_ID\", \"類型\", \"編號\", COUNT(*) FROM \"機械性質追溯編號\" GROUP BY 1, 2, 3 HAVING COUNT(*) > 1;"
psql -v ON_ERROR_STOP=1 -h $qcDbHost -p $qcDbPort -U $qcDbUser -d $qcDbName -c "DELETE FROM \"機械性質檢驗\" WHERE \"產品尺寸\" = 'MIGRATION42-TEST' AND \"材質\" = 'MIGRATION42-TEST';"
Remove-Item Env:PGPASSWORD
```

Expected:

- `old_table` 為 null，`new_table` 為 `機械性質追溯編號`。
- fixture 只有 `擠製編號 → {E-M42}` 與
  `T4爐號 → {T4-M42-01,T4-M42-02}`，兩種類型皆從序號 1 連續排列。
- 五個命名約束與 `ix_mech_trace_test_id` 存在。
- 最後兩個異常查詢回傳 0 rows。
- 清理 fixture 回傳 `DELETE 1`。

- [ ] **Step 5：執行全後端測試**

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: 全部 PASS。

- [ ] **Step 6：執行全前端與 repository 衛生檢查**

Run:

```powershell
Set-Location src_frontend
npm test -- --run
npm run lint -- --max-warnings=0
npm run build
Set-Location ..
git diff --check
git status --short
```

Expected:

- tests、lint、build 全部成功。
- `git diff --check` 無輸出。
- status 只允許已知 `.codex-remote-attachments/`；若有其他檔案，先判斷來源，不可一律加入提交。

- [ ] **Step 7：啟動服務並完成瀏覽器端到端驗收**

依 repository 既有方式啟動 venv 後端與前端；若目前已有服務，先確認監聽程序屬於本 workspace，不依程序名稱強制終止。

端到端步驟：

1. 開啟機械性質檢驗清單。
2. 新增一筆檢驗，填入擠製編號 `E2E-E001`。
3. 填入 T4爐號 `E2E-T4-01`，再獨立新增 `E2E-T4-02`。
4. 儲存並重新載入明細，確認一筆擠製編號、兩筆 T4爐號都存在。
5. 編輯該筆資料，只刪除 `E2E-T4-01`，確認擠製編號不受影響。
6. 儲存後回清單，確認擠製摘要為 `E2E-E001`、T4爐號摘要為 `E2E-T4-02`。
7. 重新打開明細，確認畫面沒有任何成對關係或舊稱「爐具編號」。
8. 刪除 E2E 測試資料，避免污染正式檢驗紀錄。

Expected: 全流程成功，瀏覽器 console 無本次功能產生的 error 或 warning。

- [ ] **Step 8：最終提交檢查**

```powershell
git status --short --branch
git log --oneline --decorate -8
git diff master...HEAD --stat
git diff master...HEAD --check
```

Expected: 功能分支包含本計畫所列的繁體中文 commits，無漏提交功能檔案；`.codex-remote-attachments/` 仍未追蹤且未進入任何 commit。

若 Task 7 驗證過程沒有修正檔案，不新增「空驗證 commit」。若修正本功能 defect，先補失敗測試，再用相符的繁體中文 commit 訊息提交並重跑受影響驗證。

---

## 完成定義

- Migration 42 在 PostgreSQL 首次執行與安全重跑都成功，新舊集合雙向一致且舊表只在驗證後移除。
- ORM、service、route、前端型別都以獨立兩清單為主契約。
- 新／舊 payload 分流明確；混用、間斷序號、空白、過長、型別錯誤與同類型重複均回傳 400。
- detail 的 deprecated `batches` 不產生假配對；新前端完全不讀 `batches`。
- 表單可以獨立新增／刪除，桌面並排、窄螢幕堆疊，重複錯誤具備 ARIA 關聯且會阻擋儲存。
- 清單分別顯示擠製編號與 T4爐號摘要，T4/T6 欄位使用完整「溫度/時間」標題。
- 後端全測試、前端全測試、lint 0 warnings、build、diff check 與瀏覽器端到端驗收全部通過。
