# we are not using this
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from tabulate import tabulate
from dotenv import load_dotenv




class TradeZeroNegotiator:
    def __init__(self, token=None):
        from api_tradezero.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token

        
            
        self.url = "https://api.tradezero.com/v1/accounts/accountsHub/negotiate?negotiateVersion=1"
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

    def negotiate(self):
        try:
            # 發送 POST 請求
            response = requests.post(self.url, headers=self.headers)
            response.raise_for_status()  # 如果回應的狀態碼不是 200，會拋出例外

            # 解析伺服器回應
            data = response.json()

            # 顯示基本連線資訊
            self.display_base_info(data)

            # 顯示可用的傳輸方式
            self.display_transport_info(data)

        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error: {e}")
            if hasattr(e, "response") and e.response:
                print("狀態碼：", e.response.status_code)
                print("回應內容：", e.response.text)

    def display_base_info(self, data):
        base_info_table = [
            ["Field", "Value"],
            ["Negotiate Version", data.get("negotiateVersion", "N/A")],
            ["Connection ID", data.get("connectionId", "N/A")],
            ["Connection Token", data.get("connectionToken", "N/A")]
        ]
        print("\n🔗 基本連線資訊：")
        print(tabulate(base_info_table, headers="firstrow", tablefmt="grid"))

    def display_transport_info(self, data):
        transport_table = [["Transport", "Transfer Formats"]]
        for transport in data.get("availableTransports", []):
            transport_table.append([
                transport.get("transport", "N/A"),
                ", ".join(transport.get("transferFormats", []))
            ])
        print("\n🚀 可用的傳輸方式：")
        print(tabulate(transport_table, headers="firstrow", tablefmt="grid"))

if __name__ == "__main__":
    negotiator = TradeZeroNegotiator()      
    negotiator.negotiate()