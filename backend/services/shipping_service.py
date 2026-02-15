
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from ..utils import (
    get_db_connection,
    format_value,
    validate_inspection_data,
    handle_db_error
)

class ShippingService:
    @staticmethod
    def get_list(args):
        """獲取出貨檢驗數據列表"""
        params = []
        where = []

        # 支援按 ID 查詢（優先處理）
        if args.get('id'):
            where.append("T1.識別碼 = %s")
            params.append(args['id'])
        else:
            # 一般查詢條件
            if args.get('vendor'):   where.append("V.廠商名稱 LIKE %s"); params.append(f"%{args['vendor']}%")
            if args.get('material'): where.append("T1.材質 LIKE %s");     params.append(f"%{args['material']}%")
            if args.get('spec'):     where.append("T1.檢驗規格 LIKE %s"); params.append(f"%{args['spec']}%")
            if args.get('start_date'): where.append("T1.檢驗日期 >= %s"); params.append(args['start_date'])
            if args.get('end_date'):   where.append("T1.檢驗日期 <= %s"); params.append(args['end_date'])

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = f"""
                SELECT T1.識別碼, T1.檢驗日期, T1.材質, T1.檢驗規格, T1.訂單號碼,
                       P.姓名 AS 檢驗人員, V.廠商名稱 AS 廠商中文名稱,
                       T1."外徑1-min", T1."外徑1-max", T1."外徑2-min", T1."外徑2-max",
                       T1."外徑3-min", T1."外徑3-max", T1."外徑4-min", T1."外徑4-max",
                       T1."外徑5-min", T1."外徑5-max",
                       T1."內徑1-min", T1."內徑1-max", T1."內徑2-min", T1."內徑2-max",
                       T1."內徑3-min", T1."內徑3-max", T1."內徑4-min", T1."內徑4-max",
                       T1."內徑5-min", T1."內徑5-max",
                       T1."厚度1-min", T1."厚度1-max", T1."厚度2-min", T1."厚度2-max",
                       T1."厚度3-min", T1."厚度3-max", T1."厚度4-min", T1."厚度4-max",
                       T1."厚度5-min", T1."厚度5-max",
                       T1.同心度1, T1.同心度2, T1.同心度3, T1.同心度4, T1.同心度5,
                       T1.長度1, T1.長度2, T1.長度3, T1.長度4, T1.長度5,
                       T1.硬度1, T1.硬度2, T1.硬度3, T1.硬度4, T1.硬度5,
                       T1.真直度1, T1.真直度2, T1.真直度3, T1.真直度4, T1.真直度5
                  FROM "出貨檢驗數據" T1
                  LEFT JOIN "品管人員" P ON T1.檢驗人員 = P.識別碼
                  LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
                  {where_sql}
                  ORDER BY T1.識別碼 DESC
            """
            cursor.execute(sql, params)
            cols = [c[0] for c in cursor.description]
            all_data = []
            for row in cursor.fetchall():
                item = dict(zip(cols, row))
                for key, val in item.items():
                    item[key] = format_value(val)
                
                # 確保檢驗日期是 YYYY-MM-DD 格式
                if item.get('檢驗日期'):
                    date_val = item['檢驗日期']
                    if isinstance(date_val, str):
                        if len(date_val) == 10 and '-' in date_val:
                            pass
                        elif 'T' in date_val:
                            item['檢驗日期'] = date_val.split('T')[0]
                        else:
                            try:
                                parsed = datetime.strptime(date_val[:10], '%Y-%m-%d')
                                item['檢驗日期'] = parsed.strftime('%Y-%m-%d')
                            except:
                                pass
                
                all_data.append(item)
                
            # 分頁處理
            total = len(all_data)
            page = int(args.get('page', 1))
            per_page = 10
            start = (page - 1) * per_page
            end = start + per_page
            
            return {
                "data": all_data[start:end],
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            }
        finally:
            conn.close()

    @staticmethod
    def get_by_id(data_id):
        """根據 ID 獲取單筆出貨檢驗資料"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT T1.識別碼, T1.檢驗日期, T1.材質, T1.檢驗規格, T1.訂單號碼,
                       P.姓名 AS 檢驗人員, V.廠商名稱 AS 廠商中文名稱,
                       T1."外徑1-min", T1."外徑1-max", T1."外徑2-min", T1."外徑2-max",
                       T1."外徑3-min", T1."外徑3-max", T1."外徑4-min", T1."外徑4-max",
                       T1."外徑5-min", T1."外徑5-max",
                       T1."內徑1-min", T1."內徑1-max", T1."內徑2-min", T1."內徑2-max",
                       T1."內徑3-min", T1."內徑3-max", T1."內徑4-min", T1."內徑4-max",
                       T1."內徑5-min", T1."內徑5-max",
                       T1."厚度1-min", T1."厚度1-max", T1."厚度2-min", T1."厚度2-max",
                       T1."厚度3-min", T1."厚度3-max", T1."厚度4-min", T1."厚度4-max",
                       T1."厚度5-min", T1."厚度5-max",
                       T1.同心度1, T1.同心度2, T1.同心度3, T1.同心度4, T1.同心度5,
                       T1.長度1, T1.長度2, T1.長度3, T1.長度4, T1.長度5,
                       T1.硬度1, T1.硬度2, T1.硬度3, T1.硬度4, T1.硬度5,
                       T1.真直度1, T1.真直度2, T1.真直度3, T1.真直度4, T1.真直度5
                FROM "出貨檢驗數據" T1
                LEFT JOIN "品管人員" P ON T1.檢驗人員 = P.識別碼
                LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
                WHERE T1.識別碼 = %s
            """
            cursor.execute(sql, (data_id,))
            cols = [c[0] for c in cursor.description]
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            item = dict(zip(cols, row))
            
            # 格式化每個值
            for key, val in item.items():
                item[key] = format_value(val)
            
            # 確保檢驗日期是 YYYY-MM-DD 格式
            if item.get('檢驗日期'):
                date_val = item['檢驗日期']
                if isinstance(date_val, str) and 'T' in date_val:
                    item['檢驗日期'] = date_val.split('T')[0]
            
            return item
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_stats(args):
        """獲取出貨檢驗的 SPC 統計數據（含公差界限）"""
        field = args.get('field', '外徑')
        vendor = args.get('vendor')
        material = args.get('material')
        spec = args.get('spec')
        start_date = args.get('start_date')
        end_date = args.get('end_date')

        params = []
        where = []
        if vendor: where.append("V.廠商名稱 LIKE %s"); params.append(f"%{vendor}%")
        if material: where.append("T1.材質 LIKE %s"); params.append(f"%{material}%")
        if spec: where.append("T1.檢驗規格 LIKE %s"); params.append(f"%{spec}%")
        if start_date: where.append("T1.檢驗日期 >= %s"); params.append(start_date)
        if end_date: where.append("T1.檢驗日期 <= %s"); params.append(end_date)
        
        where_sql = " WHERE " + " AND ".join(where) if where else ""

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 查詢公差標準（如果有）
            tolerance_limits = {"USL": None, "LSL": None, "found": False}
            if material:
                cursor.execute("""
                    SELECT T1."識別碼"
                    FROM "廠商公差主檔" T1
                    WHERE T1."材質" = %s
                    ORDER BY T1."廠商ID" DESC NULLS LAST, T1."規格" DESC NULLS LAST
                    LIMIT 1
                """, (material,))
                tol_main = cursor.fetchone()
                if tol_main:
                    # 查找對應測量項目的公差
                    cursor.execute("""
                        SELECT "公差下限", "公差上限", "尺寸下限", "尺寸上限"
                        FROM "廠商公差明細檔"
                        WHERE "主檔ID" = %s AND "測量項目" = %s
                        LIMIT 1
                    """, (tol_main[0], field))
                    tol_detail = cursor.fetchone()
                    if tol_detail:
                        tolerance_limits["found"] = True
                        tolerance_limits["公差下限"] = float(tol_detail[0]) if tol_detail[0] is not None else None
                        tolerance_limits["公差上限"] = float(tol_detail[1]) if tol_detail[1] is not None else None
                        tolerance_limits["尺寸下限"] = float(tol_detail[2]) if tol_detail[2] is not None else None
                        tolerance_limits["尺寸上限"] = float(tol_detail[3]) if tol_detail[3] is not None else None
                        # 計算 USL/LSL (標準值 ± 公差)
                        if tol_detail[2] is not None and tol_detail[3] is not None:
                            tolerance_limits["LSL"] = float(tol_detail[2])
                            tolerance_limits["USL"] = float(tol_detail[3])
                        elif tol_detail[0] is not None and tol_detail[1] is not None:
                            # 如果沒有尺寸上下限，嘗試用公差計算
                            std_val = cursor.execute("""
                                SELECT "標準值" FROM "廠商公差明細檔" 
                                WHERE "主檔ID" = %s AND "測量項目" = %s LIMIT 1
                            """, (tol_main[0], field))
                            std_result = cursor.fetchone()
                            if std_result and std_result[0] is not None:
                                std = float(std_result[0])
                                tolerance_limits["LSL"] = std - float(tol_detail[0])
                                tolerance_limits["USL"] = std + float(tol_detail[1])
                            else:
                                tolerance_limits["LSL"] = None
                                tolerance_limits["USL"] = None
            sql = f"""
                SELECT T1.識別碼, T1.檢驗日期, T1.訂單號碼,
                       T1."{field}1-min", T1."{field}1-max",
                       T1."{field}2-min", T1."{field}2-max",
                       T1."{field}3-min", T1."{field}3-max",
                       T1."{field}4-min", T1."{field}4-max",
                       T1."{field}5-min", T1."{field}5-max"
                FROM "出貨檢驗數據" T1
                LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
                {where_sql}
                ORDER BY T1.識別碼 DESC
            """
            # 如果欄位不是 minmax 類型，SQL 會有不同
            is_minmax = field in ['外徑', '內徑', '厚度']
            if not is_minmax:
                sql = f"""
                    SELECT T1.識別碼, T1.檢驗日期, T1.訂單號碼,
                           T1."{field}1", T1."{field}2", T1."{field}3", T1."{field}4", T1."{field}5"
                    FROM "出貨檢驗數據" T1
                    LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
                    {where_sql}
                    ORDER BY T1.識別碼 DESC
                """
            
            rows = cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            if not rows:
                return {"labels": [], "avgs": [], "ranges": [], "x_cl":0, "x_ucl":0, "x_lcl":0, "r_cl":0, "r_ucl":0}

            labels = []
            ids = []
            dates = []
            avgs = []
            ranges = []
            ids_valid = []  # 只存有效數據的 ID
            dates_valid = []  # 只存有效數據的日期
            labels_valid = []  # 只存有效數據的標籤
            insufficient_data = []  # 標記數據不足的原始索引
            
            # 從後往前排（時間序）
            for idx, r in enumerate(rows[::-1]):
                vals = []
                valid_groups = 0  # 有效組數
                
                if is_minmax:
                    # 每組取 (min + max) / 2，min 和 max 都必須有值才算有效
                    for i in range(3, 13, 2):
                        if r[i] is not None and r[i+1] is not None and r[i] != '' and r[i+1] != '':
                            try:
                                val = (float(r[i]) + float(r[i+1])) / 2
                                vals.append(val)
                                valid_groups += 1
                            except (ValueError, TypeError):
                                pass
                else:
                    for i in range(3, 8):
                        if r[i] is not None and r[i] != '':
                            try:
                                vals.append(float(r[i]))
                                valid_groups += 1
                            except (ValueError, TypeError):
                                pass
                
                original_idx = len(rows) - 1 - idx
                
                if valid_groups >= 3 and vals:
                    vals_np = np.array(vals, dtype=float)
                    avg_val = float(np.mean(vals_np))
                    range_val = float(np.ptp(vals_np))
                    avgs.append(avg_val)
                    ranges.append(range_val)
                    ids_valid.append(str(r[0]))
                    dates_valid.append(str(r[1]) if r[1] else '')
                    labels_valid.append(str(r[2]) if r[2] else str(r[0]))
                else:
                    insufficient_data.append({
                        "id": str(r[0]),
                        "date": str(r[1]) if r[1] else '',
                        "valid_groups": valid_groups,
                        "original_idx": original_idx
                    })

            BASELINE_COUNT = 25
            
            if len(avgs) >= 5:
                baseline_count = min(BASELINE_COUNT, len(avgs))
                baseline_avgs = avgs[:baseline_count]
                baseline_ranges = ranges[:baseline_count]
                
                x_cl = np.mean(baseline_avgs)
                r_cl = np.mean(baseline_ranges)
                x_ucl = x_cl + 0.577 * r_cl
                x_lcl = x_cl - 0.577 * r_cl
                r_ucl = 2.114 * r_cl
                
                x_lcl = max(x_lcl, 0)
            else:
                x_cl = x_ucl = x_lcl = r_cl = r_ucl = 0
                baseline_count = 0

            return {
                "labels": labels_valid,
                "ids": ids_valid,
                "dates": dates_valid,
                "avgs": [float(x) for x in avgs],
                "ranges": [float(x) for x in ranges],
                "x_cl": float(x_cl),
                "x_ucl": float(x_ucl),
                "x_lcl": float(x_lcl),
                "r_cl": float(r_cl),
                "r_ucl": float(r_ucl),
                "baseline_count": baseline_count,
                "insufficient_data": insufficient_data,
                "total_rows": len(rows),
                "valid_count": len(avgs),
                "tolerance": tolerance_limits
            }
        finally:
            conn.close()

    @staticmethod
    def save_data(data, is_update=False):
        """新增或更新出貨檢驗資料"""
        errors = validate_inspection_data(data)
        if errors:
            raise ValueError(", ".join(errors))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 檢驗人員 ID
            cursor.execute(
                '''SELECT "識別碼" FROM "品管人員" WHERE "姓名" = %s''',
                (data.get('檢驗人員姓名'),)
            )
            p = cursor.fetchone()
            p_id = p[0] if p else None
            if not p_id:
                raise ValueError(f"找不到檢驗人員: {data.get('檢驗人員姓名')}")

            # 廠商 ID
            cursor.execute(
                '''SELECT "識別碼" FROM "廠商資料" WHERE "廠商名稱" = %s''',
                (data.get('廠商中文名稱'),)
            )
            v = cursor.fetchone()
            v_id = v[0] if v else None
            if not v_id:
                raise ValueError(f"找不到廠商: {data.get('廠商中文名稱')}")

            fields = ['"檢驗日期"', '"檢驗人員"', '"廠商名稱"', '"檢驗規格"', '"材質"', '"訂單號碼"']
            params = [
                data.get('檢驗日期'),
                p_id,
                v_id,
                data.get('檢驗規格'),
                data.get('材質'),
                data.get('訂單號碼')
            ]

            def get_val(k):
                val = data.get(k)
                return None if val == "" else val

            for i in range(1, 6):
                for col in ['外徑', '內徑', '厚度']:
                    fields += [f'"{col}{i}-min"', f'"{col}{i}-max"']
                    params += [get_val(f'{col}{i}-min'), get_val(f'{col}{i}-max')]

                for col in ['同心度', '長度', '硬度', '真直度']:
                    fields.append(f'"{col}{i}"')
                    params.append(get_val(f'{col}{i}'))

            if is_update:
                set_sql = ", ".join([f'{f}=%s' for f in fields])
                params.append(data.get('識別碼'))
                cursor.execute(
                    f'UPDATE "出貨檢驗數據" SET {set_sql} WHERE "識別碼" = %s',
                    params
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO "出貨檢驗數據"
                    ({','.join(fields)})
                    VALUES ({','.join(['%s' for _ in params])})
                    """,
                    params
                )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_data(record_id):
        """刪除出貨檢驗資料"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''DELETE FROM "出貨檢驗數據" WHERE "識別碼" = %s''', (record_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def import_data(file):
        """匯入 Excel 資料"""
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
                for key, value in main_data.items():
                    if pd.isna(value):
                        main_data[key] = None

                inspector_name = main_data.get('檢驗人員')
                if pd.isna(inspector_name) or str(inspector_name).strip() == "":
                    inspector_id = None
                else:
                    inspector_str = str(inspector_name).strip()
                    cursor.execute('''SELECT 識別碼 FROM "品管人員" WHERE 姓名 = %s''', (inspector_str,))
                    i = cursor.fetchone()
                    inspector_id = i[0] if i else None
                    if not inspector_id:
                        cursor.execute('''SELECT "姓名" FROM "品管人員"''')
                        all_inspectors = [row[0] for row in cursor.fetchall()]
                        display_row_num = row_num + 2
                        raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_str}'。資料庫中的檢驗人員有：{', '.join(all_inspectors)}")

                vendor_name = main_data.get('廠商名稱')
                if pd.isna(vendor_name) or str(vendor_name).strip() == "":
                    vendor_id = None
                else:
                    vendor_str = str(vendor_name).strip()
                    cursor.execute('''SELECT 識別碼 FROM "廠商資料" WHERE 廠商名稱 = %s''', (vendor_str,))
                    v = cursor.fetchone()
                    vendor_id = v[0] if v else None

                display_row_num = row_num + 2
                if not inspector_id:
                    raise ValueError(f"第 {display_row_num} 行: 找不到檢驗人員 '{inspector_name}'")
                if not vendor_id:
                    raise ValueError(f"第 {display_row_num} 行: 找不到廠商 '{vendor_name}'")

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
                        fields += [f'"{col}{i}-min"', f'"{col}{i}-max"']
                        params += [main_data.get(f'{col}{i}-min'), main_data.get(f'{col}{i}-max')]

                    for col in ['同心度', '長度', '硬度', '真直度']:
                        fields.append(f'"{col}{i}"')
                        params.append(main_data.get(f'{col}{i}'))

                cursor.execute(
                    f"""
                    INSERT INTO "出貨檢驗數據"
                    ({','.join(fields)})
                    VALUES ({','.join(['%s' for _ in params])})
                    """,
                    params
                )
                success_count += 1

            conn.commit()
            return success_count
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def export_excel(args):
        """匯出 Excel"""
        params = []
        where = []

        if args.get('vendor'):   where.append("V.廠商名稱 LIKE %s"); params.append(f"%{args['vendor']}%")
        if args.get('material'): where.append("T1.材質 LIKE %s");     params.append(f"%{args['material']}%")
        if args.get('spec'):     where.append("T1.檢驗規格 LIKE %s"); params.append(f"%{args['spec']}%")
        if args.get('start_date'): where.append("T1.檢驗日期 >= %s"); params.append(args['start_date'])
        if args.get('end_date'):   where.append("T1.檢驗日期 <= %s"); params.append(args['end_date'])

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT T1.識別碼, T1.檢驗日期, T1.材質, T1.檢驗規格, T1.訂單號碼,
                       P.姓名 AS 檢驗人員, V.廠商名稱 AS 廠商名稱,
                       T1."外徑1-min", T1."外徑1-max", T1."外徑2-min", T1."外徑2-max",
                       T1."外徑3-min", T1."外徑3-max", T1."外徑4-min", T1."外徑4-max",
                       T1."外徑5-min", T1."外徑5-max",
                       T1."內徑1-min", T1."內徑1-max", T1."內徑2-min", T1."內徑2-max",
                       T1."內徑3-min", T1."內徑3-max", T1."內徑4-min", T1."內徑4-max",
                       T1."內徑5-min", T1."內徑5-max",
                       T1."厚度1-min", T1."厚度1-max", T1."厚度2-min", T1."厚度2-max",
                       T1."厚度3-min", T1."厚度3-max", T1."厚度4-min", T1."厚度4-max",
                       T1."厚度5-min", T1."厚度5-max",
                       T1.同心度1, T1.同心度2, T1.同心度3, T1.同心度4, T1.同心度5,
                       T1.長度1, T1.長度2, T1.長度3, T1.長度4, T1.長度5,
                       T1.硬度1, T1.硬度2, T1.硬度3, T1.硬度4, T1.硬度5,
                       T1.真直度1, T1.真直度2, T1.真直度3, T1.真直度4, T1.真直度5
                  FROM "出貨檢驗數據" T1
                  LEFT JOIN "品管人員" P ON T1.檢驗人員 = P.識別碼
                  LEFT JOIN "廠商資料" V ON T1.廠商名稱 = V.識別碼
                  {where_sql}
                  ORDER BY T1.識別碼 DESC
              """
            sql = sql.format(where_sql=where_sql)
            rows = cursor.execute(sql, params)
            rows = cursor.fetchall()

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
            return output
        finally:
            conn.close()
