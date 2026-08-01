import datetime as dt

from backend.models import CorrectiveAction, Role, User
from backend.services.ncmr_service import NCMRService
from backend.utils import generate_token, hash_password


def _auth_headers(db_session, username="route_bounds_user"):
    user = User(username=username, password="pw", role="viewer", is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {"Authorization": f"Bearer {token}"}


def _analytics_headers(db_session, username="analytics_bounds_user"):
    """建立具 analytics.view 權限的角色與使用者，回傳帶 JWT 的 headers。"""
    db_session.add(Role(code='analytics_viewer', name='分析檢視',
                        permissions={'analytics.view': True}))
    user = User(username=username, password=hash_password('pw12345678'),
                role='analytics_viewer', is_active=True)
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


def test_dashboard_stats_rejects_invalid_date_query(client, db_session):
    headers = _auth_headers(db_session, "dashboard_bounds_user")

    response = client.get(
        "/api/dashboard/stats?start=2026-99-99&end=2026-08-31",
        headers=headers,
    )

    assert response.status_code == 400
    assert "start" in response.get_json()["error"]["message"]


def test_dashboard_stats_rejects_start_after_end(client, db_session):
    headers = _auth_headers(db_session, "dashboard_bounds_user2")

    response = client.get(
        "/api/dashboard/stats?start=2026-09-01&end=2026-08-31",
        headers=headers,
    )

    assert response.status_code == 400
    assert "start" in response.get_json()["error"]["message"]


def test_dashboard_stats_rejects_range_over_366_days(client, db_session):
    headers = _auth_headers(db_session, "dashboard_bounds_user3")

    response = client.get(
        "/api/dashboard/stats?start=2025-01-01&end=2026-01-02",
        headers=headers,
    )

    assert response.status_code == 400
    assert "366" in response.get_json()["error"]["message"]


def test_legacy_ncmr_service_keeps_capa_methods():
    assert callable(NCMRService.create_capa)
    assert callable(NCMRService.update_capa)
    assert callable(NCMRService.delete_capa)


def test_quality_analytics_rejects_invalid_date(client, db_session):
    headers = _analytics_headers(db_session, "qa_bounds_user1")

    response = client.get(
        "/api/quality-analytics/pareto?date_from=2026-99-99",
        headers=headers,
    )

    assert response.status_code == 400
    assert "date_from" in response.get_json()["error"]["message"]


def test_quality_analytics_rejects_range_over_366_days(client, db_session):
    headers = _analytics_headers(db_session, "qa_bounds_user2")

    response = client.get(
        "/api/quality-analytics/pareto?date_from=2025-01-01&date_to=2026-01-02",
        headers=headers,
    )

    assert response.status_code == 400
    assert "366" in response.get_json()["error"]["message"]


def test_quality_analytics_top_n_falls_back_on_non_numeric(client, db_session):
    headers = _analytics_headers(db_session, "qa_bounds_user3")

    response = client.get(
        "/api/quality-analytics/defect-trends?top_n=abc",
        headers=headers,
    )

    assert response.status_code == 200


def test_quality_analytics_capa_aging_respects_overdue_limit(client, db_session):
    headers = _analytics_headers(db_session, "qa_bounds_user4")
    db_session.add_all([
        CorrectiveAction(
            eight_d_number=f'CAPA-RB{i}',
            status='進行中',
            created_at=dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc),
            d0_deadline=dt.date(2026, 5, 10),
        )
        for i in range(1, 4)
    ])
    db_session.commit()

    response = client.get(
        "/api/quality-analytics/capa-aging?overdue_limit=2",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.get_json()["data"]["overdue_items"]) == 2
