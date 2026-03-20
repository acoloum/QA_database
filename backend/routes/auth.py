from flask import Blueprint, jsonify, request
from ..extensions import db
from ..models import User
from ..utils import (
    generate_token,
    verify_token,
    generate_csrf_token,
    hash_password,
    verify_password,
    handle_db_error,
    auth_required
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json
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

        # Migrate legacy SHA256 hash to bcrypt on successful login
        if not user.password.startswith('$2b$') and not user.password.startswith('$2a$'):
            user.password = hash_password(password)
            db.session.commit()

        token = generate_token(user.id, user.username)
        return jsonify({
            'token': token,
            'username': user.username,
            'user_id': user.id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            'user_id': payload.get('user_id')
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
def create_user():
    """新增使用者"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    try:
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "使用者名稱已存在"}), 400

        new_user = User(
            username=username,
            password=hash_password(password),
            is_active=1
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "使用者建立成功"})
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        # UNIQUE 衝突 → 400，其他 DB 錯誤 → 500
        if 'UNIQUE' in error_msg or 'unique' in error_msg:
            return jsonify({"error": "使用者名稱已存在"}), 400
        return jsonify({"error": str(e)}), 500

