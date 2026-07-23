from backend.models import MechanicalTest, MechanicalMeasurement


def test_create_mechanical_test_with_children(db_session):
    """主檔可帶批次與量測明細，關聯與級聯刪除正常。"""
    from backend.models import MechanicalBatch

    test = MechanicalTest(
        product_size="36x25.2",
        material="6061-T651",
        t4_temp_time="530/40MIN",
        t6_temp_time="175/6HR",
    )
    test.batches.append(
        MechanicalBatch(seq=1, extrusion_no="010761 D35", furnace_no="011313T42")
    )
    test.measurements.append(
        MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=73.3)
    )
    db_session.add(test)
    db_session.commit()

    loaded = db_session.get(MechanicalTest, test.id)
    assert loaded.product_size == "36x25.2"
    assert len(loaded.batches) == 1
    assert loaded.batches[0].extrusion_no == "010761 D35"
    assert len(loaded.measurements) == 1
    assert loaded.measurements[0].item == "硬度"

    # 級聯刪除
    db_session.delete(loaded)
    db_session.commit()
    assert db_session.query(MechanicalMeasurement).count() == 0
    assert db_session.query(MechanicalBatch).count() == 0


def test_mechanical_child_foreign_keys_match_cascade_migration():
    from backend.models import MechanicalBatch

    batch_fk = next(iter(MechanicalBatch.__table__.columns['機械性質檢驗_ID'].foreign_keys))
    measurement_fk = next(iter(MechanicalMeasurement.__table__.columns['機械性質檢驗_ID'].foreign_keys))

    assert batch_fk.ondelete == "CASCADE"
    assert measurement_fk.ondelete == "CASCADE"


def test_measurement_unique_constraint(db_session):
    """同一測試中（項目+位置+取樣序）不可重複。"""
    import pytest
    from sqlalchemy.exc import IntegrityError

    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.measurements.append(MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=70))
    test.measurements.append(MechanicalMeasurement(item="硬度", location="爐門", sample_no=1, value=71))
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_batch_sequence_constraints(db_session):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from backend.models import MechanicalBatch

    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.batches.extend([
        MechanicalBatch(seq=1),
        MechanicalBatch(seq=1),
    ])
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    test = MechanicalTest(product_size="36x25.2", material="6061-T651")
    test.batches.append(MechanicalBatch(seq=0))
    db_session.add(test)
    with pytest.raises(IntegrityError):
        db_session.commit()
