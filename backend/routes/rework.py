from flask import Blueprint, jsonify, request
from datetime import datetime
from ..utils import (
    get_db_connection,
    format_value,
    auth_required,
    generate_number
)

rework_bp = Blueprint('rework', __name__)

def generate_rework_number():
    """生成重工單號"""
    return generate_number('RW', "重工申請單", '申請單號')

@rework_bp.route('/api/rework/applications', methods=['GET'])
@auth_required
def get_rework_applications():
    """獲取重工申請列表"""
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    rework_id = request.args.get('rework_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT r.*, 
                   p1."姓名" AS "申請人員姓名",
                   p2."姓名" AS "審核人員姓名",
                   n."不良描述" AS "ncmr_description",
                   n."NCMR單號" AS "ncmr_number",
                   n."廠商" AS "廠商",
                   n."材質" AS "材質",
                   n."產品資訊" AS "產品資訊"
            FROM "重工申請單" r
            LEFT JOIN "品管人員" p1 ON r."申請人員" = p1."識別碼"
            LEFT JOIN "品管人員" p2 ON r."審核人員" = p2."識別碼"
            LEFT JOIN "不合格品單" n ON r."NCMR_ID" = n."識別碼"
        """
        params = []
        conditions = []
        
        if rework_id:
            conditions.append('r."識別碼" = %s')
            params.append(rework_id)
        if status:
            conditions.append('r."狀態" = %s')
            params.append(status)
        if start_date:
            conditions.append('r."申請日期" >= %s')
            params.append(start_date)
        if end_date:
            conditions.append('r."申請日期" <= %s')
            params.append(end_date)
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
            
        sql += ' ORDER BY r."申請日期" DESC'
        
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 使用 format_value() 統一格式化所有值
            for key, val in item.items():
                item[key] = format_value(val)
            data.append(item)
            
        return jsonify(data)
    finally:
        conn.close()

@rework_bp.route('/api/rework/apply', methods=['POST'])
@auth_required
def apply_rework():
    """提交重工申請"""
    data = request.json
    
    # 清理數據 - 移除可能的文件上傳字段
    if isinstance(data, dict):
        data_copy = {}
        for key, value in data.items():
            # 移除任何可能的文件字段或非標準字段
            if key not in ['不合格品管理.png', 'file', 'upload'] and not key.endswith('[]'):
                data_copy[key] = value
        data = data_copy
    
    # 驗證必填欄位
    errors = []
    if not data.get('NCMR_ID'):
        errors.append("NCMR_ID為必填欄位")
    if not data.get('申請人員姓名'):
        errors.append("申請人員為必填欄位")
    if not data.get('重工數量'):
        errors.append("重工數量為必填欄位")
    if not data.get('申請原因'):
        errors.append("申請原因為必填欄位")
        
    # 數值驗證
    try:
        if data.get('重工數量'):
            float(data.get('重工數量'))
    except (ValueError, TypeError):
        errors.append("重工數量必須是數字")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    ncmr_id = data.get('NCMR_ID')
    if not ncmr_id:
        return jsonify({"error": "NCMR_ID 為必填"}), 400
    try:
        ncmr_id = int(ncmr_id)
    except (ValueError, TypeError):
        return jsonify({"error": "NCMR_ID 必須是數字"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取申請人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('申請人員姓名'),)
        )
        applicant = cursor.fetchone()
        if not applicant:
            return jsonify({"error": "找不到申請人員"}), 400
        applicant_id = applicant[0]
        
        # 獲取完整NCMR資訊
        cursor.execute(
            """
            SELECT "識別碼", "NCMR單號", "判定結果", "狀態", "不良描述", "產品資訊", "材質", "廠商"
            FROM "不合格品單" 
            WHERE "識別碼" = %s
            """,
            (ncmr_id,)
        )
        ncmr = cursor.fetchone()
        if not ncmr:
            return jsonify({"error": "找不到對應的NCMR記錄"}), 400
            
        ncmr_db_id, ncmr_number, determination, ncmr_status, bad_desc, product_info, material, vendor = ncmr
        if product_info is None:
            product_info = ''
        
        rework_number = generate_rework_number()
            
        sql = """
            INSERT INTO "重工申請單" 
            ("NCMR_ID", "申請單號", "申請人員", "部門", "緊急程度", "產品資訊", "批號", 
             "重工數量", "申請原因", "預計完成日期", "狀態")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '申請中')
            RETURNING "識別碼";
        """
        expected_date = data.get('預計完成日期')
        if expected_date == '':
            expected_date = None
            
        cursor.execute(sql, (
            ncmr_id,
            rework_number,
            applicant_id,
            data.get('部門', ''),
            data.get('緊急程度', '普通'),
            product_info,
            data.get('批號', ''),
            data.get('重工數量'),
            data.get('申請原因'),
            expected_date
        ))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "無法取得產生的重工單 ID"}), 500
        rework_id = row[0]
        
        # 自動更新NCMR狀態為轉重工
        cursor.execute(
            '''UPDATE "不合格品單" SET "狀態" = '轉重工' WHERE "識別碼" = %s''',
            (ncmr_id,)
        )
        
        conn.commit()
        return jsonify({"success": True, "rework_id": rework_id, "ncmr_number": ncmr_number})
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"資料庫執行錯誤: {str(e)}"}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/application/<int:rework_id>', methods=['PUT'])
@auth_required
def update_rework_application(rework_id):
    """更新重工申請單"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查申請單是否存在
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "識別碼" = %s''',
            (rework_id,)
        )
        if not cursor.fetchone():
            return jsonify({"error": "找不到重工申請單"}), 404
        
        fields = []
        values = []
        
        field_mapping = {
            '部門': '部門',
            '緊急程度': '緊急程度',
            '廠商': '廠商',
            '材質': '材質',
            '產品資訊': '產品資訊',
            '批號': '批號',
            '重工數量': '重工數量',
            '申請原因': '申請原因',
            '預計完成日期': '預計完成日期'
        }
        
        for key, db_field in field_mapping.items():
            if key in data:
                fields.append(f'"{db_field}" = %s')
                # 處理空日期
                if key == '預計完成日期' and data[key] == '':
                    values.append(None)
                else:
                    values.append(data[key])
        
        if not fields:
            return jsonify({"error": "沒有要更新的欄位"}), 400
        
        sql = f'UPDATE "重工申請單" SET {", ".join(fields)} WHERE "識別碼" = %s'
        values.append(rework_id)
        
        cursor.execute(sql, values)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/approve', methods=['POST'])
@auth_required
def approve_rework():
    """審核重工申請"""
    data = request.json
    rework_id = data.get('rework_id')
    action = data.get('action')  # 'approve' 或 'reject'
    opinion = data.get('opinion', '')
    reviewer_name = data.get('審核人員姓名')
    
    if not rework_id or not action or not reviewer_name:
        return jsonify({"error": "缺少必要參數"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        reviewer_id = None
        if reviewer_name:
            # 嘗試獲取審核人員ID，如果不存在則設為 NULL
            cursor.execute(
                '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
                (reviewer_name,)
            )
            reviewer = cursor.fetchone()
            if reviewer:
                reviewer_id = reviewer[0]
        
        # 更新審核狀態
        if action == '核准':
            new_status = '已核准'
        elif action == '拒絕':
            new_status = '已拒絕'
        else:
            return jsonify({"error": "無效的審核動作"}), 400
            
        sql = """
            UPDATE "重工申請單" 
            SET 審核狀態 = %s, 審核人員 = %s, 審核時間 = CURRENT_TIMESTAMP, 
                審核意見 = %s, 狀態 = %s
            WHERE 識別碼 = %s
        """
        cursor.execute(sql, (new_status, reviewer_id, opinion, new_status, rework_id))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/executions', methods=['GET'])
@auth_required
def get_rework_executions():
    """獲取重工執行記錄"""
    rework_id = request.args.get('rework_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        rework_db_id = None
        if rework_id:
            try:
                rework_db_id = int(rework_id)
            except ValueError:
                cursor.execute(
                    '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
                    (rework_id,)
                )
                result = cursor.fetchone()
                if result:
                    rework_db_id = result[0]
        
        sql = """
            SELECT e."識別碼", e."重工單號", e."執行部門", e."負責人員", e."協同人員",
                   e."開始時間", e."預計完成時間", e."實際完成時間", e."使用設備",
                   e."重工方式", e."SOP編號", e."耗材記錄", e."完成數量", e."不良數量",
                   e."良率", e."執行狀況", e."異常狀況", e."執行人員",
                   p1."姓名" AS 負責人員姓名,
                   p2."姓名" AS 執行人員姓名
            FROM "重工執行記錄" e
            LEFT JOIN "品管人員" p1 ON e."負責人員" = p1."識別碼"
            LEFT JOIN "品管人員" p2 ON e."執行人員" = p2."識別碼"
        """
        params = []
        if rework_db_id:
            sql += ' WHERE e."重工單號" = %s'
            params.append(rework_db_id)
            
        sql += ' ORDER BY e."識別碼" DESC'
        
        cursor.execute(sql, params or [])
        cols = [c[0] for c in cursor.description]
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 格式化日期
            for date_field in ['開始時間', '預計完成時間', '實際完成時間']:
                if item.get(date_field):
                    item[date_field] = item[date_field].strftime('%Y-%m-%d %H:%M:%S')
            data.append(item)
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/execute', methods=['POST'])
@auth_required
def execute_rework():
    """記錄重工執行"""
    data = request.json
    
    # 驗證必填欄位
    errors = []
    if not data.get('重工單號'):
        errors.append("重工單號為必填欄位")
    if not data.get('負責人員姓名'):
        errors.append("負責人員為必填欄位")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取負責人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('負責人員姓名'),)
        )
        executor = cursor.fetchone()
        if not executor:
            return jsonify({"error": "找不到負責人員"}), 400
        executor_id = executor[0]
        
        sql = """
            INSERT INTO "重工執行記錄" 
            ("重工單號", "執行部門", "負責人員", "協同人員", "開始時間", 
             "預計完成時間", "實際完成時間", "使用設備", "重工方式", "SOP編號", "耗材記錄", 
             "完成數量", "不良數量", "良率", "執行狀況", "異常狀況", "執行人員")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        start_time = data.get('開始時間')
        if start_time:
            start_time = start_time.replace('T', ' ')
            
        end_time = data.get('預計完成時間')
        if end_time:
            end_time = end_time.replace('T', ' ')
            
        actual_end_time = data.get('實際完成時間')
        if actual_end_time:
            actual_end_time = actual_end_time.replace('T', ' ')
        
        # 計算良率
        complete_qty = float(data.get('完成數量', 0) or 0)
        defect_qty = float(data.get('不良數量', 0) or 0)
        yield_rate = None
        if complete_qty > 0:
            yield_rate = ((complete_qty - defect_qty) / complete_qty) * 100

        # 獲取重工申請單的識別碼（INTEGER）
        rework_number = data.get('重工單號')
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
            (rework_number,)
        )
        rework_result = cursor.fetchone()
        if not rework_result:
            return jsonify({"error": "找不到重工申請單"}), 400
        rework_db_id = rework_result[0]

        cursor.execute(sql, (
            rework_db_id,
            data.get('執行部門', ''),
            executor_id,
            data.get('協同人員', ''),
            start_time or None,
            end_time or None,
            actual_end_time or None,
            data.get('使用設備', ''),
            data.get('重工方式', ''),
            data.get('SOP編號', ''),
            data.get('耗材記錄', ''),
            complete_qty,
            defect_qty,
            yield_rate,
            data.get('執行狀況', ''),
            data.get('異常狀況', ''),
            executor_id
        ))
        
        # 更新重工申請單狀態為執行中
        cursor.execute(
            '''UPDATE "重工申請單" SET "狀態" = '執行中' WHERE "識別碼" = %s''',
            (rework_db_id,)
        )
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['GET'])
@auth_required
def get_execution(execution_id):
    """獲取單筆執行記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT e.*, p1."姓名" AS "負責人員姓名", p2."姓名" AS "執行人員姓名"
            FROM "重工執行記錄" e
            LEFT JOIN "品管人員" p1 ON e."負責人員" = p1."識別碼"
            LEFT JOIN "品管人員" p2 ON e."執行人員" = p2."識別碼"
            WHERE e."識別碼" = %s
        """
        cursor.execute(sql, (execution_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到執行記錄"}), 404
        cols = [c[0] for c in cursor.description]
        item = dict(zip(cols, row))
        return jsonify(item)
    finally:
        conn.close()

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['PUT'])
@auth_required
def update_execution(execution_id):
    """更新執行記錄"""
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        fields = []
        values = []
        
        if '負責人員姓名' in data:
            cursor.execute('SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s', (data['負責人員姓名'],))
            result = cursor.fetchone()
            if result:
                fields.append('"負責人員" = %s')
                values.append(result[0])
        
        field_mapping = {
            '執行部門': '執行部門',
            '協同人員': '協同人員',
            '開始時間': '開始時間',
            '預計完成時間': '預計完成時間',
            '實際完成時間': '實際完成時間',
            '使用設備': '使用設備',
            '重工方式': '重工方式',
            'SOP編號': 'SOP編號',
            '耗材記錄': '耗材記錄',
            '完成數量': '完成數量',
            '不良數量': '不良數量',
            '執行狀況': '執行狀況',
            '異常狀況': '異常狀況'
        }
        
        for key, db_field in field_mapping.items():
            if key in data:
                fields.append(f'"{db_field}" = %s')
                values.append(data[key])
        
        if not fields:
            return jsonify({"error": "沒有要更新的欄位"}), 400
        
        sql = f'UPDATE "重工執行記錄" SET {", ".join(fields)} WHERE "識別碼" = %s'
        values.append(execution_id)
        cursor.execute(sql, values)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/execution/<int:execution_id>', methods=['DELETE'])
@auth_required
def delete_execution(execution_id):
    """刪除執行記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM "重工執行記錄" WHERE "識別碼" = %s', (execution_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/inspections', methods=['GET'])
@auth_required
def get_rework_inspections():
    """獲取重工品檢記錄"""
    rework_id = request.args.get('rework_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        rework_db_id = None
        if rework_id:
            try:
                rework_db_id = int(rework_id)
            except ValueError:
                cursor.execute(
                    '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
                    (rework_id,)
                )
                result = cursor.fetchone()
                if result:
                    rework_db_id = result[0]
        
        sql = """
            SELECT i.*, p."姓名" AS "檢驗人員姓名"
            FROM "重工品檢記錄" i
            LEFT JOIN "品管人員" p ON i."檢驗人員" = p."識別碼"
        """
        params = []
        if rework_db_id:
            sql += ' WHERE i."重工單號" = %s'
            params.append(rework_db_id)
            
        sql += ' ORDER BY i."檢驗日期" DESC'
        
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 格式化日期
            if item.get('檢驗日期'):
                item['檢驗日期'] = item['檢驗日期'].strftime('%Y-%m-%d %H:%M:%S')
            if item.get('建立時間'):
                item['建立時間'] = item['建立時間'].strftime('%Y-%m-%d %H:%M:%S')
            data.append(item)
            
        return jsonify(data)
    finally:
        conn.close()

@rework_bp.route('/api/rework/inspect', methods=['POST'])
@auth_required
def inspect_rework():
    """記錄重工品檢"""
    data = request.json
    
    # 驗證必填欄位
    errors = []
    if not data.get('重工單號'):
        errors.append("重工單號為必填欄位")
    if not data.get('檢驗人員姓名'):
        errors.append("檢驗人員為必填欄位")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取重工申請單的識別碼（INTEGER）
        rework_number = data.get('重工單號')
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
            (rework_number,)
        )
        rework_result = cursor.fetchone()
        if not rework_result:
            return jsonify({"error": "找不到重工申請單"}), 400
        rework_db_id = rework_result[0]
        
        # 獲取檢驗人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('檢驗人員姓名'),)
        )
        inspector = cursor.fetchone()
        if not inspector:
            return jsonify({"error": "找不到檢驗人員"}), 400
        inspector_id = inspector[0]
        
        sql = """
            INSERT INTO "重工品檢記錄" 
            ("重工單號", "檢驗日期", "檢驗人員", "檢驗項目", "檢驗標準", "檢驗結果", "不良數量", "檢驗備註")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            rework_db_id,
            data.get('檢驗日期'),
            inspector_id,
            data.get('檢驗項目', ''),
            data.get('檢驗標準', ''),
            data.get('檢驗結果', '合格'),
            data.get('不良數量', 0),
            data.get('檢驗備註', '')
        ))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['GET'])
@auth_required
def get_inspection(inspection_id):
    """獲取單筆品檢記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT i.*, p."姓名" AS "檢驗人員姓名"
            FROM "重工品檢記錄" i
            LEFT JOIN "品管人員" p ON i."檢驗人員" = p."識別碼"
            WHERE i."識別碼" = %s
            """,
            (inspection_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到品檢記錄"}), 404
        
        cols = [c[0] for c in cursor.description]
        item = dict(zip(cols, row))
        
        # 格式化日期
        if item.get('檢驗日期'):
            item['檢驗日期'] = item['檢驗日期'].strftime('%Y-%m-%d')
        
        return jsonify(item)
    finally:
        conn.close()

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['PUT'])
@auth_required
def update_inspection(inspection_id):
    """更新品檢記錄"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取檢驗人員ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('檢驗人員姓名'),)
        )
        inspector = cursor.fetchone()
        if not inspector:
            return jsonify({"error": "找不到檢驗人員"}), 400
        inspector_id = inspector[0]
        
        cursor.execute(
            """
            UPDATE "重工品檢記錄" 
            SET "檢驗日期" = %s, "檢驗人員" = %s, "檢驗項目" = %s, 
                "檢驗標準" = %s, "檢驗結果" = %s, "不良數量" = %s, "檢驗備註" = %s
            WHERE "識別碼" = %s
            """,
            (
                data.get('檢驗日期'),
                inspector_id,
                data.get('檢驗項目', ''),
                data.get('檢驗標準', ''),
                data.get('檢驗結果', '合格'),
                data.get('不良數量', 0),
                data.get('檢驗備註', ''),
                inspection_id
            )
        )
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/inspection/<int:inspection_id>', methods=['DELETE'])
@auth_required
def delete_inspection(inspection_id):
    """刪除品檢記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''DELETE FROM "重工品檢記錄" WHERE "識別碼" = %s''',
            (inspection_id,)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/close', methods=['POST'])
@auth_required
def close_rework():
    """結案重工申請"""
    data = request.json
    rework_id = data.get('rework_id')
    
    if not rework_id:
        return jsonify({"error": "缺少重工單號參數"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查當前狀態
        cursor.execute('''SELECT "狀態" FROM "重工申請單" WHERE "識別碼" = %s''', (rework_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到該重工單"}), 404
            
        current_status = row[0]
        if current_status == '已完成':
            return jsonify({"error": "該重工單已結案"}), 400
            
        # 更新狀態
        cursor.execute(
            """
            UPDATE "重工申請單" 
            SET "狀態" = '已完成', "實際完成日期" = CURRENT_TIMESTAMP
            WHERE "識別碼" = %s
            """,
            (rework_id,)
        )
        
        # 更新 NCMR 狀態為重工已完成
        cursor.execute('''SELECT "NCMR_ID" FROM "重工申請單" WHERE "識別碼" = %s''', (rework_id,))
        ncmr_result = cursor.fetchone()
        if ncmr_result:
            ncmr_id = ncmr_result[0]
            cursor.execute('''UPDATE "不合格品單" SET "狀態" = '重工已完成' WHERE "識別碼" = %s''', (ncmr_id,))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/delete', methods=['POST'])
@auth_required
def delete_rework():
    """刪除重工申請"""
    data = request.json
    rework_id = data.get('rework_id')
    
    if not rework_id:
        return jsonify({"error": "缺少重工單號參數"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 刪除相關的執行記錄
        cursor.execute('''DELETE FROM "重工執行記錄" WHERE "重工單號" = %s''', (rework_id,))
        # 刪除相關的品檢記錄
        cursor.execute('''DELETE FROM "重工品檢記錄" WHERE "重工單號" = %s''', (rework_id,))
        # 刪除相關的成本記錄
        cursor.execute('''DELETE FROM "重工成本分析" WHERE "重工單號" = %s''', (rework_id,))
        # 刪除重工申請單
        cursor.execute('''DELETE FROM "重工申請單" WHERE "識別碼" = %s''', (rework_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/costs', methods=['GET'])
@auth_required
def get_rework_costs():
    """獲取重工成本記錄"""
    rework_id = request.args.get('rework_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        rework_db_id = None
        if rework_id:
            try:
                rework_db_id = int(rework_id)
            except ValueError:
                cursor.execute(
                    '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
                    (rework_id,)
                )
                result = cursor.fetchone()
                if result:
                    rework_db_id = result[0]
        
        sql = """
            SELECT c.*, p."姓名" AS "記錄人員姓名"
            FROM "重工成本分析" c
            LEFT JOIN "品管人員" p ON c."記錄人員" = p."識別碼"
        """
        params = []
        if rework_db_id:
            sql += ' WHERE c."重工單號" = %s'
            params.append(rework_db_id)
            
        sql += ' ORDER BY c."記錄日期" DESC'
        
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        data = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            # 格式化日期
            if item.get('記錄日期'):
                item['記錄日期'] = item['記錄日期'].strftime('%Y-%m-%d %H:%M:%S')
            data.append(item)
            
        return jsonify(data)
    finally:
        conn.close()

@rework_bp.route('/api/rework/cost', methods=['POST'])
@auth_required
def add_rework_cost():
    """新增重工成本記錄"""
    data = request.json
    
    # 驗證必填欄位
    errors = []
    if not data.get('重工單號'):
        errors.append("重工單號為必填欄位")
    if not data.get('成本類型'):
        errors.append("成本類型為必填欄位")
    if not data.get('成本項目'):
        errors.append("成本項目為必填欄位")
        
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取重工申請單的識別碼（INTEGER）
        rework_number = data.get('重工單號')
        cursor.execute(
            '''SELECT "識別碼" FROM "重工申請單" WHERE "申請單號" = %s''',
            (rework_number,)
        )
        rework_result = cursor.fetchone()
        if not rework_result:
            return jsonify({"error": "找不到重工申請單"}), 400
        rework_db_id = rework_result[0]
        
        sql = """
            INSERT INTO "重工成本分析" 
            ("重工單號", "成本類型", "成本項目", "單位成本", "數量", "總成本", 
             "成本幣別", "記錄人員", "備註")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # 獲取記錄人員 ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('記錄人員姓名'),)
        )
        record_person = cursor.fetchone()
        record_person_id = record_person[0] if record_person else None

        cursor.execute(sql, (
            rework_db_id,
            data.get('成本類型'),
            data.get('成本項目'),
            data.get('單位成本', 0),
            data.get('數量', 0),
            data.get('總成本', 0),
            data.get('成本幣別', 'TWD'),
            record_person_id,
            data.get('備註', '')
        ))
        
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['GET'])
@auth_required
def get_cost(cost_id):
    """獲取單筆成本記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT c.*, p."姓名" AS "記錄人員姓名"
            FROM "重工成本分析" c
            LEFT JOIN "品管人員" p ON c."記錄人員" = p."識別碼"
            WHERE c."識別碼" = %s
            """,
            (cost_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "找不到成本記錄"}), 404
        
        cols = [c[0] for c in cursor.description]
        item = dict(zip(cols, row))
        
        # 格式化日期
        if item.get('記錄日期'):
            item['記錄日期'] = item['記錄日期'].strftime('%Y-%m-%d')
        
        return jsonify(item)
    finally:
        conn.close()

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['PUT'])
@auth_required
def update_cost(cost_id):
    """更新成本記錄"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取記錄人員 ID
        cursor.execute(
            '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
            (data.get('記錄人員姓名'),)
        )
        record_person = cursor.fetchone()
        record_person_id = record_person[0] if record_person else None
        
        # 重新計算總成本
        unit_cost = float(data.get('單位成本', 0) or 0)
        qty = float(data.get('數量', 0) or 0)
        total_cost = unit_cost * qty
        
        cursor.execute(
            """
            UPDATE "重工成本分析" 
            SET "成本類型" = %s, "成本項目" = %s, "單位成本" = %s, 
                "數量" = %s, "總成本" = %s, "記錄人員" = %s, "備註" = %s
            WHERE "識別碼" = %s
            """,
            (
                data.get('成本類型'),
                data.get('成本項目'),
                unit_cost,
                qty,
                total_cost,
                record_person_id,
                data.get('備註', ''),
                cost_id
            )
        )
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/cost/<int:cost_id>', methods=['DELETE'])
@auth_required
def delete_cost(cost_id):
    """刪除成本記錄"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''DELETE FROM "重工成本分析" WHERE "識別碼" = %s''',
            (cost_id,)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@rework_bp.route('/api/rework/statistics', methods=['GET'])
@auth_required
def get_rework_statistics():
    """獲取重工統計數據"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        params = []
        where_clause = ""
        
        if start_date:
            where_clause += " AND 申請日期 >= %s"
            params.append(start_date)
        if end_date:
            where_clause += " AND 申請日期 <= %s"
            params.append(end_date)
            
        # 基本統計
        stats = {}
        
        # 申請數量統計
        sql = """
            SELECT 
                COUNT(*) as 總申請數,
                SUM(CASE WHEN 狀態 = '已完成' THEN 1 ELSE 0 END) as 完成數,
                SUM(CASE WHEN 狀態 = '執行中' THEN 1 ELSE 0 END) as 執行中數,
                SUM(CASE WHEN 狀態 = '已核准' THEN 1 ELSE 0 END) as 已核准數,
                SUM(CASE WHEN 審核狀態 = '已拒絕' THEN 1 ELSE 0 END) as 拒絕數,
                SUM(COALESCE(重工數量, 0)) as 總重工數量
            FROM "重工申請單" 
            WHERE 1=1 {where_clause}
        """
        cursor.execute(sql.format(where_clause=where_clause), params)
        
        result = cursor.fetchone()
        if result:
            stats['application_stats'] = {
                'total_applications': result[0],
                'completed': result[1],
                'in_progress': result[2],
                'approved': result[3],
                'rejected': result[4],
                'total_rework_quantity': float(result[5]) if result[5] else 0
            }
        
        sql = """
            SELECT 
                    COUNT(*) as 記錄數,
                    SUM(COALESCE(總成本, 0)) as 總成本,
                    SUM(CASE WHEN 成本類型 = '人工成本' THEN COALESCE(總成本, 0) ELSE 0 END) as 人工成本,
                    SUM(CASE WHEN 成本類型 = '材料成本' THEN COALESCE(總成本, 0) ELSE 0 END) as 材料成本,
                    SUM(CASE WHEN 成本類型 = '設備成本' THEN COALESCE(總成本, 0) ELSE 0 END) as 設備成本
            FROM "重工成本分析" c
            INNER JOIN "重工申請單" r ON c.重工單號 = r.識別碼
            WHERE 1=1 {where_clause}
        """
        cursor.execute(sql.format(where_clause=where_clause), params)

        result = cursor.fetchone()
        if result:
            stats['cost_stats'] = {
                'total_records': result[0],
                'total_cost': float(result[1]) if result[1] else 0,
                'labor_cost': float(result[2]) if result[2] else 0,
                'material_cost': float(result[3]) if result[3] else 0,
                'equipment_cost': float(result[4]) if result[4] else 0
            }
        
        # 部門統計
        sql = """
            SELECT 
                部門,
                COUNT(*) as 申請數,
                SUM(COALESCE(重工數量, 0)) as 重工數量
            FROM "重工申請單" 
            WHERE 1=1 {where_clause}
            GROUP BY 部門
            ORDER BY 申請數 DESC
        """
        cursor.execute(sql.format(where_clause=where_clause), params)
        
        dept_stats = []
        for row in cursor.fetchall():
            dept_stats.append({
                'department': row[0],
                'count': row[1],
                'quantity': float(row[2]) if row[2] else 0
            })
        stats['department_stats'] = dept_stats
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
