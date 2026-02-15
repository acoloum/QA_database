from flask import Blueprint, jsonify, request, send_file
import pandas as pd
from io import BytesIO
from ..utils import (
    get_db_connection,
    format_value,
    auth_required,
    handle_db_error,
    verify_token
)

tolerance_bp = Blueprint('tolerance', __name__)

@tolerance_bp.route('/api/tolerance/search', methods=['GET'])
@auth_required
def search_tolerance():
    """查詢公差資料"""
    args = request.args
    params = []
    where = []
    
    if args.get('material'):
        where.append('T1."材質" LIKE %s')
        params.append(f"%{args['material']}%")
    if args.get('vendor_id'):
        where.append('T1."廠商ID" = %s')
        params.append(args['vendor_id'])
    if args.get('spec'):
        where.append('T1."規格" LIKE %s')
        params.append(f"%{args['spec']}%")
    
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    
    # 分頁參數
    page = int(args.get('page', 1))
    page_size = int(args.get('page_size', 20))
    offset = (page - 1) * page_size
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢總筆數
        count_sql = f"""
            SELECT COUNT(*) 
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            {where_sql}
        """
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]
        
        # 查詢分頁資料
        sql = f"""
            SELECT T1."識別碼", T1."材質", T1."規格", T1."廠商ID", V."廠商名稱",
                   T1."備註", T1."建立日期"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            {where_sql}
            ORDER BY T1."識別碼" DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(sql, params + [page_size, offset])
        cols = [c[0] for c in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            item = dict(zip(cols, row))
            for key, val in item.items():
                item[key] = format_value(val)
            results.append(item)
        
        return jsonify({
            "success": True, 
            "data": results, 
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/<int:id>', methods=['GET'])
@auth_required
def get_tolerance_detail(id):
    """獲取單筆公差詳細資料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢主檔
        cursor.execute("""
            SELECT T1."識別碼", T1."材質", T1."規格", T1."廠商ID", V."廠商名稱",
                   T1."備註", T1."建立日期"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            WHERE T1."識別碼" = %s
        """, (id,))
        
        main_row = cursor.fetchone()
        if not main_row:
            return jsonify({"error": "找不到該筆公差資料"}), 404
        
        cols = [c[0] for c in cursor.description]
        main_data = dict(zip(cols, main_row))
        for key, val in main_data.items():
            main_data[key] = format_value(val)
        
        # 查詢明細
        cursor.execute("""
            SELECT "識別碼", "測量項目", "測量位置", "尺寸下限", "尺寸上限",
                   "公差下限", "公差上限", "標準值", "單位", "備註"
            FROM "廠商公差明細檔"
            WHERE "主檔ID" = %s
            ORDER BY "識別碼"
        """, (id,))
        
        details = []
        cols = [c[0] for c in cursor.description]
        for row in cursor.fetchall():
            detail = dict(zip(cols, row))
            for key, val in detail.items():
                detail[key] = format_value(val)
            details.append(detail)
        
        return jsonify({"success": True, "main": main_data, "details": details})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/add', methods=['POST'])
@auth_required
def add_tolerance():
    """新增公差資料"""
    data = request.json
    
    if not data.get('材質'):
        return jsonify({"error": "材質為必填欄位"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 插入主檔（不記錄建立人員）
        cursor.execute("""
            INSERT INTO "廠商公差主檔" ("材質", "規格", "廠商ID", "備註")
            VALUES (%s, %s, %s, %s)
        """, (
            data.get('材質'),
            data.get('規格'),
            data.get('廠商ID'),
            data.get('備註')
        ))
        
        # 獲取新插入的主檔ID
        cursor.execute('''SELECT lastval()''')
        main_id = cursor.fetchone()[0]
        
        # 插入明細
        details = data.get('details', [])
        for detail in details:
            cursor.execute("""
                INSERT INTO "廠商公差明細檔" 
                ("主檔ID", "測量項目", "測量位置", "尺寸下限", "尺寸上限", "公差下限", "公差上限", "標準值", "單位", "備註")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                main_id,
                detail.get('測量項目'),
                detail.get('測量位置'),
                detail.get('尺寸下限'),
                detail.get('尺寸上限'),
                detail.get('公差下限'),
                detail.get('公差上限'),
                detail.get('標準值'),
                detail.get('單位', 'mm'),
                detail.get('備註')
            ))
        
        conn.commit()
        return jsonify({"success": True, "id": int(main_id)})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/update/<int:id>', methods=['POST'])
@auth_required
def update_tolerance(id):
    """更新公差資料"""
    data = request.json
    
    if not data.get('材質'):
        return jsonify({"error": "材質為必填欄位"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 更新主檔（不記錄更新人員）
        cursor.execute("""
            UPDATE "廠商公差主檔"
            SET "材質" = %s, "規格" = %s, "廠商ID" = %s, "備註" = %s
            WHERE "識別碼" = %s
        """, (
            data.get('材質'),
            data.get('規格'),
            data.get('廠商ID'),
            data.get('備註'),
            id
        ))
        
        # 刪除舊明細
        cursor.execute('''DELETE FROM "廠商公差明細檔" WHERE "主檔ID" = %s''', (id,))
        
        # 插入新明細
        details = data.get('details', [])
        for detail in details:
            cursor.execute("""
                INSERT INTO "廠商公差明細檔" 
                ("主檔ID", "測量項目", "測量位置", "尺寸下限", "尺寸上限", "公差下限", "公差上限", "標準值", "單位", "備註")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id,
                detail.get('測量項目'),
                detail.get('測量位置'),
                detail.get('尺寸下限'),
                detail.get('尺寸上限'),
                detail.get('公差下限'),
                detail.get('公差上限'),
                detail.get('標準值'),
                detail.get('單位', 'mm'),
                detail.get('備註')
            ))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/delete/<int:id>', methods=['POST'])
@auth_required
def delete_tolerance(id):
    """刪除公差資料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''DELETE FROM "廠商公差主檔" WHERE "識別碼" = %s''', (id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/options', methods=['GET'])
def get_tolerance_options():
    """獲取公差選項資料"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 獲取材質列表
        cursor.execute('''SELECT DISTINCT "材質" FROM "廠商公差主檔" WHERE "材質" IS NOT NULL ORDER BY "材質"''')
        materials = [row[0] for row in cursor.fetchall()]
        
        # 獲取規格列表
        cursor.execute('''SELECT DISTINCT "規格" FROM "廠商公差主檔" WHERE "規格" IS NOT NULL AND "規格" != '' ORDER BY "規格"''')
        specs = [row[0] for row in cursor.fetchall()]
        
        # 獲取廠商列表
        cursor.execute('''SELECT "識別碼", "廠商名稱" FROM "廠商資料" ORDER BY "廠商名稱"''')
        vendors = [{"id": row[0], "name": row[1].strip() if row[1] else ""} for row in cursor.fetchall()]
        
        # 獲取測量項目列表
        cursor.execute('''SELECT DISTINCT "測量項目" FROM "廠商公差明細檔" WHERE "測量項目" IS NOT NULL ORDER BY "測量項目"''')
        measure_items = [row[0] for row in cursor.fetchall()]
        
        return jsonify({
            "materials": materials,
            "specs": specs,
            "vendors": vendors,
            "measureItems": measure_items
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/export', methods=['GET'])
@auth_required
def export_tolerance_excel():
    """匯出公差資料為 Excel"""
    args = request.args
    params = []
    where = []
    
    if args.get('material'):
        where.append('T1."材質" LIKE %s')
        params.append(f"%{args['material']}%")
    if args.get('vendor_id'):
        where.append('T1."廠商ID" = %s')
        params.append(args['vendor_id'])
    if args.get('spec'):
        where.append('T1."規格" LIKE %s')
        params.append(f"%{args['spec']}%")
    
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢主檔和明細
        sql = f"""
            SELECT T1."識別碼", T1."材質", T1."規格", V."廠商名稱",
                   T2."測量項目", T2."測量位置", T2."尺寸下限", T2."尺寸上限",
                   T2."公差下限", T2."公差上限", T2."標準值", T2."單位", T2."備註"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            LEFT JOIN "廠商公差明細檔" T2 ON T1."識別碼" = T2."主檔ID"
            {where_sql}
            ORDER BY T1."識別碼", T2."識別碼"
        """
        cursor.execute(sql, params)
        
        rows = cursor.fetchall()
        if not rows:
            df = pd.DataFrame(columns=['識別碼', '材質', '規格', '廠商名稱', '測量項目', '測量位置', 
                                       '尺寸下限', '尺寸上限', '公差下限', '公差上限', '標準值', '單位', '備註'])
        else:
            cols = [c[0] for c in cursor.description]
            df = pd.DataFrame([list(r) for r in rows], columns=cols)
        
        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        
        return send_file(output, as_attachment=True, download_name='廠商公差資料.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()

@tolerance_bp.route('/api/tolerance/check', methods=['GET', 'OPTIONS'])
def check_tolerance():
    """根據廠商+材質+規格查詢公差標準，用於出貨檢驗驗證"""
    # 處理 CORS 預檢請求
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # 驗證認證
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': '缺少認證 Token'}), 401
    if token.startswith('Bearer '):
        token = token[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({'error': '無效或過期的 Token'}), 401
    request.user = payload
    
    vendor_id = request.args.get('vendor_id')
    material = request.args.get('material')
    spec = request.args.get('spec')

    if not material:
        return jsonify({"success": False, "error": "材質為必填參數"}), 400
    
    # 將 vendor_id 轉換為整數（URL 參數是字串）
    if vendor_id:
        try:
            vendor_id = int(vendor_id)
        except (ValueError, TypeError):
            vendor_id = None

    # 正規化規格字串（移除多餘空白、統一分隔符）
    def normalize_spec(spec_str):
        """正規化規格字串"""
        # 資料庫 NULL 值會變成 Python None
        if spec_str is None:
            return ''
        # 字串處理
        if isinstance(spec_str, str):
            spec_str = spec_str.strip().replace('×', '*').replace('x', '*')
            # 移除多餘的*
            while '**' in spec_str:
                spec_str = spec_str.replace('**', '*')
            # 處理字串 "None" 或 "NULL" 
            if spec_str.upper() in ('NONE', 'NULL', ''):
                return ''
            return spec_str.strip()
        return ''

    input_spec = normalize_spec(spec)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查詢所有符合材質條件的公差主檔
        sql = """
            SELECT T1."識別碼", T1."材質", T1."規格", T1."廠商ID", V."廠商名稱"
            FROM "廠商公差主檔" T1
            LEFT JOIN "廠商資料" V ON T1."廠商ID" = V."識別碼"
            WHERE T1."材質" = %s
        """
        params = [material]
        cursor.execute(sql, params)
        candidates = cursor.fetchall()

        # 分類候選記錄
        priority1_exact = []    # 有廠商 + 完全匹配
        priority2_partial = []  # 有廠商 + 規格部分匹配（開頭匹配）
        priority3_similar = []  # 有廠商 + 規格相近（前兩個部分相同）
        priority4_generic = []  # 有廠商 + 無規格
        priority5_exact = []    # 無廠商 + 完全匹配
        priority6_partial = []  # 無廠商 + 規格部分匹配
        priority7_similar = []  # 無廠商 + 規格相近
        priority8_generic = []  # 無廠商 + 無規格

        for row in candidates:
            tol_id = row[0]
            tol_material = row[1]
            tol_spec = row[2]
            tol_vendor_id = row[3]
            tol_vendor_name = row[4]

            normalized_spec = normalize_spec(tol_spec)
            has_vendor = tol_vendor_id is not None
            has_spec = normalized_spec != ''

            # 判斷匹配類型
            # 檢查廠商ID是否匹配（P1-P3需要廠商ID完全相同）
            vendor_match = (tol_vendor_id == vendor_id) if (tol_vendor_id is not None and vendor_id is not None) else False
            
            # 解析規格，判斷是否相近（前綴相同，但長度部分不同）
            def specs_similar(spec1, spec2):
                """判斷兩個規格是否相近（前綴匹配）"""
                if not spec1 or not spec2:
                    return False
                parts1 = spec1.split('*')
                parts2 = spec2.split('*')
                # 前兩個部分相同（外徑和厚度/內徑相同）
                if len(parts1) >= 2 and len(parts2) >= 2:
                    if parts1[0] == parts2[0] and parts1[1] == parts2[1]:
                        return True
                return False
            
            if vendor_match:
                # 廠商匹配的記錄 (Priority 1-4)
                if has_spec and normalized_spec == input_spec:
                    # 完全匹配
                    priority1_exact.append(row)
                elif has_spec and input_spec.startswith(normalized_spec + '*'):
                    # 規格部分匹配（前綴完全匹配）
                    priority2_partial.append(row)
                elif has_spec and specs_similar(normalized_spec, input_spec):
                    # 規格相近（前兩個部分相同）
                    priority3_similar.append(row)
                elif not has_spec:
                    # 無規格（通用）
                    priority4_generic.append(row)
            elif not has_vendor:
                # 無廠商的記錄 (Priority 5-8)
                if has_spec and normalized_spec == input_spec:
                    priority5_exact.append(row)
                elif has_spec and input_spec.startswith(normalized_spec + '*'):
                    priority6_partial.append(row)
                elif has_spec and specs_similar(normalized_spec, input_spec):
                    priority7_similar.append(row)
                elif not has_spec:
                    priority8_generic.append(row)
            else:
                # 有廠商但不匹配的記錄（跳過）
                pass

        # 按優先順序選擇
        matched_row = None
        final_priority = None
        for idx, priority_list in enumerate([priority1_exact, priority2_partial, priority3_similar, priority4_generic,
                                             priority5_exact, priority6_partial, priority7_similar, priority8_generic], 1):
            if priority_list:
                matched_row = priority_list[0]
                final_priority = idx
                break

        if not matched_row:
            return jsonify({"success": True, "found": False, "message": "找不到對應的公差標準"})

        main_row = matched_row
        main_id = main_row[0]
        
        # 查詢明細公差資料
        cursor.execute("""
            SELECT "測量項目", "測量位置", "尺寸下限", "尺寸上限", 
                   "公差下限", "公差上限", "標準值", "單位"
            FROM "廠商公差明細檔"
            WHERE "主檔ID" = %s
            ORDER BY "識別碼"
        """, (main_id,))
        
        details = []
        for row in cursor.fetchall():
            details.append({
                "項目": row[0],
                "位置": row[1] or '',
                "尺寸下限": float(row[2]) if row[2] is not None else None,
                "尺寸上限": float(row[3]) if row[3] is not None else None,
                "公差下限": float(row[4]) if row[4] is not None else None,
                "公差上限": float(row[5]) if row[5] is not None else None,
                "標準值": float(row[6]) if row[6] is not None else None,
                "單位": row[7] or 'mm'
            })
        
        priority_names = {
            1: "相同廠商+相同材質+相同規格(完全匹配)",
            2: "相同廠商+相同材質+規格部分匹配(開頭匹配)",
            3: "相同廠商+相同材質+規格相近(前兩個部分相同)",
            4: "相同廠商+相同材質+無規格(通用)",
            5: "無廠商+相同材質+相同規格(完全匹配)",
            6: "無廠商+相同材質+規格部分匹配",
            7: "無廠商+相同材質+規格相近",
            8: "無廠商+相同材質+無規格"
        }
        
        return jsonify({
            "success": True, 
            "found": True,
            "tolerance_id": main_id,
            "material": main_row[1],
            "spec": main_row[2],
            "vendor_id": main_row[3],
            "vendor_name": main_row[4].strip() if main_row[4] else '',
            "tolerances": details,
            "matched_priority": final_priority,
            "priority_name": priority_names.get(final_priority, "未知")
        })
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
    finally:
        conn.close()
