# tz_api/auth.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from tz_api.api_login_jwt import TradeZeroLogin  # 你原本的 login 類別


load_dotenv(override=True)


class TzAuth:
    CACHE_FILE = "cache/.tz_token_cache.json"

    def __init__(self):
        
        self.jwt_token = self.load_token_from_cache()
        
        if not self.jwt_token:
            print("⚠️ Token not found or expired. Logging in...")
            self.login_and_cache_token()

    def load_token_from_cache(self):
        """載入並驗證快取 token"""
        if os.path.exists(self.CACHE_FILE):
            with open(self.CACHE_FILE, "r") as f:
                try:
                    data = json.load(f)
                    expires = datetime.fromisoformat(data.get("expires")).replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) < expires:
                        print("✅ Loaded valid token from cache.")
                        self.customer_id = data.get("customer_id")
                        return data["jwt_token"]
                    else:
                        print("⚠️ Token expired.")
                except Exception as e:
                    print("⚠️ Error reading token cache:", e)
        return None

    def login_and_cache_token(self):
        """使用 TradeZeroLogin 進行登入並儲存 token"""
        self.login_manager = TradeZeroLogin(cache_file=self.CACHE_FILE)
       
        if self.login_manager.login():
            token = self.login_manager.jwt_token

            self.jwt_token = token
            print("✅ Token refreshed and cached.")
        else:
            raise ValueError("❌ Login failed.")

    def get_token(self):
        return self.jwt_token


if __name__ == "__main__":
    tz_auth = TzAuth()
    jwt_token = tz_auth.jwt_token