import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from collections import defaultdict




class TradeZeroPositionFetcher:
    def __init__(self, token=None):
        # 初始化 TokenCache 來處理 Token 的加載和儲存
        from tz_api.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token
        self.customer_id = self.tz_auth.customer_id

        
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

    def print_positions(self,positions):
        print("-" * 60)
        print("📊 Position List")
        for pos in positions:
            print(f"🧾 Symbol: {pos['symbol']}")
            print(f"   ├─ Side: {pos['side']}")
            print(f"   ├─ Shares: {pos['shares']}")
            print(f"   ├─ Average Price: {pos['priceAvg']:.2f}")
            print(f"   ├─ Open Price: {pos['priceOpen']:.2f}")
            print(f"   ├─ Close Price: {pos['priceClose']:.2f}")
            print(f"   ├─ Realized P/L: ${pos['realized']:.2f}")
            print(f"   ├─ Shares In: {pos['sharesIn']}")
            print(f"   ├─ Shares Out: {pos['sharesOut']}")
            print(f"   ├─ Created: {pos['createdDate']}")
            print(f"   └─ Updated: {pos['updatedDate']}")
            print("-" * 60)

# 示例用法（使用你提供的 list 當作變數 positions）
# print_positions(positions)


    def fetch_positions(self):
        self.url = f"https://api.tradezero.com/v1/accounts/api/accounts/positions/{self.customer_id}"
        try:
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()  # 檢查是否成功
            data = response.json()
            self.print_positions(data)
            return data


        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if e.response is not None:
                print("Status Code:", e.response.status_code)
                print("Response:", e.response.text)
            return None

    from collections import defaultdict

    def print_orders_summary(self, orders):
        print("-" * 70)
        print("📊 Order Summary (Merged by Symbol + Side)")

        summary = defaultdict(lambda: {'qty': 0.0, 'canceled_qty': 0.0, 'count': 0, 'limit_prices': set()})

        for order in orders:
            if order['status'] != 'Canceled':
                symbol = order['symbol']
                side = order['side']
                quantity = float(order['orderQuantity'])
                limit_price = order['limitPrice']
                canceled_qty = float(order.get('cancelledQuantity', 0))

                key = (symbol, side)
                summary[key]['qty'] += quantity
                summary[key]['canceled_qty'] += canceled_qty
                summary[key]['count'] += 1
                summary[key]['limit_prices'].add(limit_price)

        for (symbol, side), data in summary.items():
            prices = ", ".join(f"${p}" for p in sorted(data['limit_prices']))
            print(f"+{'-'*70}+")
            print(f"| Symbol: {symbol:<6} | Side: {side:<10} | Orders: {data['count']:<3}               |")
            print(f"| Total Qty: {data['qty']:<8.2f} | Canceled: {data['canceled_qty']:<8.2f}         |")
            print(f"| Limit Prices: {prices:<50} |")
            print(f"+{'-'*70}+")
        print("-" * 70)




    def fetch_orders(self):
        self.url = f"https://api.tradezero.com/v1/accounts/api/accounts/orders/{self.customer_id}"
        try:
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()  # 檢查是否成功
            data = response.json()
            self.print_orders_summary(data)
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if e.response is not None:
                print("Status Code:", e.response.status_code)
                print("Response:", e.response.text)
            return None



if __name__ == "__main__":
    fetcher = TradeZeroPositionFetcher()
    fetcher.fetch_orders()