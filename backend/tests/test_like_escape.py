"""模糊搜尋共用條件 ilike_contains 的測試：使用者輸入的 % 與 _ 必須依字面比對。"""
import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert, select

from backend.utils import escape_like, ilike_contains


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("6063", "6063"),
        ("A_B", "A\\_B"),
        ("100%", "100\\%"),
        ("C:\\x", "C:\\\\x"),
    ],
)
def test_escape_like(raw, expected):
    assert escape_like(raw) == expected


@pytest.fixture
def items():
    metadata = MetaData()
    table = Table("items", metadata, Column("id", Integer, primary_key=True), Column("name", String))
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(table), [
            {"name": "6063_T5"},
            {"name": "6063XT5"},
            {"name": "折扣100%"},
            {"name": "折扣1000"},
            {"name": "Abc"},
        ])
    return engine, table


def _search(items, keyword):
    engine, table = items
    with engine.connect() as connection:
        rows = connection.execute(
            select(table.c.name).where(ilike_contains(table.c.name, keyword)).order_by(table.c.id)
        )
        return [row.name for row in rows]


def test_underscore_is_literal(items):
    # 未跳脫時 _ 代表任意單一字元，會連 6063XT5 一起撈出
    assert _search(items, "3_T") == ["6063_T5"]


def test_percent_is_literal(items):
    assert _search(items, "100%") == ["折扣100%"]


def test_case_insensitive_contains(items):
    assert _search(items, "aB") == ["Abc"]
