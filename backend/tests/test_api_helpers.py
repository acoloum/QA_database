import importlib.util
from pathlib import Path

from sqlalchemy import URL

from backend.errors import APIError
from backend.utils import api_success, api_error


def test_api_success_default(app):
    resp, code = api_success(data={'id': 1})
    assert code == 200
    json_data = resp.get_json()
    assert json_data['success'] is True
    assert json_data['data'] == {'id': 1}
    assert json_data['message'] == '操作成功'


def test_api_success_custom_code(app):
    resp, code = api_success(data={'id': 2}, code=201)
    assert code == 201


def test_api_error_default_keeps_machine_readable_envelope(app):
    """若 api_error 退回字串 error，前端會失去可判定的錯誤碼。"""
    resp, code = api_error('資料不存在')

    assert code == 400
    assert resp.get_json() == {
        'success': False,
        'error': {
            'code': 'VALIDATION_ERROR',
            'message': '資料不存在',
        },
    }


def test_api_error_custom_status_code_and_details_are_not_dropped(app):
    """若 status、業務 code 或空 details 被混用／省略，caller 會走錯分支。"""
    resp, status = api_error(
        '逐列處置無效',
        422,
        code='MSA_IMPORT_RESOLUTION_INVALID',
        details={},
    )

    assert status == 422
    assert resp.get_json() == {
        'success': False,
        'error': {
            'code': 'MSA_IMPORT_RESOLUTION_INVALID',
            'message': '逐列處置無效',
            'details': {},
        },
    }


def test_api_error_to_dict_keeps_empty_details_for_stable_contract():
    """若 APIError 用 truthy 判斷 details，合法空物件會在序列化時消失。"""
    error = APIError(
        '逐列處置無效',
        code='MSA_IMPORT_RESOLUTION_INVALID',
        status_code=422,
        details={},
    )

    assert error.to_dict() == {
        'success': False,
        'error': {
            'code': 'MSA_IMPORT_RESOLUTION_INVALID',
            'message': '逐列處置無效',
            'details': {},
        },
    }


def test_database_url_percent_encodes_reserved_password_characters(monkeypatch):
    """若 DB URI 用字串插值，p@ss:w/rd 會被誤解析成主機或路徑。"""
    monkeypatch.setenv('DB_HOST', 'db.internal')
    monkeypatch.setenv('DB_PORT', '5544')
    monkeypatch.setenv('DB_NAME', 'qc_db')
    monkeypatch.setenv('DB_USER', 'tester')
    monkeypatch.setenv('DB_PASSWORD', 'p@ss:w/rd')
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key')
    config_path = Path(__file__).parents[1] / 'config.py'
    spec = importlib.util.spec_from_file_location('backend_config_db_url_test', config_path)
    assert spec is not None and spec.loader is not None
    isolated_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isolated_config)

    database_url = isolated_config.SQLALCHEMY_DATABASE_URI

    assert isinstance(database_url, URL)
    assert database_url.password == 'p@ss:w/rd'
    assert database_url.render_as_string(hide_password=False) == (
        'postgresql+psycopg2://tester:p%40ss%3Aw%2Frd@db.internal:5544/qc_db'
    )
