import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from tabulate import tabulate
from tz_api.api_auth import TzAuth


# region fundamentals

# login to tradezero and use it's api to fetch fundamentals by symbol
class FundamentalsFetcher:
    def __init__(self):
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token
        self.base_url = "https://api.tradezero.com/v1/fundamentals/api/fundamentals"


    def fetch(self, symbol: str):
        url = f"{self.base_url}?symbols={symbol.upper()}"
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if not data:
                print(f"⚠️ No data returned for symbol '{symbol.upper()}'.")
                return

            #self.display(data[0])
            return data

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if hasattr(e, "response") and e.response:
                print("Status Code:", e.response.status_code)
                print("Response:", e.response.text)

    def format_number(self, num):
        if not isinstance(num, (int, float)):
            return num
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.2f}K"
        return str(num)

    def display(self, data: dict):
        table = [["Field", "Value"]]
        for key, value in data.items():
            if value is not None:
                if key in ["float", "outstandingShares", "averageVolume3M", "sales", "bookValue", "turnoverPercentage"]:
                    value = self.format_number(value)
                table.append([key, value])
        print("\n📊 Fundamentals Data==:")
        print(tabulate(table, headers="firstrow", tablefmt="grid\n\n\n\n"))
    



    
    def fetch_symbols(self, symbols: list[str]):
        symbols_param = ",".join([s.upper() for s in symbols])
        url = f"{self.base_url}?symbols={symbols_param}"
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

        print(f"Fetching fundamentals for symbols: {', '.join(symbols)}")

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if not data:
                print("⚠️ No data returned for the requested symbols.")
                return []
            
            # 去重：根據 symbol 字段建一個 dict（保持順序）
            # 去重：根據 symbol 字段建一個 dict（保持順序）
            unique_data = {}
            for item in data:
                sym = item.get("symbol")
                if sym and sym not in unique_data:
                    unique_data[sym] = item

            for i, (sym, symbol_data) in enumerate(unique_data.items(), start=1):
                print(f"\n\n\nSymbol: {i} ({sym})")
                print("================================================")
                self.display(symbol_data)

            return list(unique_data.values())  # 總是返回 list

        except requests.RequestException as e:
            print(f"❌ Failed to fetch symbols due to: {e}")
            return []  # 例外時也返回空 list



if __name__ == "__main__":
    # 使用從 cache 加載的 token 或登錄
    fetcher = FundamentalsFetcher()
    #data  = fetcher.fetch("AAPL")
    #print(data)

    

    data = fetcher.fetch_symbols(["AAPL", "MSFT"])
    #print(data)
