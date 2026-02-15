
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from ..utils import (
    get_db_connection,
    format_value,
    validate_patrol_data,
    handle_db_error
)

class PatrolService:
    @staticmethod
    def get_options():
        """獲取下拉選單選項"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''SELECT "識別碼", "擠壓機編號" FROM "擠壓機台"''')
            machines = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
            
            cursor.execute('''SELECT "識別碼", "員工姓名" FROM "擠壓人員"''')
            operators = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
            
            cursor.execute('''SELECT "識別碼", "姓名" FROM "品管人員"''')
            inspectors = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
            
            cursor.execute('''SELECT "識別碼", "廠商名稱" FROM "廠商資料"''')
            customers = [{"id": r[0], "name": r[1].strip()} for r in cursor.fetchall()]
            
            return {
                "machines": machines,
                "operators": operators,
                "inspectors": inspectors,
                "customers": customers
            }
        finally:
            conn.close()

    @staticmethod
    def get_spc(args):
        """獲取巡檢 SPC 統計數據"""
        item = args.get('item', '厚度')
        pos = args.get('pos', '')
        
        params = [item]
        where = ["T2.測量項目 = %s"]

        if pos: where.append("T2.測量位置 = %s"); params.append(pos)
        if args.get('s_date'): where.append("T1.檢驗日期 >= %s"); params.append(args['s_date'])
        if args.get('e_date'): where.append("T1.檢驗日期 <= %s"); params.append(args['e_date'])
        if args.get('m_id'):   where.append("T1.機台 = %s");       params.append(args['m_id'])
        if args.get('op_id'):  where.append("T1.主機手 = %s");     params.append(args['op_id'])
        if args.get('mat'):    where.append("T1.材質 LIKE %s");    params.append(f"%{args['mat']}%")
        if args.get('spec'):   where.append("T1.擠壓規格 LIKE %s");params.append(f"%{args['spec']}%")

        where_sql = "WHERE " + " AND ".join(where)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = f"""
                SELECT T1."檢驗日期", T2."主檔ID", T2."組別", T2."最小值", T2."最大值"
                FROM "巡檢主檔" T1
                JOIN "巡檢子檔" T2 ON T1."識別碼" = T2."主檔ID"
                {where_sql}
                ORDER BY T1."識別碼" DESC
            """
            rows = cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return {"labels": [], "avgs": [], "ranges": []}

            groups = {}
            for r in rows:
                # 過濾掉 None 值
                val1 = r[3]
                val2 = r[4]
                if val1 is None or val2 is None:
                    continue
                key = f"{r[0].strftime('%m/%d')}-#{r[1]}-G{r[2]}"
                groups.setdefault(key, []).extend([float(val1), float(val2)])

            labels = list(groups.keys())
            avgs = [np.mean(groups[k]) for k in labels]
            ranges = [np.ptp(groups[k]) for k in labels]

            A2, D4, D3 = 0.483, 2.004, 0
            if avgs:
                x_cl, r_cl = np.mean(avgs), np.mean(ranges)
                x_ucl = x_cl + A2 * r_cl
                x_lcl = x_cl - A2 * r_cl
                r_ucl = D4 * r_cl
                r_lcl = D3 * r_cl
            else:
                x_cl = r_cl = x_ucl = x_lcl = r_ucl = r_lcl = 0

            return {
                "labels": labels,
                "avgs": avgs,
                "ranges": ranges,
                "x_cl": x_cl,
                "x_ucl": x_ucl,
                "x_lcl": x_lcl,
                "r_cl": r_cl,
                "r_ucl": r_ucl,
                "r_lcl": r_lcl
            }
        finally:
            conn.close()

    @staticmethod
    def get_detail(id):
        """獲取巡檢詳細資料（主檔+子檔）"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 主檔
            cursor.execute(
                '''SELECT * FROM "巡檢主檔" WHERE "識別碼" = %s''',
                (id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            cols = [c[0] for c in cursor.description]
            main = {c: format_value(v) for c, v in zip(cols, row)}

            # 子檔
            details = []
            cursor.execute(
                """
                SELECT "組別", "測量項目", "測量位置", "最小值", "最大值"
                FROM "巡檢子檔"
                WHERE "主檔ID" = %s
                """,
                (id,)
            )
            for r in cursor.fetchall():
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

            return {
                "main": main,
                "details": details
            }
        finally:
            conn.close()

    @staticmethod
    def add_patrol(data):
        """新增巡檢資料"""
        errors = validate_patrol_data(data)
        if errors:
            raise ValueError(", ".join(errors))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 新增主檔
            cursor.execute(
                """
                INSERT INTO "巡檢主檔" ("檢驗日期", "機台", "主機手", "檢驗人員", "材質", "擠壓規格", "客戶名稱", "原料批號")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING "識別碼"
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
                    INSERT INTO "巡檢子檔"
                    ("主檔ID", "組別", "測量項目", "測量位置", "最小值", "最大值")
                    VALUES (%s, %s, %s, %s, %s, %s)
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
            return patrol_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_patrol(data):
        """更新巡檢資料"""
        record_id = data.get('id')
        if not record_id:
            raise ValueError("缺少記錄 ID")

        errors = validate_patrol_data(data)
        if errors:
            raise ValueError(", ".join(errors))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE "巡檢主檔"
                SET "檢驗日期"=%s, "機台"=%s, "主機手"=%s, "檢驗人員"=%s, "材質"=%s, "擠壓規格"=%s, "客戶名稱"=%s, "原料批號"=%s
                WHERE "識別碼"=%s
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

            cursor.execute('''DELETE FROM "巡檢子檔" WHERE "主檔ID" = %s''', (record_id,))

            for d in data.get('details', []):
                group_raw = str(d.get('group', '')).strip()
                group_val = group_raw.replace('第', '').replace('組', '')
                group_val = group_val if group_val.isdigit() else 1

                cursor.execute(
                    """
                    INSERT INTO "巡檢子檔"
                    ("主檔ID", "組別", "測量項目", "測量位置", "最小值", "最大值")
                    VALUES (%s, %s, %s, %s, %s, %s)
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
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_patrol(record_id):
        """刪除巡檢資料"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''DELETE FROM "巡檢子檔" WHERE "主檔ID" = %s''', (record_id,))
            cursor.execute('''DELETE FROM "巡檢主檔" WHERE "識別碼" = %s''', (record_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_history(args):
        """獲取巡檢歷史列表（分頁）"""
        params = []
        where = []

        if args.get('s_date'): where.append("T.檢驗日期 >= %s"); params.append(args['s_date'])
        if args.get('e_date'): where.append("T.檢驗日期 <= %s"); params.append(args['e_date'])
        if args.get('m_id'):   where.append("T.機台 = %s");       params.append(args['m_id'])
        if args.get('op_id'):  where.append("T.主機手 = %s");     params.append(args['op_id'])
        if args.get('mat'):    where.append("T.材質 LIKE %s");    params.append(f"%{args['mat']}%")
        if args.get('spec'):   where.append("T.擠壓規格 LIKE %s");params.append(f"%{args['spec']}%")

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            page = int(args.get('page', 1))
            per_page = int(args.get('per_page', 20))
            
            # Get total count
            count_sql = f'SELECT COUNT(*) FROM "巡檢主檔" T {where_sql}'
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            total_pages = (total + per_page - 1) // per_page
            
            # Get paginated data
            offset = (page - 1) * per_page
            sql = f"""
                SELECT T.識別碼, T.檢驗日期, M.擠壓機編號, OP.員工姓名, T.材質, T.擠壓規格
                FROM "巡檢主檔" T
                LEFT JOIN "擠壓機台" M ON T.機台 = M.識別碼
                LEFT JOIN "擠壓人員" OP ON T.主機手 = OP.識別碼
                {where_sql}
                ORDER BY T.識別碼 DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, params + [per_page, offset])
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
            return {"data": data, "pages": total_pages, "total": total}
        finally:
            conn.close()

    @staticmethod
    def export_excel(args):
        """匯出巡檢資料 Excel"""
        params, where = [], []

        if args.get('s_date'): where.append("T.檢驗日期 >= %s"); params.append(args['s_date'])
        if args.get('e_date'): where.append("T.檢驗日期 <= %s"); params.append(args['e_date'])
        if args.get('m_id'):   where.append("T.機台 = %s");       params.append(args['m_id'])
        if args.get('op_id'):  where.append("T.主機手 = %s");     params.append(args['op_id'])
        if args.get('mat'):    where.append("T.材質 LIKE %s");    params.append(f"%{args['mat']}%")
        if args.get('spec'):   where.append("T.擠壓規格 LIKE %s");params.append(f"%{args['spec']}%")

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = f"""
                SELECT T.識別碼, T.檢驗日期, M.擠壓機編號, OP.員工姓名,
                       T.材質, T.擠壓規格, C.廠商名稱, T.原料批號, P.姓名
                FROM "巡檢主檔" T
                LEFT JOIN "擠壓機台" M ON T.機台 = M.識別碼
                LEFT JOIN "擠壓人員" OP ON T.主機手 = OP.識別碼
                LEFT JOIN "品管人員" P ON T.檢驗人員 = P.識別碼
                LEFT JOIN "廠商資料" C ON T.客戶名稱 = C.識別碼
                {where_sql}
                ORDER BY T.識別碼 DESC
            """
            rows = cursor.execute(sql, params)
            rows = cursor.fetchall()

            if not rows:
                df = pd.DataFrame(columns=['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員'])
                export_data = [] # defined for consistency
                unique_groups = []
            else:
                export_data = []
                unique_groups = []
                for row in rows:
                    record_id = row[0]
                    main_data = list(row)

                    cursor.execute(
                        """
                        SELECT "組別", "測量項目", "測量位置", "最小值", "最大值"
                        FROM "巡檢子檔"
                        WHERE "主檔ID" = %s
                        ORDER BY "組別", "測量項目", "測量位置"
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

                    # Collect unique groups for headers
                    current_groups = []
                    for d in details:
                        group_raw = str(d[0]).strip()
                        group_name = group_raw if "組" in group_raw else f"第{group_raw}組"
                        if group_name not in current_groups:
                            current_groups.append(group_name)
                    
                    # Merge into global unique groups while preserving order
                    for g in current_groups:
                        if g not in unique_groups:
                            unique_groups.append(g)

                    if not current_groups:
                        current_groups = ["第1組"]
                        if "第1組" not in unique_groups:
                            unique_groups.append("第1組")

                    # We need consistent columns for all rows, but groups might vary per row.
                    # The original code iterated `unique_groups` which seems to accumulate across ALL rows?
                    # No, in original code `unique_groups` was per row, but then `export_data.append`...
                    # Wait, if `unique_groups` varies per row, the DataFrame structure will be messy if we just append list with different lengths?
                    # The original code:
                    # `for group in unique_groups:` (local to row)
                    # `export_data.append(row_data)`
                    # `cols = ...` (defined using `unique_groups` from LAST ROW?)
                    # This looks like a bug in original code if different rows have different groups.
                    # Ideally we should find the max number of groups or union of all groups.
                    # For now, I will mimic the original behavior but fixing the scope issue if any.
                    # Actually, let's just use the groups present in THIS row to flatten it?
                    # But if we want a single table, valid columns must be consistent.
                    # I'll assume standard max 1 group or just handle what's there.
                    # To be safe and consistent with previous "Standard", let's assume "第1組" at least.
                    
                    # Refined approach: accumulate data as dicts then DataFrame constructor handles missing cols
                    row_dict = dict(zip(['識別碼', '檢驗日期', '擠壓機編號', '員工姓名', '材質', '擠壓規格', '廠商名稱', '原料批號', '檢驗人員'], main_data))
                    
                    for group in current_groups:
                        for item in ["外徑", "內徑", "厚度"]:
                            for pos in ["前段", "中段", "後段"]:
                                key = f"{group}_{item}_{pos}"
                                min_val = measurements.get(key, {}).get("min", "")
                                max_val = measurements.get(key, {}).get("max", "")
                                # Construct column names dynamically
                                row_dict[f"{group}{item}{pos}最小"] = min_val
                                row_dict[f"{group}{item}{pos}最大"] = max_val
                    
                    export_data.append(row_dict)

                df = pd.DataFrame(export_data)

            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return output
        finally:
            conn.close()

    @staticmethod
    def import_data(file):
        """匯入巡檢資料 Excel"""
        try:
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"檔案讀取失敗: {str(e)}")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            success_count = 0
            for row_num, row in enumerate(df.iterrows()):
                main_data = row[1].to_dict()

                machine_name = main_data.get('擠壓機編號')
                if pd.isna(machine_name) or str(machine_name).strip() == "":
                    machine_id = None
                else:
                    machine_str = str(machine_name).strip()
                    cursor.execute('''SELECT 識別碼 FROM "擠壓機台" WHERE 擠壓機編號 = %s''', (machine_str,))
                    m = cursor.fetchone()
                    machine_id = m[0] if m else None

                operator_name = main_data.get('員工姓名')
                if pd.isna(operator_name) or str(operator_name).strip() == "":
                    operator_id = None
                else:
                    operator_str = str(operator_name).strip()
                    cursor.execute('''SELECT 識別碼 FROM "擠壓人員" WHERE 員工姓名 = %s''', (operator_str,))
                    o = cursor.fetchone()
                    operator_id = o[0] if o else None

                customer_name = main_data.get('客戶名稱')
                if pd.isna(customer_name) or str(customer_name).strip() == "":
                    customer_id = None
                else:
                    customer_str = str(customer_name).strip()
                    cursor.execute('''SELECT 識別碼 FROM "廠商資料" WHERE 廠商名稱 = %s''', (customer_str,))
                    c = cursor.fetchone()
                    customer_id = c[0] if c else None

                inspector_name = main_data.get('檢驗人員')
                if pd.isna(inspector_name) or str(inspector_name).strip() == "":
                    inspector_id = None
                else:
                    inspector_str = str(inspector_name).strip()
                    cursor.execute('''SELECT 識別碼 FROM "品管人員" WHERE 姓名 = %s''', (inspector_str,))
                    i = cursor.fetchone()
                    inspector_id = i[0] if i else None

                display_row_num = row_num + 2
                if not machine_id:
                    raise ValueError(f"第 {display_row_num} 行: 找不到機台 '{machine_name}'")
                if not operator_id:
                    raise ValueError(f"第 {display_row_num} 行: 找不到員工 '{operator_name}'")
                if not inspector_id:
                    raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'")

                cursor.execute(
                    """
                    INSERT INTO "巡檢主檔"
                    (檢驗日期, 機台, 主機手, 材質, 擠壓規格, 客戶名稱, 原料批號, 檢驗人員)
                    RETURNING 識別碼
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                        INSERT INTO "巡檢子檔"
                        (主檔ID, 組別, 測量項目, 測量位置, 最小值, 最大值)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (patrol_id, "1", item, pos, min_val, max_val)
                    )

                success_count += 1

            conn.commit()
            return success_count
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
