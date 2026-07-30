import re
from flask import Blueprint, jsonify, request, current_app
from ..extensions import db, limiter
from ..models import User, Role
from ..utils import (
    generate_token,
    verify_token,
    generate_csrf_token,
    hash_password,
    verify_password,
    handle_db_error,
    auth_required,
    require_permission
)

_VALID_ROLES = ('user', 'admin')
_USERNAME_RE = re.compile(r'^[A-Za-z0-9_\-\.]{3,50}$')

auth_bp = Blueprint('auth', __name__)


def _role_is_valid(role_code: str) -> bool:
    """確認角色代碼可用；保留內建角色，同時支援角色表定義的細粒度角色。"""
    if role_code in _VALID_ROLES:
        return True
    return Role.query.filter_by(code=role_code).first() is not None

@auth_bp.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.json
    if not data:
        return jsonify({'error': '請求格式錯誤，需要 JSON 資料'}), 400
    username = data.get('username') or data.get('account')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': '使用者名稱和密碼為必填欄位'}), 400

    try:
        user = User.query.filter_by(username=username).first()

        if not user:
            return jsonify({"error": "使用者名稱或密碼錯誤"}), 401

        if not verify_password(password, user.password):
            return jsonify({"error": "使用者名稱或密碼錯誤"}), 401

        if not user.is_active:
            return jsonify({"error": "帳號已被停用"}), 401

        # 將舊版 SHA256 雜湊在登入成功時升級為 bcrypt
        if not user.password.startswith('$2b$') and not user.password.startswith('$2a$'):
            user.password = hash_password(password)
            db.session.commit()

        token = generate_token(user.id, user.username, user.role)
        role_obj = Role.query.filter_by(code=user.role).first()
        permissions = role_obj.permissions if role_obj else {}
        return jsonify({
            'token': token,
            'username': user.username,
            'user_id': user.id,
            'role': user.role,
            'permissions': permissions
        })
    except Exception as e:
        current_app.logger.exception("Login error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500

@auth_bp.route('/api/verify-token', methods=['GET'])
def verify_token_api():
    """驗證 Token 是否有效"""
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'valid': False, 'error': '缺少 Token'}), 401

    if token.startswith('Bearer '):
        token = token[7:]

    payload = verify_token(token)
    if payload:
        # 從 Role 資料表取得該角色的 permissions
        role_code = payload.get('role', 'user')
        role_obj = Role.query.filter_by(code=role_code).first()
        permissions = role_obj.permissions if role_obj else {}
        return jsonify({
            'valid': True,
            'username': payload.get('username'),
            'user_id': payload.get('user_id'),
            'role': role_code,
            'permissions': permissions,
        })
    else:
        return jsonify({'valid': False, 'error': 'Token 無效或已過期'}), 401

@auth_bp.route('/api/csrf-token', methods=['GET'])
def get_csrf_token_api():
    """取得 CSRF Token"""
    token = generate_csrf_token()
    return jsonify({'csrf_token': token})

@auth_bp.route('/api/roles', methods=['GET'])
@auth_required
@require_permission('user.manage')
def list_roles(current_user):
    """列出所有角色（需 user.manage 權限）"""
    try:
        roles = Role.query.order_by(Role.code).all()
        return jsonify([
            {'code': r.code, 'name': r.name, 'permissions': r.permissions}
            for r in roles
        ])
    except Exception as e:
        current_app.logger.exception("List roles error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@auth_bp.route('/api/users', methods=['GET'])
@auth_required
@require_permission('user.manage')
def list_users(current_user):
    """列出所有使用者（需 user.manage 權限）"""
    try:
        users = User.query.order_by(User.id).all()
        return jsonify([
            {
                'id': u.id,
                'username': u.username,
                'role': u.role,
                'inspector_id': u.inspector_id,
                'is_active': u.is_active,
                'created_at': u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ])
    except Exception as e:
        current_app.logger.exception("List users error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@auth_bp.route('/api/roles/<string:role_code>', methods=['PATCH'])
@auth_required
@require_permission('user.manage')
def update_role_permissions(current_user, role_code):
    """更新角色權限（需 user.manage 權限）"""
    data = request.json
    if not data or 'permissions' not in data:
        return jsonify({"error": "請求格式錯誤，需要 permissions 欄位"}), 400

    permissions = data['permissions']
    if not isinstance(permissions, dict):
        return jsonify({"error": "permissions 必須為物件格式"}), 400

    try:
        role = Role.query.filter_by(code=role_code).first()
        if not role:
            return jsonify({"error": f"角色不存在：{role_code}"}), 404
        role.permissions = permissions
        db.session.commit()
        return jsonify({'code': role.code, 'name': role.name, 'permissions': role.permissions})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update role permissions error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@auth_bp.route('/api/users/<int:user_id>/role', methods=['PUT'])
@auth_required
@require_permission('user.manage')
def update_user_role(current_user, user_id):
    """修改使用者角色（需 user.manage 權限）"""
    data = request.json
    if not data:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400

    new_role = data.get('role')
    if not _role_is_valid(new_role):
        return jsonify({"error": f"角色代碼不存在：{new_role}"}), 400

    # 禁止管理員修改自己的角色，避免意外失去管理員權限
    request_user = getattr(request, 'user', {})
    if request_user.get('user_id') == user_id:
        return jsonify({"error": "無法修改自己的角色"}), 400

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "找不到使用者"}), 404
        user.role = new_role
        db.session.commit()
        return jsonify({"success": True, "message": f"角色已更新為 {new_role}"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update user role error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@auth_bp.route('/api/users/<int:user_id>/active', methods=['PUT'])
@auth_required
@require_permission('user.manage')
def update_user_active(current_user, user_id):
    """啟用／停用使用者帳號（需 user.manage 權限）"""
    data = request.json
    if not data or 'is_active' not in data:
        return jsonify({"error": "請求格式錯誤，需要 is_active 欄位"}), 400

    request_user = getattr(request, 'user', {})
    if request_user.get('user_id') == user_id:
        return jsonify({"error": "無法停用自己的帳號"}), 400

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "找不到使用者"}), 404
        user.is_active = bool(data['is_active'])
        db.session.commit()
        status_text = '啟用' if user.is_active else '停用'
        return jsonify({"success": True, "message": f"帳號已{status_text}"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update user active error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500


@auth_bp.route('/api/users', methods=['POST'])
@auth_required
@require_permission('user.manage')
def create_user(current_user):
    """新增使用者（需 user.manage 權限）"""
    data = request.json
    if not data:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    username = data.get('username', '').strip()
    password = data.get('password', '')
    new_role = data.get('role', 'user')
    inspector_id = data.get('inspector_id')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    if not _USERNAME_RE.match(username):
        return jsonify({"error": "使用者名稱長度需 3–50 字元，僅允許英數字、底線、連字號、點號"}), 400

    if len(password) < 8:
        return jsonify({"error": "密碼長度至少需要 8 個字元"}), 400

    if not _role_is_valid(new_role):
        return jsonify({"error": "角色值無效，請選擇已定義的角色"}), 400

    try:
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "使用者名稱已存在"}), 400

        new_user = User(
            username=username,
            password=hash_password(password),
            role=new_role,
            inspector_id=inspector_id,
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "使用者建立成功"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Create user error: %s", str(e))
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500
