import requests
import csv
jwt_token= "Token"
# 設定參數與 token
symbol = "AAPL"
ms_interval = 60000  # 1分鐘K線
max_candles = 1200
url = "https://api.tradezero.com/v1/charts/api/chart/csvv2"

headers = {
    "Authorization": "Bearer {}".format(jwt_token),
    "Content-Type": "application/json"
}

params = {
    "symbol": symbol,
    "msInterval": ms_interval,
    "maxCandles": max_candles
}

# 發送 GET 請求
response = requests.get(url, headers=headers, params=params)

# 檢查回應狀態
if response.status_code == 200:
    csv_text = response.text.strip().split("\n")
    print(f"✅ 成功獲取 {len(csv_text) - 1} 筆資料")
    print(csv_text)
    output_filename = "chart_1m.csv"

    with open(output_filename, "w", newline="") as f:
        writer = csv.writer(f)
        for row in csv_text:
            writer.writerow(row.split(","))
    
    print(f"✅ 成功儲存 {len(csv_text) - 1} 筆資料至 {output_filename}")
else:
    print(f"❌ 請求失敗：狀態碼 {response.status_code}")
    print(response.text)
