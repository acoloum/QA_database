from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import pyodbc
import decimal
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from io import BytesIO
import openpyxl
import jwt
import hashlib
from functools import wraps

app = Flask(__name__)
CORS(app)

SECRET_KEY = 'your-secret-key-change-this-in-production'
TOKEN_EXPIRATION_HOURS = 24

# ==================================================
# DB Connection
# ==================================================
def get_db_connection():
    return pyodbc.connect(
        r"Driver={ODBC Driver 18 for SQL Server};"
        r"Server=localhost\SQLEXPRESS;"
        r"Database=品保資料庫;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
        r"TrustServerCertificate=yes;"
        r"Connection Timeout=30;"
    )

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token(user_id, username):
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': '缺少認證 Token'}), 401
        if token.startswith('Bearer '):
            token = token[7:]
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': '無效或過期的 Token'}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated

def handle_db_error(e):
    error_msg = str(e)
    if 'FOREIGN KEY' in error_msg:
        return '關聯資料錯誤：請檢查相關資料是否存在'
    elif 'UNIQUE' in error_msg:
        return '資料重複：此筆資料已存在'
    elif 'NOT NULL' in error_msg:
        return '資料不完整：請填寫所有必填欄位'
    elif 'timeout' in error_msg.lower():
        return '資料庫連線逾時，請稍後再試'
    elif 'connection' in error_msg.lower():
        return '資料庫連線失敗，請檢查連線設定'
    elif 'login' in error_msg.lower() or 'authentication' in error_msg.lower():
        return '資料庫認證失敗，請檢查連線設定'
    else:
        return f'資料庫錯誤：{error_msg}'

def format_value(val):
    if isinstance(val, (decimal.Decimal, float)):
        return float(val)
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d')
    if isinstance(val, bytes):
        return val.hex()
    if isinstance(val, str):
        return val.strip()
    return val if val is not None else ""

def validate_date_format(date_str):
    if not date_str:
        return True
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_inspection_data(data):
    errors = []
    if not data.get('檢驗日期'):
        errors.append("檢驗日期為必填欄位")
    elif not validate_date_format(data.get('檢驗日期')):
        errors.append("檢驗日期格式錯誤，應為 YYYY-MM-DD")
    if not data.get('廠商中文名稱'):
        errors.append("廠商為必填欄位")
    if not data.get('材質'):
        errors.append("材質為必填欄位")
    if not data.get('檢驗規格'):
        errors.append("檢驗規格為必填欄位")
    if not data.get('檢驗人員姓名'):
        errors.append("檢驗人員為必填欄位")
    return errors

def validate_patrol_data(data):
    errors = []
    if not data.get('檢驗日期'):
        errors.append("檢驗日期為必填欄位")
    elif not validate_date_format(data.get('檢驗日期')):
        errors.append("檢驗日期格式錯誤，應為 YYYY-MM-DD")
    if not data.get('機台'):
        errors.append("機台為必填欄位")
    if not data.get('檢驗人員'):
        errors.append("檢驗人員為必填欄位")
    if not data.get('details') or len(data.get('details', [])) == 0:
        errors.append("明細資料為必填欄位")
    return errors

# ==================================================
# 【共用】下拉選單 API（前端會用）
# ==================================================
@app.route('/api/inspectors')
def get_inspectors():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 姓名 FROM dbo.品管人員")
        return jsonify([{"name": r[0].strip()} for r in cursor.fetchall()])
    finally:
        conn.close()


@app.route('/api/vendors')
def get_vendors():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 廠商名稱 FROM dbo.廠商資料")
        return jsonify([{"name": r[0].strip()} for r in cursor.fetchall()])
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】SPC
# ==================================================
@app.route('/api/stats')
def get_stats():
    field = request.args.get('field', '').strip()
    if not field:
        return jsonify({"labels": [], "avgs": [], "ranges": []})

    params, where = [], []
    args = request.args

    if args.get('vendor'):   where.append("V.廠商名稱 LIKE ?"); params.append(f"%{args['vendor']}%")
    if args.get('material'): where.append("T1.材質 LIKE ?");     params.append(f"%{args['material']}%")
    if args.get('spec'):     where.append("T1.檢驗規格 LIKE ?"); params.append(f"%{args['spec']}%")
    if args.get('start_date'): where.append("T1.檢驗日期 >= ?"); params.append(args['start_date'])
    if args.get('end_date'):   where.append("T1.檢驗日期 <= ?"); params.append(args['end_date'])

    is_minmax = field in ['外徑', '內徑', '厚度']
    cols = []
    for i in range(1, 6):
        if is_minmax:
            cols += [f"[{field}{i}-min]", f"[{field}{i}-max]"]
        else:
            cols.append(f"[{field}{i}]")

    where_sql = " AND ".join(where)
    if where_sql:
        where_sql = "AND " + where_sql

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T1.識別碼, T1.檢驗日期, {','.join(cols)}
            FROM dbo.出貨檢驗數據 T1
            LEFT JOIN dbo.廠商資料 V ON T1.廠商名稱 = V.識別碼
            WHERE 1=1 {where_sql}
            ORDER BY T1.檢驗日期
        """
        rows = cursor.execute(sql, params).fetchall()

        labels, avgs, ranges = [], [], []
        for r in rows:
            vals = [float(v) for v in r[2:] if v not in (None, "")]
            if not vals:
                continue
            labels.append(f"{r[1].strftime('%m/%d')}(#{r[0]})")
            avgs.append(np.mean(vals))
            ranges.append(np.ptp(vals))

        if not avgs:
            return jsonify({"labels": [], "avgs": [], "ranges": []})

        xbar = np.mean(avgs)
        rbar = np.mean(ranges)

        return jsonify({
            "labels": labels,
            "avgs": avgs,
            "ranges": ranges,
            "x_cl": xbar,
            "x_ucl": xbar + 0.577 * rbar,
            "x_lcl": xbar - 0.577 * rbar,
            "r_cl": rbar,
            "r_ucl": 2.114 * rbar
        })
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】資料查詢
# ==================================================
@app.route('/api/data')
def get_data():
    page = int(request.args.get('page', 1))
    page_size = 15

    params, where = [], []
    args = request.args

    if args.get('vendor'):   where.append("V.廠商名稱 LIKE ?"); params.append(f"%{args['vendor']}%")
    if args.get('material'): where.append("T1.材質 LIKE ?");     params.append(f"%{args['material']}%")
    if args.get('spec'):     where.append("T1.檢驗規格 LIKE ?"); params.append(f"%{args['spec']}%")
    if args.get('start_date'): where.append("T1.檢驗日期 >= ?"); params.append(args['start_date'])
    if args.get('end_date'):   where.append("T1.檢驗日期 <= ?"); params.append(args['end_date'])

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"SELECT COUNT(*) FROM dbo.出貨檢驗數據 T1 LEFT JOIN dbo.廠商資料 V ON T1.廠商名稱 = V.識別碼 {where_sql}",
        params
    )
    total = cursor.fetchone()[0]

    sql = f"""
        SELECT T1.*, P.姓名 AS 檢驗人員姓名, V.廠商名稱 AS 廠商中文名稱
        FROM dbo.出貨檢驗數據 T1
        LEFT JOIN dbo.品管人員 P ON T1.檢驗人員 = P.識別碼
        LEFT JOIN dbo.廠商資料 V ON T1.廠商名稱 = V.識別碼
        {where_sql}
        ORDER BY T1.識別碼 DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    rows = cursor.execute(
        sql,
        params + [(page - 1) * page_size, page_size]
    ).fetchall()

    cols = [c[0] for c in cursor.description]
    conn.close()

    return jsonify({
        "data": [{cols[i]: format_value(r[i]) for i in range(len(cols))} for r in rows],
        "total_pages": (total + page_size - 1) // page_size
    })
# ==================================================
# 【出貨檢驗】新增 / 更新
# ==================================================
@app.route('/api/add', methods=['POST'])
@app.route('/api/update', methods=['POST'])
def save_data():
    data = request.json
    is_update = request.path.endswith('update')

    errors = validate_inspection_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢驗人員 ID
        cursor.execute(
            "SELECT 識別碼 FROM dbo.品管人員 WHERE 姓名 = ?",
            (data.get('檢驗人員姓名'),)
        )
        p = cursor.fetchone()
        p_id = p[0] if p else None

        # 廠商 ID
        cursor.execute(
            "SELECT 識別碼 FROM dbo.廠商資料 WHERE 廠商名稱 = ?",
            (data.get('廠商中文名稱'),)
        )
        v = cursor.fetchone()
        v_id = v[0] if v else None

        fields = ["檢驗日期", "檢驗人員", "廠商名稱", "檢驗規格", "材質", "訂單號碼"]
        params = [
            data.get('檢驗日期'),
            p_id,
            v_id,
            data.get('檢驗規格'),
            data.get('材質'),
            data.get('訂單號碼')
        ]

        for i in range(1, 6):
            for col in ['外徑', '內徑', '厚度']:
                fields += [f"[{col}{i}-min]", f"[{col}{i}-max]"]
                params += [data.get(f'{col}{i}-min'), data.get(f'{col}{i}-max')]

            for col in ['同心度', '長度', '硬度', '真直度']:
                fields.append(f"[{col}{i}]")
                params.append(data.get(f'{col}{i}'))

        if is_update:
            set_sql = ", ".join([f"{f}=?" for f in fields])
            params.append(data.get('識別碼'))
            cursor.execute(
                f"UPDATE dbo.出貨檢驗數據 SET {set_sql} WHERE 識別碼 = ?",
                params
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO dbo.出貨檢驗數據
                ({','.join(fields)})
                VALUES ({','.join(['?' for _ in params])})
                """,
                params
            )

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】刪除
# ==================================================
@app.route('/api/delete', methods=['POST'])
def delete_data():
    data = request.json
    record_id = data.get('id')
    if not record_id:
        return jsonify({"error": "缺少記錄 ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM dbo.出貨檢驗數據 WHERE 識別碼 = ?", (record_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】匯入 Excel
# ==================================================
@app.route('/api/import', methods=['POST', 'OPTIONS'])
def shipping_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    try:
        df = pd.read_excel(file, engine='openpyxl')
        print("Excel 列名:", df.columns.tolist())
        print("Excel 第一行:", df.iloc[0].to_dict() if len(df) > 0 else "空表格")
    except Exception as e:
        return jsonify({"error": f"檔案讀取失敗: {str(e)}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success_count = 0
        for row_num, row in enumerate(df.iterrows()):
            main_data = row[1].to_dict()
            for key, value in main_data.items():
                if pd.isna(value):
                    main_data[key] = None

            # 查找檢驗人員 ID
            inspector_name = main_data.get('檢驗人員')
            if pd.isna(inspector_name) or str(inspector_name).strip() == "":
                inspector_id = None
            else:
                inspector_str = str(inspector_name).strip()
                cursor.execute("SELECT 識別碼 FROM dbo.品管人員 WHERE 姓名 = ?", (inspector_str,))
                i = cursor.fetchone()
                inspector_id = i[0] if i else None
                if not inspector_id:
                    cursor.execute("SELECT 姓名 FROM dbo.品管人員")
                    all_inspectors = [row[0] for row in cursor.fetchall()]
                    display_row_num = row_num + 2
                    return jsonify({"error": f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_str}'(repr: {repr(inspector_str)})。資料庫中的檢驗人員有：{', '.join(all_inspectors)}"}), 400

            # 查找廠商 ID
            vendor_name = main_data.get('廠商名稱')
            if pd.isna(vendor_name) or str(vendor_name).strip() == "":
                vendor_id = None
            else:
                vendor_str = str(vendor_name).strip()
                cursor.execute("SELECT 識別碼 FROM dbo.廠商資料 WHERE 廠商名稱 = ?", (vendor_str,))
                v = cursor.fetchone()
                vendor_id = v[0] if v else None

            # 檢查必要欄位
            display_row_num = row_num + 2
            if not inspector_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'"}), 400
            if not vendor_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到廠商 '{vendor_name}'"}), 400

            # 準備插入數據
            fields = ["檢驗日期", "檢驗人員", "廠商名稱", "檢驗規格", "材質", "訂單號碼"]
            params = [
                main_data.get('檢驗日期'),
                inspector_id,
                vendor_id,
                main_data.get('檢驗規格'),
                main_data.get('材質'),
                main_data.get('訂單號碼')
            ]

            for i in range(1, 6):
                for col in ['外徑', '內徑', '厚度']:
                    fields += [f"[{col}{i}-min]", f"[{col}{i}-max]"]
                    params += [main_data.get(f'{col}{i}-min'), main_data.get(f'{col}{i}-max')]

                for col in ['同心度', '長度', '硬度', '真直度']:
                    fields.append(f"[{col}{i}]")
                    params.append(main_data.get(f'{col}{i}'))

            cursor.execute(
                f"""
                INSERT INTO dbo.出貨檢驗數據
                ({','.join(fields)})
                VALUES ({','.join(['?' for _ in params])})
                """,
                params
            )

            success_count += 1

        conn.commit()
        return jsonify({"success": True, "message": f"匯入成功，共 {success_count} 筆資料"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】Options
# ==================================================
@app.route('/api/patrol/options')
def patrol_options():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        return jsonify({
            "machines":   [{"id": r[0], "name": r[1].strip()} for r in cursor.execute("SELECT 識別碼, 擠壓機編號 FROM dbo.擠壓機台")],
            "operators":  [{"id": r[0], "name": r[1].strip()} for r in cursor.execute("SELECT 識別碼, 員工姓名 FROM dbo.擠壓人員")],
            "inspectors": [{"id": r[0], "name": r[1].strip()} for r in cursor.execute("SELECT 識別碼, 姓名 FROM dbo.品管人員")],
            "customers":  [{"id": r[0], "name": r[1].strip()} for r in cursor.execute("SELECT 識別碼, 廠商名稱 FROM dbo.廠商資料")]
        })
    finally:
        conn.close()

# ==================================================
# 【出貨檢驗】匯出 Excel
# ==================================================
@app.route('/api/export/excel')
def export_excel():
    args = request.args
    params = []
    where = []

    if args.get('vendor'):   where.append("V.廠商名稱 LIKE ?"); params.append(f"%{args['vendor']}%")
    if args.get('material'): where.append("T1.材質 LIKE ?");     params.append(f"%{args['material']}%")
    if args.get('spec'):     where.append("T1.檢驗規格 LIKE ?"); params.append(f"%{args['spec']}%")
    if args.get('start_date'): where.append("T1.檢驗日期 >= ?"); params.append(args['start_date'])
    if args.get('end_date'):   where.append("T1.檢驗日期 <= ?"); params.append(args['end_date'])

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT T1.識別碼, T1.檢驗日期, T1.材質, T1.檢驗規格, T1.訂單號碼,
                   P.姓名 AS 檢驗人員, V.廠商名稱 AS 廠商名稱,
                   T1.[外徑1-min], T1.[外徑1-max], T1.[外徑2-min], T1.[外徑2-max],
                   T1.[外徑3-min], T1.[外徑3-max], T1.[外徑4-min], T1.[外徑4-max],
                   T1.[外徑5-min], T1.[外徑5-max],
                   T1.[內徑1-min], T1.[內徑1-max], T1.[內徑2-min], T1.[內徑2-max],
                   T1.[內徑3-min], T1.[內徑3-max], T1.[內徑4-min], T1.[內徑4-max],
                   T1.[內徑5-min], T1.[內徑5-max],
                   T1.[厚度1-min], T1.[厚度1-max], T1.[厚度2-min], T1.[厚度2-max],
                   T1.[厚度3-min], T1.[厚度3-max], T1.[厚度4-min], T1.[厚度4-max],
                   T1.[厚度5-min], T1.[厚度5-max],
                   T1.同心度1, T1.同心度2, T1.同心度3, T1.同心度4, T1.同心度5,
                   T1.長度1, T1.長度2, T1.長度3, T1.長度4, T1.長度5,
                   T1.硬度1, T1.硬度2, T1.硬度3, T1.硬度4, T1.硬度5,
                   T1.真直度1, T1.真直度2, T1.真直度3, T1.真直度4, T1.真直度5
              FROM dbo.出貨檢驗數據 T1
              LEFT JOIN dbo.品管人員 P ON T1.檢驗人員 = P.識別碼
              LEFT JOIN dbo.廠商資料 V ON T1.廠商名稱 = V.識別碼
              {where_sql}
              ORDER BY T1.識別碼 DESC
          """
        sql = sql.format(where_sql=where_sql)
        rows = cursor.execute(sql, params).fetchall()

        if not rows:
            df = pd.DataFrame(columns=['識別碼', '檢驗日期', '材質', '檢驗規格', '訂單號碼', '檢驗人員', '廠商名稱',
                                         '外徑1-最小', '外徑1-最大', '外徑2-最小', '外徑2-最大',
                                         '外徑3-最小', '外徑3-最大', '外徑4-最小', '外徑4-最大', '外徑5-最小', '外徑5-最大',
                                         '內徑1-最小', '內徑1-最大', '內徑2-最小', '內徑2-最大',
                                         '內徑3-最小', '內徑3-最大', '內徑4-最小', '內徑4-最大', '內徑5-最小', '內徑5-最大',
                                         '厚度1-最小', '厚度1-最大', '厚度2-最小', '厚度2-最大',
                                         '厚度3-最小', '厚度3-最大', '厚度4-最小', '厚度4-最大', '厚度5-最小', '厚度5-最大',
                                         '同心度1', '同心度2', '同心度3', '同心度4', '同心度5',
                                         '長度1', '長度2', '長度3', '長度4', '長度5',
                                         '硬度1', '硬度2', '硬度3', '硬度4', '硬度5',
                                         '真直度1', '真直度2', '真直度3', '真直度4', '真直度5'])
        else:
            cols = [c[0] for c in cursor.description]
            df = pd.DataFrame([list(r) for r in rows], columns=cols)

            if '檢驗日期' in df.columns:
                df['檢驗日期'] = pd.to_datetime(df['檢驗日期']).dt.strftime('%Y-%m-%d')

        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        return send_file(output, as_attachment=True, download_name='出貨檢驗數據.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    finally:
        conn.close()

# ==================================================
# 【巡檢】SPC
# ==================================================
@app.route('/api/patrol/spc')
def patrol_spc():
    item = request.args.get('item', '厚度')
    pos = request.args.get('pos', '')

    params = [item]
    where = ["T2.測量項目 = ?"]

    args = request.args
    if pos: where.append("T2.測量位置 = ?"); params.append(pos)
    if args.get('s_date'): where.append("T1.檢驗日期 >= ?"); params.append(args['s_date'])
    if args.get('e_date'): where.append("T1.檢驗日期 <= ?"); params.append(args['e_date'])
    if args.get('m_id'):   where.append("T1.機台 = ?");       params.append(args['m_id'])
    if args.get('op_id'):  where.append("T1.主機手 = ?");     params.append(args['op_id'])
    if args.get('mat'):    where.append("T1.材質 LIKE ?");    params.append(f"%{args['mat']}%")
    if args.get('spec'):   where.append("T1.擠壓規格 LIKE ?");params.append(f"%{args['spec']}%")

    where_sql = "WHERE " + " AND ".join(where)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T1.檢驗日期, T2.主檔ID, T2.組別, T2.最小值, T2.最大值
            FROM dbo.巡檢主檔 T1
            JOIN dbo.巡檢子檔 T2 ON T1.識別碼 = T2.主檔ID
            {where_sql}
            ORDER BY T1.識別碼 DESC
        """
        rows = cursor.execute(sql, params).fetchall()
        if not rows:
            return jsonify({"labels": [], "avgs": [], "ranges": []})

        groups = {}
        for r in rows:
            key = f"{r[0].strftime('%m/%d')}-#{r[1]}-G{r[2]}"
            groups.setdefault(key, []).extend([float(r[3]), float(r[4])])

        labels = list(groups.keys())[::-1]
        avgs = [np.mean(groups[k]) for k in labels]
        ranges = [np.ptp(groups[k]) for k in labels]

        A2, D4, D3 = 0.483, 2.004, 0
        x_cl, r_cl = np.mean(avgs), np.mean(ranges)

        return jsonify({
            "labels": labels,
            "avgs": avgs,
            "ranges": ranges,
            "x_cl": x_cl,
            "x_ucl": x_cl + A2 * r_cl,
            "x_lcl": x_cl - A2 * r_cl,
            "r_cl": r_cl,
            "r_ucl": D4 * r_cl,
            "r_lcl": D3 * r_cl
        })
    finally:
        conn.close()
# ==================================================
# 【巡檢】明細資料
# ==================================================
@app.route('/api/patrol/detail/<int:id>')
def patrol_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 主檔
        row = cursor.execute(
            "SELECT * FROM dbo.巡檢主檔 WHERE 識別碼 = ?",
            (id,)
        ).fetchone()

        if not row:
            return jsonify({"error": "資料不存在"}), 404

        cols = [c[0] for c in cursor.description]
        main = {c: format_value(v) for c, v in zip(cols, row)}

        # 子檔
        details = []
        for r in cursor.execute(
            """
            SELECT 組別, 測量項目, 測量位置, 最小值, 最大值
            FROM dbo.巡檢子檔
            WHERE 主檔ID = ?
            """,
            (id,)
        ).fetchall():
            group_val = str(r[0]).strip()
            # 如果組別是數字，轉換為 "第X組" 格式
            if group_val.isdigit():
                group_val = f"第{group_val}組"
            details.append({
                "group": group_val,
                "item": r[1].strip(),
                "pos": r[2].strip(),
                "min": float(r[3]) if r[3] is not None else None,
                "max": float(r[4]) if r[4] is not None else None
            })

        return jsonify({
            "main": main,
            "details": details
        })
    finally:
        conn.close()

# ==================================================
# 【巡檢】新增（支援 CORS preflight）
# ==================================================
@app.route('/api/patrol/add', methods=['POST', 'OPTIONS'])
def patrol_add():
    if request.method == 'OPTIONS':
        # 預檢請求，直接回 200
        return '', 200

    data = request.json
    errors = validate_patrol_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 新增主檔
        cursor.execute(
            """
            INSERT INTO dbo.巡檢主檔 (檢驗日期, 機台, 主機手, 檢驗人員, 材質, 擠壓規格, 客戶名稱, 原料批號)
            OUTPUT INSERTED.識別碼
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get('檢驗日期'),
                data.get('機台'),
                data.get('主機手'),
                data.get('檢驗人員'),
                data.get('材質'),
                data.get('擠壓規格'),
                data.get('客戶名稱'),
                data.get('原料批號')
            )
        )
        patrol_id = cursor.fetchone()[0]

        # 新增子檔
        for d in data.get('details', []):
            # 將 "第1組" 轉換為數字 "1"
            group_raw = str(d.get('group', '')).strip()
            group_val = group_raw.replace('第', '').replace('組', '')
            group_val = group_val if group_val.isdigit() else 1

            cursor.execute(
                """
                INSERT INTO dbo.巡檢子檔
                (主檔ID, 組別, 測量項目, 測量位置, 最小值, 最大值)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    patrol_id,
                    group_val,
                    d.get('item'),
                    d.get('pos'),
                    d.get('min'),
                    d.get('max')
                )
            )

        conn.commit()
        return jsonify({"success": True, "id": patrol_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】更新
# ==================================================
@app.route('/api/patrol/update', methods=['POST'])
def patrol_update():
    data = request.json
    record_id = data.get('id')
    if not record_id:
        return jsonify({"error": "缺少記錄 ID"}), 400

    errors = validate_patrol_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE dbo.巡檢主檔
            SET 檢驗日期=?, 機台=?, 主機手=?, 檢驗人員=?, 材質=?, 擠壓規格=?, 客戶名稱=?, 原料批號=?
            WHERE 識別碼=?
            """,
            (
                data.get('檢驗日期'),
                data.get('機台'),
                data.get('主機手'),
                data.get('檢驗人員'),
                data.get('材質'),
                data.get('擠壓規格'),
                data.get('客戶名稱'),
                data.get('原料批號'),
                record_id
            )
        )

        cursor.execute("DELETE FROM dbo.巡檢子檔 WHERE 主檔ID = ?", (record_id,))

        for d in data.get('details', []):
            # 將 "第1組" 轉換為數字 "1"
            group_raw = str(d.get('group', '')).strip()
            group_val = group_raw.replace('第', '').replace('組', '')
            group_val = group_val if group_val.isdigit() else 1

            cursor.execute(
                """
                INSERT INTO dbo.巡檢子檔
                (主檔ID, 組別, 測量項目, 測量位置, 最小值, 最大值)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    group_val,
                    d.get('item'),
                    d.get('pos'),
                    d.get('min'),
                    d.get('max')
                )
            )

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】刪除
# ==================================================
@app.route('/api/patrol/delete', methods=['POST'])
def patrol_delete():
    data = request.json
    record_id = data.get('id')
    if not record_id:
        return jsonify({"error": "缺少記錄 ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM dbo.巡檢子檔 WHERE 主檔ID = ?", (record_id,))
        cursor.execute("DELETE FROM dbo.巡檢主檔 WHERE 識別碼 = ?", (record_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【巡檢】歷史記錄
# ==================================================
@app.route('/api/patrol/history')
@auth_required
def patrol_history():
    args = request.args
    params = []
    where = []

    if args.get('s_date'): where.append("T.檢驗日期 >= ?"); params.append(args['s_date'])
    if args.get('e_date'): where.append("T.檢驗日期 <= ?"); params.append(args['e_date'])
    if args.get('m_id'):   where.append("T.機台 = ?");       params.append(args['m_id'])
    if args.get('op_id'):  where.append("T.主機手 = ?");     params.append(args['op_id'])
    if args.get('mat'):    where.append("T.材質 LIKE ?");    params.append(f"%{args['mat']}%")
    if args.get('spec'):   where.append("T.擠壓規格 LIKE ?");params.append(f"%{args['spec']}%")

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T.識別碼, T.檢驗日期, M.擠壓機編號, OP.員工姓名, T.材質, T.擠壓規格
            FROM dbo.巡檢主檔 T
            LEFT JOIN dbo.擠壓機台 M ON T.機台 = M.識別碼
            LEFT JOIN dbo.擠壓人員 OP ON T.主機手 = OP.識別碼
            {where_sql}
            ORDER BY T.識別碼 DESC
        """
        cursor.execute(sql, params)
        data = []
        for row in cursor.fetchall():
            date_value = row[1]
            if date_value:
                if hasattr(date_value, 'strftime'):
                    date_str = date_value.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_value).split()[0]
            else:
                date_str = ''
            data.append({
                'id': row[0],
                'date': date_str,
                'm_name': row[2],
                'op_name': row[3],
                'mat': row[4],
                'spec': row[5]
            })
        return jsonify({"data": data})
    finally:
        conn.close()

# ==================================================
# 【巡檢】匯出 Excel
# ==================================================
@app.route('/api/patrol/export')
def patrol_export():
    args = request.args
    params, where = []

    if args.get('s_date'): where.append("T.檢驗日期 >= ?"); params.append(args['s_date'])
    if args.get('e_date'): where.append("T.檢驗日期 <= ?"); params.append(args['e_date'])
    if args.get('m_id'):   where.append("T.機台 = ?");       params.append(args['m_id'])
    if args.get('op_id'):  where.append("T.主機手 = ?");     params.append(args['op_id'])
    if args.get('mat'):    where.append("T.材質 LIKE ?");    params.append(f"%{args['mat']}%")
    if args.get('spec'):   where.append("T.擠壓規格 LIKE ?");params.append(f"%{args['spec']}%")

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = f"""
            SELECT T.識別碼, T.檢驗日期, M.擠壓機編號, OP.員工姓名,
                   T.材質, T.擠壓規格, C.廠商名稱, T.原料批號, P.姓名
            FROM dbo.巡檢主檔 T
            LEFT JOIN dbo.擠壓機台 M ON T.機台 = M.識別碼
            LEFT JOIN dbo.擠壓人員 OP ON T.主機手 = OP.識別碼
            LEFT JOIN dbo.品管人員 P ON T.檢驗人員 = P.識別碼
            LEFT JOIN dbo.廠商資料 C ON T.客戶名稱 = C.識別碼
            {where_sql}
            ORDER BY T.識別碼 DESC
        """
        rows = cursor.execute(sql, params).fetchall()

        if not rows:
            df = pd.DataFrame(columns=['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員'])
        else:
            export_data = []
            for row in rows:
                record_id = row[0]
                main_data = list(row)

                cursor.execute(
                    """
                    SELECT 組別, 測量項目, 測量位置, 最小值, 最大值
                    FROM dbo.巡檢子檔
                    WHERE 主檔ID = ?
                    ORDER BY 組別, 測量項目, 測量位置
                    """,
                    (record_id,)
                )
                details = cursor.fetchall()

                measurements = {}
                for d in details:
                    group_raw = str(d[0]).strip()
                    group_name = group_raw if "組" in group_raw else f"第{group_raw}組"
                    item = str(d[1]).strip() if d[1] else ""
                    pos = str(d[2]).strip() if d[2] else ""

                    try:
                        min_val = float(d[3]) if d[3] is not None and d[3] != "" else ""
                        max_val = float(d[4]) if d[4] is not None and d[4] != "" else ""
                    except (ValueError, TypeError):
                        min_val = ""
                        max_val = ""

                    key = f"{group_name}_{item}_{pos}"
                    measurements[key] = {"min": min_val, "max": max_val}

                unique_groups = []
                for d in details:
                    group_raw = str(d[0]).strip()
                    group_name = group_raw if "組" in group_raw else f"第{group_raw}組"
                    if group_name not in unique_groups:
                        unique_groups.append(group_name)

                if not unique_groups:
                    unique_groups = ["第1組"]

                for group in unique_groups:
                    group_name = group
                    row_data = main_data.copy()

                    for item in ["外徑", "內徑", "厚度"]:
                        for pos in ["前段", "中段", "後段"]:
                            key = f"{group_name}_{item}_{pos}"
                            min_val = measurements.get(key, {}).get("min", "")
                            max_val = measurements.get(key, {}).get("max", "")
                            row_data.append(min_val)
                            row_data.append(max_val)

                    export_data.append(row_data)

            cols = ['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員']
            for _ in unique_groups:
                cols.extend([
                    "外徑前段最小", "外徑前段最大",
                    "外徑中段最小", "外徑中段最大",
                    "外徑後段最小", "外徑後段最大",
                    "內徑前段最小", "內徑前段最大",
                    "內徑中段最小", "內徑中段最大",
                    "內徑後段最小", "內徑後段最大",
                    "厚度前段最小", "厚度前段最大",
                    "厚度中段最小", "厚度中段最大",
                    "厚度後段最小", "厚度後段最大"
                ])

            df = pd.DataFrame(export_data, columns=cols)

        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        return send_file(output, as_attachment=True, download_name='巡檢數據.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    finally:
        conn.close()

# ==================================================
# 【巡檢】匯入 Excel
# ==================================================
@app.route('/api/patrol/import', methods=['POST', 'OPTIONS'])
def patrol_import():
    if request.method == 'OPTIONS':
        return '', 200

    if 'file' not in request.files:
        return jsonify({"error": "沒有上傳檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400

    try:
        df = pd.read_excel(file, engine='openpyxl')
    except Exception as e:
        return jsonify({"error": f"檔案讀取失敗: {str(e)}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success_count = 0
        for row_num, row in enumerate(df.iterrows()):
            main_data = row[1].to_dict()

            # 查找機台 ID
            machine_name = main_data.get('擠壓機編號')
            if pd.isna(machine_name) or str(machine_name).strip() == "":
                machine_id = None
            else:
                machine_str = str(machine_name).strip()
                cursor.execute("SELECT 識別碼 FROM dbo.擠壓機台 WHERE 擠壓機編號 = ?", (machine_str,))
                m = cursor.fetchone()
                machine_id = m[0] if m else None

            # 查找員工 ID
            operator_name = main_data.get('員工姓名')
            if pd.isna(operator_name) or str(operator_name).strip() == "":
                operator_id = None
            else:
                operator_str = str(operator_name).strip()
                cursor.execute("SELECT 識別碼 FROM dbo.擠壓人員 WHERE 員工姓名 = ?", (operator_str,))
                o = cursor.fetchone()
                operator_id = o[0] if o else None

            # 查找客戶 ID
            customer_name = main_data.get('客戶名稱')
            if pd.isna(customer_name) or str(customer_name).strip() == "":
                customer_id = None
            else:
                customer_str = str(customer_name).strip()
                cursor.execute("SELECT 識別碼 FROM dbo.廠商資料 WHERE 廠商名稱 = ?", (customer_str,))
                c = cursor.fetchone()
                customer_id = c[0] if c else None

            # 查找檢驗人員 ID
            inspector_name = main_data.get('檢驗人員')
            if pd.isna(inspector_name) or str(inspector_name).strip() == "":
                inspector_id = None
            else:
                inspector_str = str(inspector_name).strip()
                cursor.execute("SELECT 識別碼 FROM dbo.品管人員 WHERE 姓名 = ?", (inspector_str,))
                i = cursor.fetchone()
                inspector_id = i[0] if i else None

            # 檢查必要欄位
            display_row_num = row_num + 2
            if not machine_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到機台 '{machine_name}'"}), 400
            if not operator_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到員工 '{operator_name}'"}), 400
            if not inspector_id:
                return jsonify({"error": f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'"}), 400

            cursor.execute(
                """
                INSERT INTO dbo.巡檢主檔
                (檢驗日期, 機台, 主機手, 材質, 擠壓規格, 客戶名稱, 原料批號, 檢驗人員)
                OUTPUT INSERTED.識別碼
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    main_data.get('檢驗日期'),
                    machine_id,
                    operator_id,
                    main_data.get('材質'),
                    main_data.get('擠壓規格'),
                    customer_id,
                    main_data.get('原料批號'),
                    inspector_id
                )
            )
            patrol_id = cursor.fetchone()[0]

            measurement_cols = [
                ("外徑前段最小", "外徑", "前段", "min"),
                ("外徑前段最大", "外徑", "前段", "max"),
                ("外徑中段最小", "外徑", "中段", "min"),
                ("外徑中段最大", "外徑", "中段", "max"),
                ("外徑後段最小", "外徑", "後段", "min"),
                ("外徑後段最大", "外徑", "後段", "max"),
                ("內徑前段最小", "內徑", "前段", "min"),
                ("內徑前段最大", "內徑", "前段", "max"),
                ("內徑中段最小", "內徑", "中段", "min"),
                ("內徑中段最大", "內徑", "中段", "max"),
                ("內徑後段最小", "內徑", "後段", "min"),
                ("內徑後段最大", "內徑", "後段", "max"),
                ("厚度前段最小", "厚度", "前段", "min"),
                ("厚度前段最大", "厚度", "前段", "max"),
                ("厚度中段最小", "厚度", "中段", "min"),
                ("厚度中段最大", "厚度", "中段", "max"),
                ("厚度後段最小", "厚度", "後段", "min"),
                ("厚度後段最大", "厚度", "後段", "max")
            ]

            measurements = {}
            for col_name, item, pos, min_max in measurement_cols:
                val = main_data.get(col_name)
                if pd.isna(val) == False and str(val).strip() != "":
                    key = f"{item}_{pos}"
                    if key not in measurements:
                        measurements[key] = {"min": "", "max": ""}
                    measurements[key][min_max] = str(val)

            for key, vals in measurements.items():
                item, pos = key.split("_")
                min_val = vals["min"]
                max_val = vals["max"]

                if min_val == "" and max_val == "":
                    continue

                min_val = float(min_val) if min_val != "" else None
                max_val = float(max_val) if max_val != "" else None

                cursor.execute(
                    """
                    INSERT INTO dbo.巡檢子檔
                    (主檔ID, 組別, 測量項目, 測量位置, 最小值, 最大值)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (patrol_id, "1", item, pos, min_val, max_val)
                )

            success_count += 1

        conn.commit()
        return jsonify({"success": True, "message": f"匯入成功，共 {success_count} 筆資料"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【認證】登入
# ==================================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 識別碼, 密碼, 是否啟用 FROM dbo.使用者 WHERE 使用者名稱 = ?",
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
        return jsonify({"token": token, "username": username, "user_id": user_id})
    finally:
        conn.close()

# ==================================================
# 【使用者管理】新增使用者
# ==================================================
@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "使用者名稱和密碼為必填欄位"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 識別碼 FROM dbo.使用者 WHERE 使用者名稱 = ?",
            (username,)
        )
        if cursor.fetchone():
            return jsonify({"error": "使用者名稱已存在"}), 400

        cursor.execute(
            "INSERT INTO dbo.使用者 (使用者名稱, 密碼, 是否啟用) VALUES (?, ?, 1)",
            (username, hash_password(password))
        )
        conn.commit()
        return jsonify({"success": True, "message": "使用者建立成功"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================================================
# 【認證】驗證 Token
# ==================================================
@app.route('/api/verify')
@auth_required
def verify():
    return jsonify({"valid": True, "user": request.user})

# ==================================================
# if __name__ == '__main__':
# ==================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
