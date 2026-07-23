import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import (
    MechanicalMeasurement,
    MechanicalTest,
    MechanicalTraceNumber,
)


def test_create_mechanical_test_with_independent_trace_numbers(db_session):
    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.trace_numbers.extend(
        [
            MechanicalTraceNumber(trace_type="擠製編號", seq=1, number="E001"),
            MechanicalTraceNumber(trace_type="T4爐號", seq=1, number="T4-01"),
            MechanicalTraceNumber(trace_type="T4爐號", seq=2, number="T4-02"),
        ]
    )
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
    test.trace_numbers.extend(
        [
            MechanicalTraceNumber(
                trace_type=trace_type,
                seq=seq,
                number=number,
            )
            for trace_type, seq, number in rows
        ]
    )
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
    db_session,
    trace_type,
    seq,
    number,
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


def test_trace_number_rejects_padded_number(db_session):
    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.trace_numbers.append(
        MechanicalTraceNumber(
            trace_type="擠製編號",
            seq=1,
            number=" E001 ",
        )
    )
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_mechanical_child_foreign_keys_match_cascade_migration():
    trace_number_fk = next(
        iter(
            MechanicalTraceNumber.__table__.columns[
                "機械性質檢驗_ID"
            ].foreign_keys
        )
    )
    measurement_fk = next(
        iter(
            MechanicalMeasurement.__table__.columns[
                "機械性質檢驗_ID"
            ].foreign_keys
        )
    )

    assert trace_number_fk.ondelete == "CASCADE"
    assert measurement_fk.ondelete == "CASCADE"


def test_measurement_unique_constraint(db_session):
    """同一測試中（項目+位置+取樣序）不可重複。"""
    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.measurements.append(
        MechanicalMeasurement(
            item="硬度",
            location="爐門",
            sample_no=1,
            value=70,
        )
    )
    test.measurements.append(
        MechanicalMeasurement(
            item="硬度",
            location="爐門",
            sample_no=1,
            value=71,
        )
    )
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_mechanical_string_lengths_are_explicit():
    assert MechanicalTest.product_size.type.length == 50
    assert MechanicalTest.material.type.length == 50
    assert MechanicalTest.t4_temp_time.type.length == 100
    assert MechanicalTest.t6_temp_time.type.length == 100
