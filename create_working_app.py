#!/usr/bin/env python3
import re

def restore_app():
    """從備份恢復app.py"""
    try:
        import shutil
        if os.path.exists('app.py.bak'):
            shutil.copy('app.py.bak', 'app.py')
            print("已從備份恢復app.py")
            return True
        else:
            print("找不到備份檔案")
            return False
    except Exception as e:
        print(f"恢復失敗: {e}")
        return False

def create_working_version():
    """創建一個簡化的可工作版本"""
    try:
        # 讀取原始有問題的檔案
        with open('app.py.bak', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 創除有問題的函數，只保留基本結構
        lines = content.split('\n')
        clean_lines = []
        skip_line = False
        
        for i, line in enumerate(lines, 1):
            # 跳過或修復有問題的區段
            if 'for i in range(1, 6):' in line:
                skip_line = True
                print(f"跳過問題行 {i}")
            elif 'def get_db_connection' in line and i > 23:
                print(f"保留基本db連線函數到行 {i}")
                clean_lines.append('def get_db_connection():')
                clean_lines.append('    try:')
                clean_lines.append('        return pyodbc.connect('Server=localhost\\SQLEXPRESS;Database=品保資料庫;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;Connection Timeout=30;')')
                clean_lines.append('    except Exception as e:')
                clean_lines.append('        print(f"DB連線錯誤: {e}")')
                clean_lines.append('        return None')
                clean_lines.append('')
                # 添加開括號結束
                clean_lines.append('')
                clean_lines.append('')
            elif 'def get_ncmr_info' in line and i > 25:
                print(f"保留基本NCMR函數到行 {i}")
                clean_lines.append('def get_ncmr_info(ncmr_id):')
                clean_lines.append('    conn = get_db_connection()')
                clean_lines.append('    if conn:')
                clean_lines.append('        try:')
                clean_lines.append('            cursor = conn.cursor()')
                clean_lines.append('            cursor.execute("SELECT * FROM dbo.不合格品單 WHERE 識別碼 = ?", (ncmr_id,))')
                clean_lines.append('            row = cursor.fetchone()')
                clean_lines.append('            cols = [c[0] for c in cursor.description]')
                clean_lines.append('            if row:')
                clean_lines.append('                item = {}')
                clean_lines.append('                for j, col in enumerate(cols):')
                clean_lines.append('                    value = row[j]')
                clean_lines.append('                    if value is None:')
                clean_lines.append('                        item[col] = ""')
                clean_lines.append('                    elif hasattr(value, \'strftime\'):')
                clean_lines.append('                        if \'時間\' in col:')
                clean_lines.append('                            item[col] = value.strftime(\'%Y-%m-%d %H:%M:%S\')')
                clean_lines.append('                        else:')
                clean_lines.append('                            item[col] = value.strftime(\'%Y-%m-%d\')')
                clean_lines.append('                        try:')
                clean_lines.append('                            item[col] = str(value)')
                clean_lines.append('                        except:')
                clean_lines.append('                            item[col] = ""')
                clean_lines.append('                    else:')
                clean_lines.append('                        item[col] = value')
                clean_lines.append('                    return jsonify(item)')
                clean_lines.append('        except Exception as e:')
                clean_lines.append('            print(f"NCMR API錯誤: {e}")')
                clean_lines.append('            return jsonify({"error": f"NCMR API錯誤: {str(e)}"})')
                clean_lines.append('        finally:')
                clean_lines.append('            if conn:')
                clean_lines.append('                conn.close()')
                clean_lines.append('')
                clean_lines.append('')
                return None
            
            elif 'return jsonify({"error": str(e)}), 500' in line or 'except Exception as e:' in line:
                # 保留簡化的錯誤處理
                clean_lines.append(line)
            else:
                clean_lines.append(line)
        
        # 寫入簡化版本
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write('\n'.join(clean_lines))
        
        print("創建工作版本app_simple.py完成")
        return True
        
    except Exception as e:
        print(f"創建工作版本失敗: {e}")
        return False

def main():
    print("修復app.py...")
    
    if not restore_app():
        if create_working_version():
            print("✅ 已創建app_simple.py，請使用此版本")
        else:
            print("❌ 恢復失敗，使用backup")
    else:
        print("已恢復原始檔案")

if __name__ == '__main__':
    main()