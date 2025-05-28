import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from tabulate import tabulate
import uuid
import json
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(override=True)

class TradeZeroLogin:
    def __init__(self, cache_file=None):
        
        self.login_url = "https://api.tradezero.com/v1/login/api/login/LoginAndEncryptJWT"
        self.customer_id = os.getenv("TZ_USERNAME")
        self.password = os.getenv("TZ_PASSWORD")

        print(f"\n👤 登入帳號: {self.customer_id}")
        print(f"🔑 登入密碼: {self.password}")
        
        # Set cache_file before using it in other methods
        self.cache_file = cache_file if cache_file else "cache/.tz_token_cache.json"
        
        # Ensure self.cache_file exists at initialization
        if not os.path.exists(self.cache_file):
            with open(self.cache_file, "w") as f:
                json.dump({}, f)  # Create an empty cache file if not exists
        
        # Now load device_id after cache_file is initialized
        self.device_id = self.load_device_id()
        
        self.application = "ZeroPro"
        self.version = "3.0.638.1"
        
        self.jwt_token = None
        self.encrypted_token = None
        self.expires = None
        self.request_id = None
        self.server_info = None

    def generate_device_id(self):
        return uuid.uuid4().hex.upper()

    def load_device_id(self):
        # Try to load device_id from cache file, otherwise generate a new one
        return self.get_cached_device_id()

    def is_cache_valid(self, cache_data):
        try:
            if not cache_data or not isinstance(cache_data, dict):
                return False
            if "expires" not in cache_data:
                return False
            expires = datetime.fromisoformat(cache_data.get("expires")).replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < expires
        except Exception as e:
            print("⚠️ Cache validation error:", e)
            return False
    def get_cached_device_id(self):
        """
        Retrieves the device ID from the cache file even if the JWT token is expired.
        Returns the cached device ID if found, otherwise generates a new one.
        """
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)
                
                if isinstance(cache_data, dict) and "device_id" in cache_data:
                    device_id = cache_data["device_id"]
                    print(f"✅ 從快取中取得裝置 ID: {device_id}")  # Retrieved device ID from cache
                    return device_id
        except Exception as e:
            print(f"⚠️ 取得裝置 ID 時發生錯誤: {e}")  # Error retrieving device ID
        
        # Generate new ID if none found in cache or there was an error
        new_id = self.generate_device_id()
        print(f"✅ 產生新的裝置 ID: {new_id}")  # Generated new device ID
        return new_id



    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)
                    
                if self.is_cache_valid(cache_data):
                    print("✅ 載入有效的快取權杖。")  # Loading valid cached token
                    self.jwt_token = cache_data["jwt_token"]
                    self.encrypted_token = cache_data["encrypted_token"]
                    self.expires = cache_data["expires"]
                    self.customer_id = cache_data["customer_id"]
                    self.request_id = cache_data["request_id"]
                    self.server_info = cache_data["server_info"]
                    # We DO NOT set self.device_id here because that's what we're in the process of determining
                    
                    os.environ["TZ_AUTO_TOKEN"] = self.jwt_token
                    os.environ["TZ_AUTO_ENC_TOKEN"] = self.encrypted_token
                    
                    # Don't call display here - we're still in the middle of initialization
                    # self.display(read_cache=True)   
                    
                    return cache_data  # Return the actual cache data, not just True
                else:
                    print("⚠️ 快取已過期或無效，將重新登入。")  # Cache expired or invalid
            except Exception as e:
                print(f"⚠️ 讀取快取時發生錯誤: {e}")  # Error reading cache
        return {}  # Return empty dict if no valid cache, not False

    def login(self):
        cache_data = self.load_cache()
        if cache_data and "jwt_token" in cache_data:  # Check if we have a token in the returned data
            self.display(read_cache=True)  # Now display the cached data here
            self.save_cache()
            return True

        payload = {
            "CustomerId": self.customer_id,
            "Password": self.password,
            "DeviceId": self.device_id,
            "PopulateServers": "True", 
            "Application": self.application,
            "Version": self.version
        }

        response = requests.post(self.login_url, data=payload)

        if response.status_code == 200:
            print("✅ Login Successful!")
            self.process_response(response.json())
            self.save_cache()
            return True
        else:
            print("❌ Login Failed!")
            print("Status Code:", response.status_code)
            print("Error:", response.text)
            return False

    def process_response(self, json_response):
        self.jwt_token = json_response.get("jwtToken", "N/A")
        self.encrypted_token = json_response.get("encryptedJWTToken", "N/A")
        self.expires = json_response.get("expires", "N/A")
        self.customer_id = json_response.get("customerID", "N/A")
        self.request_id = json_response.get("id", "N/A")

        os.environ["TZ_AUTO_TOKEN"] = self.jwt_token
        os.environ["TZ_AUTO_ENC_TOKEN"] = self.encrypted_token

        servers = json_response.get("availableServers", {}).get("servers", [])
        if servers:
            server = servers[0]
            self.server_info = {
                "name": server.get("name", "N/A"),
                "ip": server.get("ip", "N/A"),
                "port": server.get("port", "N/A")
            }
        else:
            self.server_info = {"name": "N/A", "ip": "N/A", "port": "N/A"}

        self.display()

    def save_cache(self):
        data = {
            "jwt_token": self.jwt_token,
            "encrypted_token": self.encrypted_token,
            "expires": self.expires,
            "customer_id": self.customer_id,
            "request_id": self.request_id,
            "server_info": self.server_info,
            "device_id": self.device_id  # Save device_id in the cache
        }
        with open(self.cache_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 Token and info cached to: {self.cache_file}")

    def display(self, read_cache=False):
        table_data = [
            ["Field", "Value"],
            ["JWT Token", self.jwt_token[:50] + "..."],
            ["Expires", self.expires],
            ["Encrypted Token (truncated)", self.encrypted_token[:50] + "..."],
            ["Customer ID", self.customer_id],
            ["Request ID", self.request_id],
            ["Server Info", f"Name: {self.server_info['name']}\nIP: {self.server_info['ip']}\nPort: {self.server_info['port']}"],
            ["Device ID", self.device_id]
        ]

        if read_cache:
            print("\n🔑 Token loaded from cache:")
        else:
            print("\n🔐 Tokens saved to environment variables:")
            print(f"  - TZ_AUTO_TOKEN: {self.jwt_token}")
            print(f"  - TZ_AUTO_ENC_TOKEN: {self.encrypted_token}")
            print("\n📋 Response Details:")
        print(tabulate(table_data, headers="firstrow", tablefmt="grid"))

if __name__ == "__main__":
    tz_login = TradeZeroLogin()
    tz_login.login()
