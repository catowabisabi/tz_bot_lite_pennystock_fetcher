import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from bson import json_util
import requests
import datetime
from datetime import  timezone, timedelta
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(override=True)




# region Summarizer====
class Summarizer:
    def __init__(self):
        self.key= os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.key)

    #region GPT Summarizer
    def summarize(self, text: str) -> str:
        prompt = f"請根據以下新聞內容生成繁體中文簡短摘要：\n\n{str(text)}"
        completion = self.client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "developer", "content": "You are a helpful assistant. You take news content as input and generate a detailed summary. Do not include the original news content in the summary."},
            {"role": "user", "content": prompt}
        ]
        )
        summary = completion.choices[0].message.content.strip()
        print(f"\n📰 Summary: {summary}\n")
        return summary
    

    #region GPT suggestion
    def suggestion(self, text: str) -> str:
        prompt = f"請根據以下新聞內容生成簡短建議：\n\n{str(text)}"
        completion = self.client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "developer", "content": "用戶是一個日內交易者, 他主要的是做空股票的交易者, 用戶會提供最新的新聞的一些總結, 如果新聞中有非常強的正面情緒, 請向用戶列出風險, 解釋為何不建議做空, 但如果沒有當天的新聞, 或新聞中的正面情緒不高, 請向用戶列出建議。"},
            {"role": "user", "content": prompt}
        ]
        )
        summary = completion.choices[0].message.content.strip()
        #print(summary)
        return summary



#region RVLNewsAnalyzer====
class RVLNewsAnalyzer:
    def __init__(self):
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.yesterday = self.now - timedelta(days=2)
        self.summerizer = Summarizer()


    #region Is Recent News
    def is_recent(self, timestamp):
        try:
            news_time = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
            return news_time.date() in {self.now.date(), self.yesterday.date()}
        except Exception as e:
            print("⚠️ Timestamp error:", e)
            return False


    #region Clean HTML
    def clean_html(self, text):
        if text.startswith("http"):  # 假設傳進來的是 URL
            try:
                response = requests.get(text)
                response.raise_for_status()
                html_content = response.text
                return BeautifulSoup(html_content, "html.parser").get_text()
            except requests.exceptions.RequestException as e:
                print(f"❌ Failed to fetch URL: {e}")
                return ""
        else:
            return BeautifulSoup(text or "", "html.parser").get_text()

    #region News Analyzer 
    def analyze(self, news_data: list):
        recent_news = []
        for news in news_data:
            
            if not self.is_recent(news.get("utcTime")):
                #print(f"⚠️ Skipping non-recent news: 不是最近的新聞: {datetime.datetime.fromtimestamp(news['utcTime'], tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} - {news['title']}")
                continue

            news_time = datetime.datetime.fromtimestamp(news["utcTime"])
            readable_time = news_time.strftime('%Y-%m-%d %H:%M:%S UTC')

            
            
            entry = {
                "title": self.clean_html(news.get("title", "")),
                "time": readable_time,
                "link": news.get("link", ""),
                "html": self.clean_html(news.get("link", ""))
            }

            summary = self.summerizer.summarize(entry)

            entry = {
                "title": self.clean_html(news.get("title", "")),
                "time": readable_time,
                "link": news.get("link", ""),
                "summary": summary
            }

            recent_news.append(entry)



        # 依時間排序，取最新的 5 則
        recent_news = sorted(recent_news, key=lambda x: x["time"], reverse=True)[:5]

        #print(json.dumps(recent_news, indent=2, ensure_ascii=False))
        return recent_news



#region TZ NewsFetcher====
class NewsFetcher:
    def __init__(self):
        

        from tz_api.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token

        self.news_analyzer = RVLNewsAnalyzer()
        self.summerizer = Summarizer()

        self.base_url = "https://api.tradezero.com/v1/news/api/news/get"


    def get_symbols_news_and_analyze(self, symbols: list[str], page: int = 1, num_results: int = 5):
        
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        suggestions = []
        for symbol in symbols:
            print("================================================")
            print(f"\n\n\n📰 Fetching news...:{symbol}")
            params = {
                "Page": page,
                "Symbol": symbol.upper(),
                "Keyword": "",
                "NumOfResults": num_results
            }

            try:
                response = requests.get(self.base_url, headers=headers, params=params)
                response.raise_for_status()
                # 取得 JSON 中的新聞陣列
                all_news = response.json()

                # 過濾只包含這個 symbol 的新聞
                filtered_news = [
                    news for news in all_news
                    if news.get("symbols") == [symbol.upper()]
                ]

                data = filtered_news
                #print(json.dumps(data, indent=2, ensure_ascii=False))

                summaries = self.news_analyzer.analyze(data)
                print(f"\n\n 📰 Summaries for {symbol.upper()}: {json.dumps(summaries, indent=2, ensure_ascii=False)}")

                suggestion = self.summerizer.suggestion(summaries)
                print(f"\n\n 📰 Suggestion for {symbol.upper()}: {suggestion}")
    
                suggestions.append({"symbol": symbol, "suggestion": 	suggestion})
        
                
                
                #=================================================not printing the news, we need the suggestion only
                #print(f"\n📰 News for {symbol.upper()}:")
                if data and isinstance(data, list):
                    for news in data[:num_results]:
                        
                        title = news.get("title", "No title")
                        link = news.get("link", "")
                        publisher = news.get("publisher", "Unknown publisher")
                        timestamp = news.get("utcTime")
                        if timestamp:
                            dt = datetime.datetime.fromtimestamp(timestamp, datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
                        else:
                            dt = "Unknown time"

                        #print(f"- {title}\n  📅 {dt} | 🗞️ {publisher}\n  🔗 {link}\n")
                else:
                    pass
                    #print("⚠️ No news data available.")
                #=================================================================================
            
            except requests.exceptions.RequestException as e:
                print(f"❌ Failed to fetch news for {symbol.upper()}: {e}")
                if hasattr(e, "response") and e.response:
                    print("Status Code:", e.response.status_code)
                    print("Response:", e.response.text)


        return suggestions

            
    
    def analyze_news(self, news_data):
        try:
            print("\n📰 Analyzing news...")
            analyzed_news = self.news_analyzer.analyze(news_data)
            
            print(json_util.dumps(analyzed_news, indent=2, ensure_ascii=False))
            return analyzed_news
        except Exception as e:
            print(f"❌ Failed to analyze news: {e}")
      


#region MAIN ENTRY
if __name__ == "__main__":
    fetcher = NewsFetcher()
    suggestions = fetcher.get_symbols_news_and_analyze(["AAPL", "MSFT"])

    #fake_news_data = {'publisherId': 45154555, 'keywords': ['NEWS', 'PRICE TARGET', 'ANALYST RATINGS'], 'symbols': ['MSFT'], 'utcTime': 1746136689, 'id': 6773239, 'title': 'Jefferies Maintains Buy on Microsoft, Raises Price Target to $550', 'link': 'https://www.benzinga.com/news/25/05/45154555/jefferies-maintains-buy-on-microsoft-raises-price-target-to-550', 'publisher': 'Benzinga Newsdesk', 'newsType': 'Headline', 'timing': 'None', 'msgType': 'NM_SYSMSG', 'symbolCode': 0, 'body': None}


   #news_analyzer = RVLNewsAnalyzer()
   # news_analyzer.analyze([fake_news_data])