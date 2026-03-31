from flask import Blueprint, jsonify, request, current_app
from ..extensions import db, limiter
from ..models import User
from ..utils import (
    generate_token,
    verify_token,
    generate_csrf_token,
    hash_password,
    verify_password,
    handle_db_error,
    auth_required,
    require_admin
)

auth_bp = Blueprint('auth', __name__)

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
        return jsonify({
            'token': token,
            'username': user.username,
            'user_id': user.id,
            'role': user.role
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
        return jsonify({
            'valid': True,
            'username': payload.get('username'),
            'user_id': payload.get('user_id'),
            'role': payload.get('role', 'user')
        })
    else:
        return jsonify({'valid': False, 'error': 'Token 無效或已過期'}), 401

@auth_bp.route('/api/csrf-token', methods=['GET'])
def get_csrf_token_api():
    """取得 CSRF Token"""
    token = generate_csrf_token()
    return jsonify({'csrf_token': token})

@auth_bp.route('/api/users', methods=['POST'])
@auth_required
@require_admin
def create_user():
    """新增使用者（需管理員角色）"""
    data = request.json
    if not data:
        return jsonify({"error": "請求格式錯誤，需要 JSON 資料"}), 400
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    if len(password) < 8:
        return jsonify({"error": "密碼長度至少需要 8 個字元"}), 400

    try:
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "使用者名稱已存在"}), 400

        from sqlalchemy import text as _text
        hashed_pw = hash_password(password)
        new_role = data.get('role', 'user')
        db.session.execute(
            _text('INSERT INTO "使用者" ("使用者名稱", "密碼", "是否啟用", "角色") VALUES (:u, :p, TRUE, :r)'),
            {'u': username, 'p': hashed_pw, 'r': new_role}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "使用者建立成功"})
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        if 'UNIQUE' in error_msg or 'unique' in error_msg:
            return jsonify({"error": "使用者名稱已存在"}), 400
        current_app.logger.exception("Create user error: %s", error_msg)
        return jsonify({"error": "伺服器內部錯誤，請稍後再試"}), 500
