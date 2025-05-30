import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from tabulate import tabulate


class AccountFetcher:
    def __init__(self, token=None, cache_file=".tz_token_cache.json"):
        from api_tradezero.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token
        
        self.url = "https://api.tradezero.com/v1/accounts/api/Accounts/"
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        print("✅ JWT Token 準備就緒")

    def fetch_account(self, symbol: str = None):
        """根據給定的 symbol 拉取帳戶資料，不指定則獲取所有帳戶"""
        try:
            endpoint = f"{self.url}{symbol}" if symbol else self.url
            print(f"🔍 正在取得帳戶資料: {endpoint}")
            
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()  # 檢查是否成功
            data = response.json()
            print(data)
            if not data:
                print(f"⚠️ 未找到{'符號 ' + symbol if symbol else ''}資料。")
                return None

            # 顯示資料
            self.display(data)
            return data

        except requests.exceptions.RequestException as e:
            print(f"❌ 請求失敗: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print("狀態碼:", e.response.status_code)
                print("回應:", e.response.text)
                
                # 如果是認證錯誤，嘗試重新登入
                if e.response.status_code in [401, 403]:
                    print("🔄 Token 可能已過期，嘗試重新登入...")
                    if hasattr(self, 'login_handler'):
                        # 刪除快取文件以強制重新登入
                        if os.path.exists(self.login_handler.cache_file):
                            os.remove(self.login_handler.cache_file)
                        
                        # 重新登入
                        login_success = self.login_handler.login()
                        if login_success:
                            self.jwt_token = self.login_handler.jwt_token
                            self.headers["Authorization"] = f"Bearer {self.jwt_token}"
                            print("✅ 重新登入成功，正在重試請求...")
                            return self.fetch_account(symbol)  # 重試請求
            return None

    def display(self, data):
        """將帳戶資料格式化為表格並打印"""
        # 確保 data 是列表
        if not isinstance(data, list):
            data = [data]
        
        # 檢查是否有資料
        if not data:
            print("⚠️ 沒有可顯示的資料。")
            return
        
        print(f"\n📘 帳戶資訊 (找到 {len(data)} 個帳戶):")
        
        # 為每個帳戶創建一個表格
        for i, account in enumerate(data):
            if i > 0:
                print("\n")  # 在帳戶之間添加空行
                
            table = [["欄位", "值"]]
            for key, value in account.items():
                table.append([key, str(value)])
            
            print(f"帳戶 #{i+1}:")
            print(tabulate(table, headers="firstrow", tablefmt="grid"))
    
    def print_account_info(self, account_info: list[dict]):
        for account in account_info:
            print("====================================")
            print(f"👤 帳戶代號：{account.get('account', 'N/A')}")
            print(f"📊 當前資產總額（Equity）：${account.get('equity', 0):,.2f}")
            print(f"💵 可用現金（Available Cash）：${account.get('availableCash', 0):,.2f}")
            print(f"📈 可用買入力（Buying Power）：${account.get('bp', 0):,.2f}")
            print(f"🛏️ 隔夜買入力（Overnight BP）：${account.get('overnightBp', 0):,.2f}")
            print(f"⚖️ 杠桿倍數（Leverage）：{account.get('leverage', 1.0)}")
            print(f"🧾 已實現盈虧（Realized P&L）：${account.get('realized', 0):,.2f}")
            print(f"📉 保證金需求（Maintenance Requirement）：${account.get('maintReq', 0):,.2f}")
            print(f"📦 選擇權等級（Option Level）：{account.get('optionTradingLevel', 0)}")
            print(f"📁 帳戶狀態：{account.get('accountStatus', 'Unknown')}")
            print("====================================\n")


# 使用方式
if __name__ == "__main__":
    try:
        # 將自動從快取中獲取 token 或登入
        account_fetcher = AccountFetcher()
        
        # 不指定符號，獲取所有帳戶
        account_fetcher.fetch_account()
        
        # 或者指定符號
        # account_fetcher.fetch_account("TZPD1D60")
    except Exception as e:
        print(f"❌ 錯誤: {e}")