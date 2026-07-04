from backend.services.pyrometry_persistence import build_point_model_kwargs


def test_build_point_model_kwargs_maps_tus_fields():
    kwargs = build_point_model_kwargs(
        test_type="TUS",
        test_id=5,
        point={"點位": "P1", "熱電偶編號": "TC-1", "頻道": "3", "修正值": "-1.2", "最高溫": "181", "最低溫": "179", "最大偏差": "1", "是否合格": False},
    )

    assert kwargs == {
        "test_id": 5,
        "position": "P1",
        "tc_no": "TC-1",
        "channel": 3,
        "correction": -1.2,
        "temp_max": 181.0,
        "temp_min": 179.0,
        "max_dev": 1.0,
        "is_pass": False,
        "excluded": False,
        "exclude_reason": None,
    }


def test_build_point_model_kwargs_maps_sat_fields():
    readings = [{"控制儀表讀值": "180", "校正測試讀值": "181"}]

    kwargs = build_point_model_kwargs(
        test_type="SAT",
        test_id=6,
        point={"控溫區": "Z1", "頻道": "", "readings": readings, "差值": "1", "修正值": "0.5", "偏差": "-0.5"},
    )

    assert kwargs == {
        "test_id": 6,
        "zone": "Z1",
        "channel": None,
        "readings": readings,
        "diff": 1.0,
        "correction": 0.5,
        "deviation": -0.5,
        "is_pass": True,
        "excluded": False,
        "exclude_reason": None,
    }
