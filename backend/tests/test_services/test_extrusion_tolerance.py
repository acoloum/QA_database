from backend.services.extrusion_tolerance_service import ExtrusionToleranceService


def test_extrusion_tolerance_search_clamps_page_size(app, db_session):
    with app.app_context():
        result = ExtrusionToleranceService.search({"page_size": "5000"})
        assert result["page_size"] == 100
