import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
from tabulate import tabulate





class NewsFetcher:
    def __init__(self, token=None):
        from tz_api.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token

        self.url = "https://api.tradezero.com/v1/news/api/news/get"
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

    def fetch_news(self, page=1, symbol=None, keyword=None, num_of_results=300):
        """根據給定的參數拉取新聞資料"""
        params = {
            "Page": page,
            "Symbol": symbol or "",
            "Keyword": keyword or "",
            "NumOfResults": num_of_results
        }

        try:
            response = requests.get(self.url, headers=self.headers, params=params)
            response.raise_for_status()  # 檢查是否成功
            data = response.json()

            if not data:
                print(f"⚠️ No news found for page {page} with symbol '{symbol}' and keyword '{keyword}'.")
                return

            # 顯示資料
            self.latest_news_display(data)

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if e.response is not None:
                print("Status Code:", e.response.status_code)
                print("Response:", e.response.text)

    def latest_news_display(self, data):
        """將新聞資料格式化為表格並打印"""
        table = [["ID", "Title", "Publisher", "Keywords", "Link"]]
        for news_item in data:
            table.append([
                news_item["id"],
                news_item["title"][:60] + "..." if len(news_item["title"]) > 30 else news_item["title"],
                news_item["publisher"],
                ", ".join(news_item["keywords"]) if "keywords" in news_item else "N/A",
                news_item["link"][:30] + "..." if len(news_item["link"]) > 30 else news_item["link"]
            ])

        print("\n📘 Latest News:")
        print(tabulate(table, headers="firstrow", tablefmt="grid"))


if __name__ == "__main__":
    # 使用方式：
    news_fetcher = NewsFetcher()  # 這裡假設你已經有設定好 JWT Token，會自動從 cache 或登入獲取
    news_fetcher.fetch_news(page=1, symbol="TNON", keyword=None, num_of_results=3)  # 拉取第一頁，無指定符號和關鍵字，最多3條新聞
