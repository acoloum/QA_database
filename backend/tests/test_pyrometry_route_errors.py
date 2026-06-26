from backend.routes.pyrometry import pyrometry_error_response
from backend.services.pyrometry_service import PyrometryValidationError


def test_pyrometry_error_response_maps_validation_error(app):
    with app.app_context():
        response, status = pyrometry_error_response(PyrometryValidationError("缺少測試日期"))

    assert status == 400
    assert response.get_json() == {"error": "缺少測試日期"}


def test_pyrometry_error_response_uses_configured_value_error_status(app):
    with app.app_context():
        response, status = pyrometry_error_response(ValueError("找不到資料"), value_error_status=404)

    assert status == 404
    assert response.get_json() == {"error": "找不到資料"}
