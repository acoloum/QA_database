# -*- coding: utf-8 -*-
"""
簡化版部署腳本 (非互動式)
用途：自動安裝依賴並提供後續指令
"""

import sys
import subprocess

def main():
    print("\n" + "=" * 70)
    print("  PostgreSQL 遷移 - 簡化版安裝")
    print("=" * 70)
    
    # 步驟 1: 安裝依賴
    print("\n[步驟 1/3] 安裝 Python 依賴套件...")
    print("-" * 70)
    
    packages = ['psycopg2-binary', 'flask', 'pandas', 'openpyxl']
    
    for pkg in packages:
        print(f"\n檢查 {pkg}...")
        try:
            __import__(pkg.replace('-', '_'))
            print(f"  ✓ {pkg} 已安裝")
        except ImportError:
            print(f"  ⬇ 正在安裝 {pkg}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg], 
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                print(f"  ✓ {pkg} 安裝成功")
            except:
                print(f"  ✗ {pkg} 安裝失敗")
                print(f"    請手動執行: pip install {pkg}")
    
    # 步驟 2: 提示建立 .env 檔案
    print("\n[步驟 2/3] 設定資料庫連線資訊")
    print("-" * 70)
    print("\n請建立 .env 檔案 (在專案根目錄),內容如下:")
    print("\n" + "─" * 50)
    print("DB_HOST=localhost")
    print("DB_PORT=5432")
    print("DB_NAME=qa_database")
    print("DB_USER=postgres")
    print("DB_PASSWORD=你的PostgreSQL密碼")
    print("─" * 50)
    
    print("\n建立方法:")
    print("  方法 1: 在根目錄新增 .env 檔案,複製上方內容,修改密碼")
    print("  方法 2: 執行: notepad .env (然後貼上上方內容)")
    
    # 步驟 3: 提供後續指令
    print("\n[步驟 3/3] 後續部署步驟")
    print("-" * 70)
    print("\n完成 .env 設定後,依序執行以下指令:")
    print("\n1. 建立資料庫 (在 pgAdmin 執行):")
    print("   CREATE DATABASE qa_database WITH ENCODING='UTF8';")
    print("\n2. 部署 Schema:")
    print("   python migration/deploy_schema.py")
    print("\n3. 匯出 SQL Server 資料:")
    print("   python migration/export_data.py")
    print("\n4. 匯入資料到 PostgreSQL:")
    print("   python migration/import_data.py")
    print("\n5. 啟動應用程式:")
    print("   python app_postgresql.py")
    print("\n6. 測試 API:")
    print("   python migration/test_api.py")
    
    print("\n" + "=" * 70)
    print("安裝完成!")
    print("=" * 70)

if __name__ == "__main__":
    main()
