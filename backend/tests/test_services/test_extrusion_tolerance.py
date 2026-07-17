from backend.services.extrusion_tolerance_service import ExtrusionToleranceService


def test_extrusion_tolerance_search_clamps_page_size(app, db_session):
    with app.app_context():
        result = ExtrusionToleranceService.search({"page_size": "5000"})
        assert result["page_size"] == 100


def test_extrusion_tolerance_detail_roundtrips_characteristic_class(app, db_session):
    """特性重要度欄位應能透過 add 寫入並經 get_detail 讀出。"""
    with app.app_context():
        data = {
            "材質": "6061-T651",
            "規格": "62.5*2.3",
            "廠商": "",
            "備註": "",
            "details": [{
                "測量項目": "外徑",
                "公差下限": -0.1,
                "公差上限": 0.1,
                "標準值": 62.5,
                "單位": "mm",
                "特性重要度": "主要",
            }],
        }
        new_id = ExtrusionToleranceService.add(data)
        got = ExtrusionToleranceService.get_detail(new_id)
        assert got["details"][0]["特性重要度"] == "主要"
