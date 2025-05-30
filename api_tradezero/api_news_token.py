import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from tabulate import tabulate


class NewsNegotiator:
    def __init__(self):

        from api_tradezero.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token
        self.CUSTOMER_ID = self.tz_auth.customer_id
        print(f"✅ Customer ID: {self.CUSTOMER_ID}")	

        self.url = "https://api.tradezero.com/v1/news/newsHub/negotiate?negotiateVersion=1"
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

    def negotiate(self):
        """發送請求協商最新的新聞"""
        try:
            response = requests.post(self.url, headers=self.headers)
            response.raise_for_status()  # 這會檢查非 2xx 的狀態碼
            data = response.json()  # 假設 API 返回的是 JSON 格式
            self.news_negotiator_display(data)

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if e.response is not None:
                print("Status Code:", e.response.status_code)
                print("Response:", e.response.text)

    def news_negotiator_display(self, data):
        """格式化顯示 API 回應"""
        if isinstance(data, dict):
            table = [["Key", "Value"]]
            for k, v in data.items():
                if isinstance(v, list):
                    pass
                else:
                    table.append([k, v])
            print("\n📡 Negotiation Response:")
            print(tabulate(table, headers="firstrow", tablefmt="grid"))
        else:
            print("\n⚠️ Unexpected response format:")
            print(data)

# 使用方式：
if __name__ == "__main__":
    negotiator = NewsNegotiator()
    negotiator.negotiate()
