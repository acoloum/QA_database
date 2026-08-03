from backend.routes.rework import rework_error_response


def test_rework_error_response_maps_value_error(app):
    with app.app_context():
        response, status = rework_error_response(ValueError("資料格式錯誤"), context="test")

    assert status == 400
    assert response.get_json() == {
        "success": False,
        "error": {"code": "VALIDATION_ERROR", "message": "資料格式錯誤"},
    }


def test_rework_error_response_returns_fixed_message_for_unexpected_error(app):
    """未預期例外不得回傳內部訊息，必須回傳固定 500 訊息。"""
    with app.app_context():
        response, status = rework_error_response(RuntimeError("資料庫中斷"), context="test")

    assert status == 500
    assert response.get_json() == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "伺服器內部錯誤"},
    }
