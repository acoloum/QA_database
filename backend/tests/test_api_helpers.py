import pytest


def test_api_success_default(app):
    with app.app_context():
        from backend.utils import api_success
        resp, code = api_success(data={'id': 1})
        assert code == 200
        json_data = resp.get_json()
        assert json_data['success'] is True
        assert json_data['data'] == {'id': 1}
        assert json_data['message'] == '操作成功'


def test_api_success_custom_code(app):
    with app.app_context():
        from backend.utils import api_success
        resp, code = api_success(data={'id': 2}, code=201)
        assert code == 201


def test_api_error_default(app):
    with app.app_context():
        from backend.utils import api_error
        resp, code = api_error('資料不存在')
        assert code == 400
        json_data = resp.get_json()
        assert json_data['success'] is False
        assert json_data['error'] == '資料不存在'


def test_api_error_custom_code(app):
    with app.app_context():
        from backend.utils import api_error
        resp, code = api_error('未授權', code=403)
        assert code == 403
