from io import BytesIO

from werkzeug.datastructures import FileStorage

from backend.services.attachment_service import AttachmentService


def test_attachment_rejects_extension_with_disallowed_mime(app):
    """副檔名合法但 MIME 不合法時，應拒絕附件上傳。"""
    with app.app_context():
        file = FileStorage(
            stream=BytesIO(b"<script>alert(1)</script>"),
            filename="惡意檔案.pdf",
            content_type="text/html",
        )

        ok, message = AttachmentService._allowed_file(file)

        assert ok is False
        assert "MIME" in message
