from flask import Blueprint, jsonify, request
from ..utils import (
    get_db_connection,
    generate_token,
    verify_token,
    generate_csrf_token,
    hash_password,
    handle_db_error
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username') or data.get('account')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': '使用者名稱和密碼為必填欄位'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT "識別碼", "密碼", "是否啟用" FROM "使用者" WHERE "使用者名稱" = %s',
            (username,)
        )
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "使用者名稱或密碼錯誤"}), 401
            
        user_id, stored_password, is_active = row
        
        if hash_password(password) != stored_password:
            return jsonify({"error": "使用者名稱或密碼錯誤"}), 401
            
        if not is_active:
             return jsonify({"error": "帳號已被停用"}), 401

        token = generate_token(user_id, username)
        return jsonify({
            'token': token,
            'username': username,
            'user_id': user_id
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

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
def create_user():
    """新增使用者"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT "識別碼" FROM "使用者" WHERE "使用者名稱" = %s''',
            (username,)
        )
        if cursor.fetchone():
            return jsonify({"error": "使用者名稱已存在"}), 400

        cursor.execute(
            '''INSERT INTO "使用者" ("使用者名稱", "密碼", "是否啟用") VALUES (%s, %s, 1)''',
            (username, hash_password(password))
        )
        conn.commit()
        return jsonify({"success": True, "message": "使用者建立成功"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()
