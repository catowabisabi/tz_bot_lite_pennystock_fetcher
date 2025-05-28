
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from datetime import datetime, timedelta, timezone

class TokenCache:
    def __init__(self, cache_file="cache/.tz_token_cache.json"):
        self.cache_file = cache_file

    def load_token(self):
        """從 cache 文件中加載有效的 token"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                cache_data = json.load(f)
                try:
                    expires = datetime.fromisoformat(cache_data.get("expires")).replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) < expires:
                        print("✅ Loaded valid token from cache.")
                        return cache_data["jwt_token"]
                except Exception as e:
                    print("⚠️ Cache validation failed:", e)
        return None

    def save_token(self, token):
        """將有效 token 保存到 cache 文件"""
        cache_data = {
            "jwt_token": token,
            "expires": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()  # 假設 token 1 天過期
        }
        with open(self.cache_file, "w") as f:
            json.dump(cache_data, f)
        print("✅ Token saved to cache.")

if __name__ == "__main__":
    cache = TokenCache()
    token = cache.load_token()
    if token:
        print("Token:", token)
    else:
        print("No valid token found in cache.")