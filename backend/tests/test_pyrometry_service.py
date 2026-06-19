from backend.models import Furnace, Role, User
from backend.services.pyrometry_service import PyrometryService
from backend.utils import generate_token, hash_password


def _make_furnace(db_session):
    furnace = Furnace(
        code="F-01",
        name="測試爐",
        tus_points=1,
        sat_points=1,
        tus_tolerance=10,
        sat_tolerance=5,
        is_active=True,
    )
    db_session.add(furnace)
    db_session.commit()
    return furnace


def _make_user(db_session):
    role = Role(code="pyrometry_editor", name="爐溫編輯", permissions={"pyrometry.edit": True})
    user = User(username="pyrometry-editor", password=hash_password("pw12345678"), role=role.code, is_active=True)
    db_session.add_all([role, user])
    db_session.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {generate_token(user.id, user.username, user.role)}"}


def test_update_test_can_change_type_from_tus_to_sat(db_session):
    furnace = _make_furnace(db_session)
    test_id = PyrometryService.create_test({
        "爐子ID": furnace.id,
        "測試類型": "TUS",
        "測試日期": "2026-06-19",
        "設定溫度": 180,
        "允許公差": 10,
        "points": [{"點位": "TUS-1", "頻道": 1, "最高溫": 181, "最低溫": 179, "修正值": 0}],
    })

    PyrometryService.update_test(test_id, {
        "爐子ID": furnace.id,
        "測試類型": "SAT",
        "測試日期": "2026-06-19",
        "設定溫度": 180,
        "允許公差": 5,
        "points": [{
            "控溫區": "Zone1",
            "頻道": 13,
            "修正值": 0,
            "readings": [{"控制儀表讀值": 180, "校正測試讀值": 181}],
        }],
    })

    detail = PyrometryService.get_test(test_id)
    assert detail["main"]["測試類型"] == "SAT"
    assert detail["tus_points"] == []
    assert len(detail["sat_points"]) == 1


def test_search_tests_clamps_page_size(db_session):
    _make_furnace(db_session)

    result = PyrometryService.search_tests({"page_size": "5000"})

    assert result["page_size"] == 100


def test_create_test_rejects_missing_required_fields(client, db_session):
    user = _make_user(db_session)

    response = client.post("/api/pyrometry/tests", headers=_headers(user), json={})

    assert response.status_code == 400
    assert "error" in response.get_json()
