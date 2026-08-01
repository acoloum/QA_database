from io import BytesIO

from werkzeug.datastructures import FileStorage

from backend.models import Attachment, Role, User
from backend.services.attachment_service import AttachmentService
from backend.utils import generate_token, hash_password


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


def test_attachment_list_requires_entity_view_permission(client, db_session):
    """附件清單不可只靠 entity_type/entity_id 猜測讀取，需具備對應模組檢視權限。"""
    db_session.add(Role(code='attachment_no_capa', name='無 CAPA 權限', permissions={}))
    user = User(
        username='attachment_viewer',
        password=hash_password('pw12345678'),
        role='attachment_no_capa',
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Attachment(
        entity_type='capa',
        entity_id=123,
        file_name='evidence.pdf',
        file_path='uploads/capa/123/evidence.pdf',
        mime_type='application/pdf',
        file_size=10,
        uploaded_by=user.id,
    ))
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    resp = client.get(
        '/api/attachments?entity_type=capa&entity_id=123',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == 403
