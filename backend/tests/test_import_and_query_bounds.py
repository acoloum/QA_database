from datetime import date

import pandas as pd

from backend.models import User
from backend.services.patrol_service import PatrolService
from backend.services.shipping_service import ShippingService
from backend.utils import generate_token


class NamedDummyFile:
    filename = "匯入測試.xlsx"

    def seek(self, *_args):
        return 0


def _auth_header(db_session, username):
    user = User(username=username, password="pw", role="viewer", is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_shipping_import_rejects_excel_with_too_many_rows(app, monkeypatch):
    monkeypatch.setattr(
        "backend.services.shipping_service.pd.read_excel",
        lambda *_args, **_kwargs: pd.DataFrame({"檢驗日期": [date.today()] * 5001}),
    )

    try:
        with app.app_context():
            ShippingService.import_data(NamedDummyFile())
    except ValueError as exc:
        assert "列數超過 5000" in str(exc)
    else:
        raise AssertionError("匯入列數超限時應拒絕檔案")


def test_patrol_import_rejects_excel_with_too_many_columns(app, monkeypatch):
    columns = {f"欄位{i}": [i] for i in range(201)}
    monkeypatch.setattr(
        "backend.services.patrol_service.pd.read_excel",
        lambda *_args, **_kwargs: pd.DataFrame(columns),
    )

    try:
        with app.app_context():
            PatrolService.import_data(NamedDummyFile())
    except ValueError as exc:
        assert "欄位數超過 200" in str(exc)
    else:
        raise AssertionError("匯入欄位數超限時應拒絕檔案")


def test_task_list_rejects_invalid_numeric_and_date_query(client, db_session):
    headers = _auth_header(db_session, "task_query_bounds")

    source_response = client.get("/api/tasks?source_id=abc", headers=headers)
    date_response = client.get("/api/tasks?due_from=2026-99-99", headers=headers)

    assert source_response.status_code == 400
    assert "source_id" in source_response.get_json()["error"]
    assert date_response.status_code == 400
    assert "due_from" in date_response.get_json()["error"]


def test_complaint_list_rejects_invalid_date_query(client, db_session):
    headers = _auth_header(db_session, "complaint_query_bounds")

    response = client.get("/api/complaints?date_from=2026-99-99", headers=headers)

    assert response.status_code == 400
    assert "date_from" in response.get_json()["error"]


def test_shipping_list_uses_default_for_invalid_page(app):
    with app.app_context():
        result = ShippingService.get_list({"page": "abc"})

    assert result["data"] == []
    assert result["total"] == 0
