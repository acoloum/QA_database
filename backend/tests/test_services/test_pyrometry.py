"""CQI-9 爐溫測試模組測試"""
import pytest
from datetime import date
from backend.models import Furnace
from backend.services.pyrometry_service import PyrometryService


def test_furnace_add_and_get(app, db_session):
    with app.app_context():
        fid = PyrometryService.add_furnace({
            "爐號": "F-01", "名稱": "1號時效爐", "製程類型": "T6時效",
            "TUS點數": 12, "SAT點數": 2, "TUS允許公差": 10, "SAT允許誤差": 5,
        })
        assert fid is not None
        detail = PyrometryService.get_furnace(fid)
        assert detail["爐號"] == "F-01"
        assert detail["TUS點數"] == 12


def test_furnace_list_only_active_by_default(app, db_session):
    with app.app_context():
        a = PyrometryService.add_furnace({"爐號": "F-A", "名稱": "啟用爐"})
        b = PyrometryService.add_furnace({"爐號": "F-B", "名稱": "停用爐"})
        PyrometryService.update_furnace(b, {"爐號": "F-B", "名稱": "停用爐", "啟用狀態": False})
        rows = PyrometryService.list_furnaces(active_only=True)
        codes = [r["爐號"] for r in rows]
        assert "F-A" in codes and "F-B" not in codes


def _auth_header(client, db_session):
    """建立測試使用者並回傳 Authorization header"""
    from backend.models import User
    from backend.utils import hash_password, generate_token
    u = User(username="pyro_tester", password=hash_password("pw"), role="admin")
    db_session.add(u)
    db_session.commit()
    token = generate_token(u.id, u.username, u.role)
    return {"Authorization": f"Bearer {token}"}


def test_furnace_api_crud(client, db_session):
    headers = _auth_header(client, db_session)
    r = client.post("/api/pyrometry/furnaces", json={"爐號": "F-09", "名稱": "退火爐"}, headers=headers)
    assert r.status_code == 200
    fid = r.get_json()["id"]
    r = client.get("/api/pyrometry/furnaces", headers=headers)
    assert any(x["爐號"] == "F-09" for x in r.get_json()["data"])
