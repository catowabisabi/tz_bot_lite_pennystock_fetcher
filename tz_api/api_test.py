import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import os

class TestFetcher:
    def __init__(self, url, token=None, cache_file=".tz_token_cache.json"):
        from tz_api.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token
        self.customer_id = self.tz_auth.customer_id
        
        self.url = url
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        print("✅ JWT Token 準備就緒")

    def fetch(self, symbol: str = None):
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


endpoint = "v1/platformsupport/api/AutoUpdateService/?majorVersion=3&minorVersion=0&release=638&build=1&includeDev=True&includeBeta=True"

# 使用方式
if __name__ == "__main__":
    try:
        # 將自動從快取中獲取 token 或登入
        test_fetcher = TestFetcher(url=f"https://api.tradezero.com/{endpoint}")
        
        # 不指定符號，獲取所有帳戶
        test_fetcher.fetch()
        
        # 或者指定符號
        # account_fetcher.fetch_account("TZPD1D60")
    except Exception as e:
        print(f"❌ 錯誤: {e}")