import re

import pytest


@pytest.mark.parametrize("supplied", ["含中文", "bad id", "a" * 65])
def test_invalid_or_oversized_correlation_id_is_replaced(client, supplied):
    """若非法或超長追蹤碼原樣反射，header/log 邊界可被污染。"""
    response = client.get(
        "/api/non/existent/route",
        headers={"X-Correlation-ID": supplied},
    )

    generated = response.headers["X-Correlation-ID"]
    assert generated != supplied
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_every_response_has_browser_security_headers(client):
    """若 after_request 漏掛，連錯誤回應也會失去瀏覽器安全防線。"""
    response = client.get("/api/non/existent/route")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
