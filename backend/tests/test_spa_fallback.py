"""前端 SPA 靜態檔服務。"""


def test_missing_hashed_asset_returns_404_not_index_html(client):
    """重建前端後，舊分頁仍會請求舊雜湊檔名。

    若 /assets/* 不存在時仍回 index.html（200, text/html），瀏覽器會報
    「MIME type text/html」或「Failed to fetch dynamically imported module」等難懂錯誤，
    前端也無法分辨是「檔案已過期」。應明確回 404。
    """
    for path in ('/assets/index-stale000.css', '/assets/LoginPage-stale000.js'):
        response = client.get(path)
        assert response.status_code == 404, path
        assert not response.content_type.startswith('text/html'), path
