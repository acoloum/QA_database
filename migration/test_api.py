"""
API 端點測試腳本
用途：測試 PostgreSQL 版本的 API 是否正常運作
"""

import requests
import json
from datetime import datetime

BASE_URL = 'http://localhost:5000'

class Colors:
    """終端機顏色（如果支援）"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    
    @staticmethod
    def success(text):
        return f"{Colors.GREEN}[OK]{Colors.END} {text}"
    
    @staticmethod
    def error(text):
        return f"{Colors.RED}[ERROR]{Colors.END} {text}"
    
    @staticmethod
    def warning(text):
        return f"{Colors.YELLOW}[WARNING]{Colors.END} {text}"
    
    @staticmethod
    def info(text):
        return f"{Colors.BLUE}[INFO]{Colors.END} {text}"


def test_endpoint(method, endpoint, description, data=None, headers=None, expected_status=200):
    """測試單個端點"""
    url = f"{BASE_URL}{endpoint}"
    
    print(f"\n測試: {description}")
    print(f"  端點: {method} {endpoint}")
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=5)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=5)
        else:
            print(Colors.error(f"不支援的方法: {method}"))
            return False
        
        print(f"  狀態碼: {response.status_code}")
        
        if response.status_code == expected_status:
            print(Colors.success("通過"))
            
            # 顯示回應內容（截斷）
            try:
                response_json = response.json()
                response_str = json.dumps(response_json, ensure_ascii=False, indent=2)
                
                if len(response_str) > 200:
                    print(f"  回應: {response_str[:200]}...")
                else:
                    print(f"  回應: {response_str}")
            except:
                pass
            
            return True
        else:
            print(Colors.error(f"失敗 - 預期狀態碼 {expected_status}"))
            print(f"  回應: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(Colors.error("連接失敗 - Flask 伺服器未運行"))
        print("  請先啟動: python app_postgresql.py")
        return False
    except requests.exceptions.Timeout:
        print(Colors.error("請求超時"))
        return False
    except Exception as e:
        print(Colors.error(f"未知錯誤: {e}"))
        return False


def main():
    print("=" * 60)
    print("API 端點測試")
    print("=" * 60)
    print(f"\n目標伺服器: {BASE_URL}")
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # ========================================
    # 1. 基礎資料 API
    # ========================================
    print("\n" + "=" * 60)
    print("階段 1: 基礎資料 API")
    print("=" * 60)
    
    results.append(test_endpoint(
        'GET', '/api/inspectors',
        '獲取品管人員清單'
    ))
    
    results.append(test_endpoint(
        'GET', '/api/vendors',
        '獲取廠商清單'
    ))
    
    results.append(test_endpoint(
        'GET', '/api/machines',
        '獲取機台清單'
    ))
    
    results.append(test_endpoint(
        'GET', '/api/operators',
        '獲取操作人員清單'
    ))
    
    results.append(test_endpoint(
        'GET', '/api/materials',
        '獲取材質清單'
    ))
    
    results.append(test_endpoint(
        'GET', '/api/specs',
        '獲取檢驗規格清單'
    ))
    
    # ========================================
    # 2. 認證 API
    # ========================================
    print("\n" + "=" * 60)
    print("階段 2: 認證 API")
    print("=" * 60)
    
    # 測試登入（需要資料庫中有測試使用者）
    results.append(test_endpoint(
        'POST', '/api/login',
        '使用者登入（測試帳號）',
        data={
            'username': 'test',
            'password': 'test123'
        },
        expected_status=401  # 預期失敗（帳號不存在）
    ))
    
    # ========================================
    # 3. 出貨檢驗 API
    # ========================================
    print("\n" + "=" * 60)
    print("階段 3: 出貨檢驗 API")
    print("=" * 60)
    
    results.append(test_endpoint(
        'GET', '/api/data',
        '獲取出貨檢驗數據（分頁）'
    ))
    
    results.append(test_endpoint(
        'GET', '/api/data?page=1',
        '獲取出貨檢驗數據（第1頁）'
    ))
    
    # ========================================
    # 4. 巡檢 API
    # ========================================
    print("\n" + "=" * 60)
    print("階段 4: 巡檢 API")
    print("=" * 60)
    
    results.append(test_endpoint(
        'GET', '/api/patrol/options',
        '獲取巡檢選項'
    ))
    
    # ========================================
    # 摘要
    # ========================================
    print("\n" + "=" * 60)
    print("測試摘要")
    print("=" * 60)
    
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"\n總測試數: {total}")
    print(f"{Colors.GREEN}通過: {passed}{Colors.END}")
    print(f"{Colors.RED}失敗: {failed}{Colors.END}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}✓ 所有測試通過！{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}⚠ 部分測試失敗{Colors.END}")
        print("\n失敗原因可能:")
        print("  1. 資料庫中沒有資料")
        print("  2. 資料庫連接設定錯誤")
        print("  3. SQL 語法轉換有誤")
        print("  4. 缺少必要的測試資料")
    
    print("\n建議:")
    print("  1. 檢查 Flask 伺服器是否正常運行")
    print("  2. 確認 PostgreSQL 資料已匯入")
    print("  3. 查看 Flask 伺服器的錯誤訊息")
    print("  4. 使用 pgAdmin 檢查資料庫內容")


if __name__ == '__main__':
    main()
