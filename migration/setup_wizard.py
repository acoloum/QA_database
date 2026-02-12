"""
PostgreSQL 遷移部署精靈
用途：自動化檢查環境、安裝依賴、引導使用者完成部署
"""

import os
import sys
import subprocess
import getpass

# 將上層目錄加入路徑以便匯入 config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_header(text):
    """列印標題"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_step(step_num, total, text):
    """列印步驟"""
    print(f"\n[步驟 {step_num}/{total}] {text}")
    print("-" * 70)

def check_python_version():
    """檢查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print(f"❌ Python 版本過舊: {sys.version}")
        print("   需要 Python 3.7 或更高版本")
        return False
    print(f"✅ Python 版本: {sys.version.split()[0]}")
    return True

def check_postgresql_installed():
    """檢查 PostgreSQL 是否安裝"""
    try:
        # 嘗試執行 psql --version
        result = subprocess.run(['psql', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            print(f"✅ PostgreSQL 已安裝: {result.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("⚠️  無法偵測 PostgreSQL (psql 指令不可用)")
    print("   請確認 PostgreSQL 已安裝且加入 PATH")
    return None  # 未知狀態,不算失敗

def install_dependencies():
    """安裝 Python 依賴套件"""
    print("\n正在安裝必要的 Python 套件...")
    
    required_packages = [
        'psycopg2-binary',  # PostgreSQL 驅動
        'flask',            # Web 框架
        'pandas',           # 資料處理
        'openpyxl',         # Excel 處理
    ]
    
    for package in required_packages:
        print(f"\n檢查套件: {package}")
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package} 已安裝")
        except ImportError:
            print(f"  ⬇️  正在安裝 {package}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"  ✅ {package} 安裝成功")
            except subprocess.CalledProcessError as e:
                print(f"  ❌ {package} 安裝失敗: {e}")
                return False
    
    return True

def setup_environment_variables():
    """設定環境變數 (建立 .env 檔案)"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    print("\n現在需要設定 PostgreSQL 連線資訊")
    print("這些資訊會儲存在 .env 檔案中 (不會提交到 Git)")
    
    # 詢問使用者
    print("\n請輸入以下資訊 (直接按 Enter 使用預設值):")
    
    host = input(f"PostgreSQL 主機位址 [localhost]: ").strip() or 'localhost'
    port = input(f"PostgreSQL 連接埠 [5432]: ").strip() or '5432'
    database = input(f"資料庫名稱 [qa_database]: ").strip() or 'qa_database'
    user = input(f"使用者名稱 [postgres]: ").strip() or 'postgres'
    
    # 密碼輸入 (隱藏顯示)
    while True:
        password = getpass.getpass(f"PostgreSQL 密碼 (輸入時不顯示): ")
        if password:
            password_confirm = getpass.getpass(f"再次輸入密碼確認: ")
            if password == password_confirm:
                break
            else:
                print("❌ 兩次密碼不一致,請重新輸入")
        else:
            print("❌ 密碼不可為空,請重新輸入")
    
    # 寫入 .env 檔案
    env_content = f"""# PostgreSQL 連線設定
# 此檔案包含敏感資訊,請勿提交到版本控制系統
DB_HOST={host}
DB_PORT={port}
DB_NAME={database}
DB_USER={user}
DB_PASSWORD={password}
"""
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print(f"\n✅ 環境變數已儲存到: {env_path}")
        
        # 確保 .gitignore 包含 .env
        gitignore_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                gitignore_content = f.read()
            if '.env' not in gitignore_content:
                with open(gitignore_path, 'a', encoding='utf-8') as f:
                    f.write('\n# 環境變數檔案\n.env\n')
                print("✅ 已將 .env 加入 .gitignore")
        
        return {
            'host': host,
            'port': int(port),
            'database': database,
            'user': user,
            'password': password
        }
    except Exception as e:
        print(f"❌ 無法寫入 .env 檔案: {e}")
        return None

def create_database(db_config):
    """建立 PostgreSQL 資料庫"""
    print("\n正在建立 PostgreSQL 資料庫...")
    
    # 準備 psql 指令
    db_name = db_config['database']
    create_db_sql = f"CREATE DATABASE {db_name} WITH OWNER = {db_config['user']} ENCODING = 'UTF8';"
    
    print(f"\n即將執行的 SQL 指令:")
    print(f"  {create_db_sql}")
    
    # 設定環境變數以便 psql 自動登入
    env = os.environ.copy()
    env['PGPASSWORD'] = db_config['password']
    
    try:
        # 先連線到預設的 postgres 資料庫檢查目標資料庫是否已存在
        check_cmd = [
            'psql',
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-U', db_config['user'],
            '-d', 'postgres',
            '-t',  # 只輸出結果
            '-c', f"SELECT 1 FROM pg_database WHERE datname = '{db_name}';"
        ]
        
        result = subprocess.run(check_cmd, 
                              capture_output=True, 
                              text=True, 
                              env=env,
                              timeout=10)
        
        if result.stdout.strip():
            print(f"⚠️  資料庫 '{db_name}' 已存在")
            overwrite = input("是否要刪除並重新建立? (y/N): ").strip().lower()
            if overwrite == 'y':
                drop_cmd = [
                    'psql',
                    '-h', db_config['host'],
                    '-p', str(db_config['port']),
                    '-U', db_config['user'],
                    '-d', 'postgres',
                    '-c', f"DROP DATABASE {db_name};"
                ]
                subprocess.run(drop_cmd, env=env, timeout=10, check=True)
                print(f"✅ 已刪除舊資料庫")
            else:
                print("⏭️  跳過資料庫建立步驟")
                return True
        
        # 建立新資料庫
        create_cmd = [
            'psql',
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-U', db_config['user'],
            '-d', 'postgres',
            '-c', create_db_sql
        ]
        
        result = subprocess.run(create_cmd, 
                              capture_output=True, 
                              text=True, 
                              env=env,
                              timeout=10)
        
        if result.returncode == 0:
            print(f"✅ 資料庫 '{db_name}' 建立成功")
            return True
        else:
            print(f"❌ 資料庫建立失敗:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ 找不到 psql 指令")
        print("   請確認 PostgreSQL 已安裝且 psql 已加入系統 PATH")
        print("\n手動建立資料庫的方法:")
        print("   1. 開啟 pgAdmin 或 psql")
        print(f"   2. 執行: {create_db_sql}")
        return None  # 未知狀態
    except subprocess.TimeoutExpired:
        print("❌ 資料庫連線逾時")
        print("   請檢查 PostgreSQL 服務是否正在執行")
        return False
    except Exception as e:
        print(f"❌ 建立資料庫時發生錯誤: {e}")
        return False

def test_database_connection(db_config):
    """測試資料庫連線"""
    print("\n正在測試資料庫連線...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        print(f"✅ 資料庫連線成功")
        print(f"   版本: {version[:80]}...")
        return True
    except Exception as e:
        print(f"❌ 資料庫連線失敗: {e}")
        return False

def main():
    """主程式"""
    print_header("PostgreSQL 遷移部署精靈")
    print("這個精靈會協助你完成以下工作:")
    print("  1. 檢查環境與依賴")
    print("  2. 安裝必要的 Python 套件")
    print("  3. 設定資料庫連線資訊")
    print("  4. 建立 PostgreSQL 資料庫")
    print("  5. 測試資料庫連線")
    
    input("\n按 Enter 鍵開始...")
    
    # ===== 步驟 1: 環境檢查 =====
    print_step(1, 5, "環境檢查")
    
    if not check_python_version():
        print("\n❌ 環境檢查失敗,無法繼續")
        return
    
    check_postgresql_installed()
    
    # ===== 步驟 2: 安裝依賴 =====
    print_step(2, 5, "安裝 Python 依賴套件")
    
    if not install_dependencies():
        print("\n❌ 依賴安裝失敗,請手動安裝後再試")
        print("   手動安裝指令: pip install psycopg2-binary flask pandas openpyxl")
        return
    
    # ===== 步驟 3: 設定環境變數 =====
    print_step(3, 5, "設定資料庫連線資訊")
    
    db_config = setup_environment_variables()
    if not db_config:
        print("\n❌ 環境變數設定失敗,無法繼續")
        return
    
    # ===== 步驟 4: 建立資料庫 =====
    print_step(4, 5, "建立 PostgreSQL 資料庫")
    
    db_result = create_database(db_config)
    if db_result is False:  # 明確失敗
        print("\n❌ 資料庫建立失敗,請檢查錯誤訊息")
        return
    elif db_result is None:  # psql 不可用
        print("\n⚠️  無法自動建立資料庫,請手動建立")
        print(f"\n手動建立方法:")
        print(f"  1. 開啟 pgAdmin")
        print(f"  2. 右鍵點擊 'Databases' → Create → Database")
        print(f"  3. Database 名稱: {db_config['database']}")
        print(f"  4. Owner: {db_config['user']}")
        print(f"  5. Encoding: UTF8")
        
        proceed = input("\n完成手動建立後,按 Enter 繼續測試連線 (或輸入 q 退出): ").strip().lower()
        if proceed == 'q':
            return
    
    # ===== 步驟 5: 測試連線 =====
    print_step(5, 5, "測試資料庫連線")
    
    if not test_database_connection(db_config):
        print("\n❌ 連線測試失敗,請檢查:")
        print("   - PostgreSQL 服務是否正在執行")
        print("   - 連線資訊是否正確")
        print("   - 防火牆設定")
        return
    
    # ===== 完成 =====
    print_header("✅ 前置作業完成!")
    print("\n下一步:")
    print("  1. 執行 schema 部署:")
    print("     python migration/deploy_schema.py")
    print("\n  2. 匯出 SQL Server 資料:")
    print("     python migration/export_data.py")
    print("\n  3. 匯入資料到 PostgreSQL:")
    print("     python migration/import_data.py")
    print("\n  4. 測試應用程式:")
    print("     python app_postgresql.py")
    print("\n  5. 測試 API 端點:")
    print("     python migration/test_api.py")
    
    print("\n" + "=" * 70)
    print("提示: 所有連線資訊已儲存在 .env 檔案中")
    print("      如需修改,請直接編輯 .env 檔案")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n使用者中斷執行")
    except Exception as e:
        print(f"\n\n❌ 發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()
