import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bson import json_util

import json
import requests
from datetime import datetime, time as dtime, timedelta




class ChartAnalyzer:
    def __init__(self, symbol: str, token=None, cache_file=".tz_token_cache.json"):
   
        self.symbol = symbol

        from tz_api.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token

        self.headers = {"Authorization": f"Bearer {self.jwt_token}"}
        self.base_url = "https://api.tradezero.com/v1/charts/api/chart/csvv2"
        self.market_open_time = dtime(9, 30)

        # 初始化時獲取數據
        print(f"🔍 正在為 {self.symbol} 獲取圖表數據...")
        self.data_1m = self.get_1m()
        self.update_last_day_data()
        self.data_5m = self.get_5m()
        self.data_1d = self.get_1d()
        print(f"✅ {self.symbol} 圖表數據準備就緒")

    def __repr__(self):
        return f"<ChartAnalyzer(symbol={self.symbol})>"
    
    def update_last_day_data(self):
        """從 self.data_1m 中提取最後一個交易日的資料，存入 self.last_day_data_1m"""
        if not self.data_1m:
            self.last_day_data_1m = []
            return

        # 提取所有日期（不重複）
        all_dates = sorted(set(x["datetime"].date() for x in self.data_1m))
        last_date = all_dates[-1]

        # 過濾出最後一日資料
        self.last_day_data_1m = [x for x in self.data_1m if x["datetime"].date() == last_date]

    def get_chart_data(self, ms_interval: int, max_candles: int = 1200):
        """獲取指定間隔的K線圖數據"""
        params = {
            "symbol": self.symbol,
            "msInterval": ms_interval,
            "maxCandles": max_candles
        }
        
        try:
            print(f"🔄 正在請求 {ms_interval} 毫秒間隔的圖表數據...")
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            if len(lines) <= 1:  # 只有標題行或空數據
                print(f"⚠️ 未找到符合條件的數據：{self.symbol}, 間隔：{ms_interval}")
                return []
                
            # 跳過標題行
            lines = lines[1:]
            data = []
            
            for line in lines:
                if not line.strip():  # 跳過空行
                    continue
                    
                parts = line.split(',')
                if len(parts) < 6:  # 數據不完整
                    print(f"⚠️ 數據格式不完整：{line}")
                    continue
                    
                dt_str = parts[0].strip()
                
                # 嘗試多種日期格式
                dt = None
                for fmt in ["%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"]:
                    try:
                        dt = datetime.strptime(dt_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if dt is None:
                    print(f"⚠️ 無法解析時間格式：{dt_str}")
                    continue
                
                try:
                    data_point = {
                        "datetime": dt,
                        "open": float(parts[1]),
                        "high": float(parts[2]),
                        "low": float(parts[3]),
                        "close": float(parts[4]),
                        "volume": float(parts[5]) if parts[5].strip() else 0,
                    }
                    data.append(data_point)
                except (ValueError, IndexError) as e:
                    print(f"❌ 解析數據錯誤：{line}, 錯誤：{e}")
                    continue
            
            # 按時間排序數據
            data.sort(key=lambda x: x["datetime"])
            print(f"✅ 成功獲取 {len(data)} 條數據")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 請求失敗: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"狀態碼: {e.response.status_code}")
                print(f"回應: {e.response.text}")
                
                # 處理認證錯誤
                if e.response.status_code in [401, 403] and hasattr(self, 'login_handler'):
                    print("🔄 Token 可能已過期，嘗試重新登入...")
                    # 刪除快取文件以強制重新登入
                    if os.path.exists(self.login_handler.cache_file):
                        os.remove(self.login_handler.cache_file)
                    
                    # 重新登入
                    login_success = self.login_handler.login()
                    if login_success:
                        self.jwt_token = self.login_handler.jwt_token
                        self.headers["Authorization"] = f"Bearer {self.jwt_token}"
                        print("✅ 重新登入成功，正在重試請求...")
                        return self.get_chart_data(ms_interval, max_candles)  # 重試請求
            return []

    def get_1m(self):
        """獲取1分鐘K線數據"""
        return self.get_chart_data(60000)
    
    def get_5m(self):
        """獲取5分鐘K線數據"""
        return self.get_chart_data(300000)
    
    def get_1d(self):
        """獲取日K線數據"""
        return self.get_chart_data(0)

    def to_two_decimal(self, value):
        """將數值格式化為保留兩位小數"""
        return round(value, 2) if value is not None else None

    def get_premarket_data(self):
        """獲取盤前數據"""
        return [x for x in self.last_day_data_1m if x["datetime"].time() < self.market_open_time]

    def get_market_data(self):
        """獲取盤中數據"""
        return [x for x in self.last_day_data_1m if x["datetime"].time() >= self.market_open_time]

    def get_premarket_high(self):
        """獲取盤前最高價"""
        premarket = self.get_premarket_data()
        return self.to_two_decimal(max(x["high"] for x in premarket)) if premarket else None

    def get_premarket_low(self):
        """獲取盤前最低價"""
        premarket = self.get_premarket_data()
        return self.to_two_decimal(min(x["low"] for x in premarket)) if premarket else None

    def get_market_open_high(self, time_range=("09:31", "09:45")):
        """獲取資料中最後一天指定時間段內的最高價（支援跨日）"""
        try:
            start = dtime(*map(int, time_range[0].split(":")))
            end = dtime(*map(int, time_range[1].split(":")))

            if not self.data_1m:
                print("⚠️ 沒有1分鐘資料")
                return None

            # 取出資料中最後一天的日期
            last_date = self.data_1m[-1]["datetime"].date()

            if start <= end:
                # 正常時間段（如 09:31–09:45）
                opens = [
                    x for x in self.data_1m
                    if x["datetime"].date() == last_date and start <= x["datetime"].time() <= end
                ]
            else:
                # 跨午夜時間段
                opens = [
                    x for x in self.data_1m
                    if (
                        (x["datetime"].date() == last_date and x["datetime"].time() >= start) or
                        (x["datetime"].date() == last_date + timedelta(days=1) and x["datetime"].time() <= end)
                    )
                ]

            # 修正錯誤：你寫的是 x["low"]，但要抓 high
            highs = [x["high"] for x in opens if "high" in x and isinstance(x["high"], (int, float))]

            return self.to_two_decimal(max(highs)) if highs else None

        except (ValueError, IndexError) as e:
            print(f"❌ 解析時間範圍錯誤：{time_range}, 錯誤：{e}")
            return None

    from datetime import datetime, time as dtime, timedelta

    def get_market_open_low(self, time_range=("09:31", "09:45")):
        """獲取資料中最後一天指定時間段內的最低價（支援跨日）"""
        try:
            start = dtime(*map(int, time_range[0].split(":")))
            end = dtime(*map(int, time_range[1].split(":")))

            if not self.data_1m:
                print("⚠️ 沒有1分鐘資料")
                return None

            # 取出資料中最後一天的日期
            last_date = self.data_1m[-1]["datetime"].date()

            if start <= end:
                # 正常時間段（如 09:31–09:45）
                opens = [
                    x for x in self.data_1m
                    if x["datetime"].date() == last_date and start <= x["datetime"].time() <= end
                ]
            else:
                # 跨午夜時間段
                opens = [
                    x for x in self.data_1m
                    if (
                        (x["datetime"].date() == last_date and x["datetime"].time() >= start) or
                        (x["datetime"].date() == last_date + timedelta(days=1) and x["datetime"].time() <= end)
                    )
                ]

            # 取出最低價
            lows = [x["low"] for x in opens if "low" in x and isinstance(x["low"], (int, float))]

            return self.to_two_decimal(min(lows)) if lows else None

        except (ValueError, IndexError) as e:
            print(f"❌ 解析時間範圍錯誤：{time_range}, 錯誤：{e}")
            return None




    def get_day_high(self):
        """獲取當日最高價"""
        if not self.last_day_data_1m:
            return None
        return self.to_two_decimal(max(x["high"] for x in self.last_day_data_1m))

    def get_day_low(self):
        """獲取盤中最低價（僅考慮盤中數據）"""
        market_data = self.get_market_data()
        if not market_data:
            return None
        return self.to_two_decimal(min(x["low"] for x in market_data))

    def get_day_close(self):
        """獲取當日收盤價"""
        if not self.last_day_data_1m:
            return None
        # 按時間排序，取最新的收盤價
        sorted_data = sorted(self.last_day_data_1m, key=lambda x: x["datetime"])
        return self.to_two_decimal(sorted_data[-1]["close"])

    def get_yesterday_close(self):
        """獲取昨日收盤價"""
        if len(self.data_1d) < 2:
            return None
        # 按時間排序，取倒數第二個的收盤價
        sorted_data = sorted(self.data_1d, key=lambda x: x["datetime"])
        return self.to_two_decimal(sorted_data[-2]["close"])

    def get_high_change_percentage(self):
        """計算最高價相對於昨日收盤的漲幅百分比"""
        y_close = self.get_yesterday_close()
        d_high = self.get_day_high()
        if y_close and d_high:
            return round((d_high - y_close) / y_close * 100, 2)
        return None

    def get_close_change_percentage(self):
        """計算收盤價相對於昨日收盤的漲跌幅百分比"""
        y_close = self.get_yesterday_close()
        d_close = self.get_day_close()
        if y_close and d_close:
            return round((d_close - y_close) / y_close * 100, 2)
        return None
    
    def get_most_volume_high(self):
        """獲取成交量最大的綠色K線的最高價（包括盤前和盤中）"""
        # 包括所有數據（盤前和盤中）
        greens = [x for x in self.last_day_data_1m if x["close"] >= x["open"] and x["volume"] > 0]
        if not greens:
            return None
        most = max(greens, key=lambda x: x["volume"])
        return self.to_two_decimal(most["high"])

    def get_most_volume_low(self):
        """獲取盤中成交量最大的紅色K線的最低價（僅盤中）"""
        # 只包括盤中數據
        market_data = self.get_market_data()
        reds = [x for x in market_data if x["close"] < x["open"] and x["volume"] > 0]
        if not reds:
            return None
        most = max(reds, key=lambda x: x["volume"])
        return self.to_two_decimal(most["low"])
    
    def get_key_levels(self, level_number=5):
        """
        獲取關鍵價格水平（返回最小的幾個水平）
        
        參數:
        level_number (int): 要返回的關鍵價格水平數量
        
        返回:
        list: 排序後的關鍵價格水平列表（最多返回指定數量的最小水平）
        """
        # 1. 計算當天早上4點開始到最新時間的總volume
        current_volume = self._get_volume_since_4am()
        print(f"current_volume: {current_volume}")
        
        # 2. 獲取當天的day high
        day_high = self.get_day_high()
        if day_high is None:
            return []
        
        # 3. 在daily圖中找出所有比當前總volume高的蠟燭圖
        daily_candles = self.data_1d
        if not daily_candles:
            return []
        
        # 4. 篩選出volume比當前高且high比當前day high高的蠟燭圖
        filtered_candles = [
            candle for candle in daily_candles 
            if candle["volume"] > current_volume and candle["high"] > day_high
        ]
        
        # 5. 如果沒有符合條件的蠟燭圖，返回空列表
        if not filtered_candles:
            return []
        
        # 6-7. 處理符合條件的蠟燭圖
        key_levels = []
        for candle in filtered_candles:
            if candle["low"] > day_high:
                key_levels.append(self.to_two_decimal(candle["low"]))
            else:
                key_levels.append(self.to_two_decimal(candle["high"]))
        
        # 8. 去重、排序
        key_levels = sorted(list(set(key_levels)))
        
        # 9. 只返回最小的幾個水平（不超過level_number）
        return key_levels[:level_number]

    def _get_volume_since_4am(self):
        """
        獲取從早上4點到最新時間的總成交量（輔助方法）
        """
        four_am = dtime(4, 0)
        market_data = [x for x in self.data_5m if x["datetime"].time() >= four_am]
        return sum(x["volume"] for x in market_data) if market_data else 0
    def run(self):
        """執行分析並返回所有數據點"""
        result = {
            "symbol": self.symbol,
            "premarket_high": self.get_premarket_high(),
            "premarket_low": self.get_premarket_low(),
            "market_open_high": self.get_market_open_high(),
            "market_open_low": self.get_market_open_low(),
            "day_high": self.get_day_high(),         # 包含盤前+盤中的最高價
            "day_low": self.get_day_low(),           # 僅盤中的最低價
            "day_close": self.get_day_close(),
            "yesterday_close": self.get_yesterday_close(),
            "high_change_percentage": self.get_high_change_percentage(),
            "close_change_percentage": self.get_close_change_percentage(),
            "most_volume_high": self.get_most_volume_high(),  # 盤前+盤中最大成交量綠K的高點
            "most_volume_low": self.get_most_volume_low(),    # 僅盤中最大成交量紅K的低點
        }
        key_levels = self.get_key_levels()
        result["key_levels"] = key_levels
        result["1m_chart_data"] = self.data_1m  
        result["5m_chart_data"] = self.data_5m
        result["1d_chart_data"] = self.data_1d
        
        return result


# CLI 執行範例
if __name__ == "__main__":
    symbol = input("請輸入股票代號（如 TSLA）: ").strip().upper()
    analyzer = ChartAnalyzer(symbol)
    result = analyzer.run()
    
    print(json_util.dumps(result, indent=2, ensure_ascii=False))
    

    #拎埋支持阻力