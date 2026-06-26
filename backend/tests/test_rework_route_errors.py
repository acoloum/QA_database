from backend.routes.rework import rework_error_response


def test_rework_error_response_maps_value_error(app):
    with app.app_context():
        response, status = rework_error_response(ValueError("資料格式錯誤"), context="test")

    assert status == 400
    assert response.get_json() == {"error": "資料格式錯誤"}


def test_rework_error_response_logs_unexpected_error(app):
    with app.app_context():
        response, status = rework_error_response(RuntimeError("資料庫中斷"), context="test")

    assert status == 500
    assert response.get_json() == {"error": "資料庫中斷"}
