from backend.models import User
from backend.services.ncmr_service import NCMRService
from backend.utils import generate_token


def _auth_headers(db_session, username="route_bounds_user"):
    user = User(username=username, password="pw", role="viewer", is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {"Authorization": f"Bearer {token}"}


def test_capa_list_rejects_invalid_date_query(client, db_session):
    headers = _auth_headers(db_session, "capa_bounds_user")

    response = client.get("/api/capas?date_from=2026-99-99", headers=headers)

    assert response.status_code == 400
    assert "date_from" in response.get_json()["error"]["message"]


def test_ncmr_list_rejects_invalid_date_query(client, db_session):
    headers = _auth_headers(db_session, "ncmr_bounds_user")

    response = client.get("/api/ncmr?date_to=2026-99-99", headers=headers)

    assert response.status_code == 400
    assert "date_to" in response.get_json()["error"]["message"]


def test_legacy_capa_list_rejects_invalid_date_query(client, db_session):
    headers = _auth_headers(db_session, "legacy_capa_bounds_user")

    response = client.get("/api/capa?date_from=2026-99-99", headers=headers)

    assert response.status_code == 400
    assert "date_from" in response.get_json()["error"]["message"]


def test_pyrometry_corrections_rejects_invalid_numeric_query(client, db_session):
    headers = _auth_headers(db_session, "pyrometry_bounds_user")

    count_response = client.get(
        "/api/pyrometry/corrections?setpoint=520&type=TUS&count=abc",
        headers=headers,
    )
    channel_response = client.get(
        "/api/pyrometry/corrections?setpoint=520&type=TUS&count=1&channels=1,x",
        headers=headers,
    )

    assert count_response.status_code == 400
    assert "count" in count_response.get_json()["error"]["message"]
    assert channel_response.status_code == 400
    assert "channels" in channel_response.get_json()["error"]["message"]


def test_legacy_ncmr_service_keeps_capa_methods():
    assert callable(NCMRService.create_capa)
    assert callable(NCMRService.update_capa)
    assert callable(NCMRService.delete_capa)
