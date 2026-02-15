from flask import Blueprint, jsonify
from ..utils import get_db_connection

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/inspectors')
def get_inspectors():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 姓名 FROM "品管人員"''')
        inspectors = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(inspectors)
    finally:
        conn.close()

@admin_bp.route('/api/vendors')
def get_vendors():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 廠商名稱 FROM "廠商資料"''')
        vendors = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(vendors)
    finally:
        conn.close()

@admin_bp.route('/api/machines')
def get_machines():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 擠壓機編號 FROM "擠壓機台"''')
        machines = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(machines)
    finally:
        conn.close()

@admin_bp.route('/api/operators')
def get_operators():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT 識別碼, 員工姓名 FROM "擠壓人員"''')
        operators = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        return jsonify(operators)
    finally:
        conn.close()

@admin_bp.route('/api/materials')
def get_materials():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT DISTINCT "材質" FROM "出貨檢驗數據" WHERE "材質" IS NOT NULL''')
        materials = [row[0].strip() for row in cursor.fetchall()]
        return jsonify(materials)
    finally:
        conn.close()

@admin_bp.route('/api/specs')
def get_specs():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT DISTINCT "檢驗規格" FROM "出貨檢驗數據" WHERE "檢驗規格" IS NOT NULL''')
        specs = [row[0].strip() for row in cursor.fetchall()]
        return jsonify(specs)
    finally:
        conn.close()
