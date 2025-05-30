
import pytz
import os
import pandas as pd
import re
#import datetime
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from polygon import RESTClient
from polygon.rest.models import (
    TickerSnapshot,
)

from program_starter.class_zeropro_starter import logger 
from database._mongodb.mongo_handler import MongoHandler
from data_handler._data_handler import DataHandler
from dotenv import load_dotenv
load_dotenv(override=True)
from api_tradezero.api_auth import TzAuth



#region Polygon Controller
class PolygonController:
    def __init__(self):
        logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Initializing MainController")
        
        #region INITIALIZATION
        self.ny_time = datetime.now(ZoneInfo("America/New_York"))
        self.today_str = self.ny_time.strftime('%Y-%m-%d')
        self.polygon_api_key = os.getenv("POLYGON_KEY")
        self.polygon_client = RESTClient(self.polygon_api_key)
        self.top_gainers = []
    

        
    #region Get Top Gainers
    def get_top_gainers(self): # get top gainers raw data
        logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Starting to get top gainers raw data")
        self.top_gainers = self.polygon_client.get_snapshot_direction(
        "stocks",
        direction="gainers",
        )
        return self.top_gainers
    
    def print_list_of_items(self, list_of_items):
        for item in list_of_items:
            print(item)
        
    def fmt(self, value):
        return round(value, 2) if isinstance(value, (int, float)) else value

    def get_top_gainers_data(self): # get top gainers clean data
        logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Starting to get top gainers clean data")
        self.top_gainers_data = []
        for item in self.get_top_gainers():
            # verify this is a TickerSnapshot
            if isinstance(item, TickerSnapshot):
                row = {
                'Ticker': item.ticker,
                'Today_Open': self.fmt(item.day.open) if item.day else None,
                'Today_High': self.fmt(item.day.high) if item.day else None,
                'Today_Low': self.fmt(item.day.low) if item.day else None,
                'Today_Close': self.fmt(item.day.close) if item.day else None,
                'Today_Volume': self.fmt(item.day.volume) if item.day else None,
                #'Today_VWAP': self.fmt(item.day.vwap) if item.day else None,

                #'Prev_Open': self.fmt(item.prev_day.open) if item.prev_day else None,
                #'Prev_High': self.fmt(item.prev_day.high) if item.prev_day else None,
                #'Prev_Low': self.fmt(item.prev_day.low) if item.prev_day else None,
                'Prev_Close': self.fmt(item.prev_day.close) if item.prev_day else None,
                #'Prev_Volume': self.fmt(item.prev_day.volume) if item.prev_day else None,
                #'Prev_VWAP': self.fmt(item.prev_day.vwap) if item.prev_day else None,

                'Min_Open': self.fmt(item.min.open) if item.min else None,
                'Min_High': self.fmt(item.min.high) if item.min else None,
                'Min_Low': self.fmt(item.min.low) if item.min else None,
                'Min_Close': self.fmt(item.min.close) if item.min else None,
                'Min_Volume': self.fmt(item.min.volume) if item.min else None,
                'Min_VWAP': self.fmt(item.min.vwap) if item.min else None,

                'Today_Change': self.fmt(item.todays_change),
                'Change_%': self.fmt(item.todays_change_percent),
                }
                self.top_gainers_data.append(row)

        #print(f"Top Gainers Data: {self.top_gainers_data}")

        df = pd.DataFrame(self.top_gainers_data)
        pd.set_option('display.max_columns', None)  # 顯示所有欄位
        print(df.to_string(index=False))

        return self.top_gainers_data





    


#region MAIN





def main(debug = False):

    #region Setting up Date
    ny_time = datetime.now(ZoneInfo("America/New_York"))
    today_str = ny_time.strftime('%Y-%m-%d')
    yesterday = ny_time - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')


    #region Setting up Mongo
    # Create Collections and Check if Top Gainers are already in MongoDB
    logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Setting up MongoDB")
    mongo_handler = MongoHandler()
    today_top_list_doc_name = "today_top_list"
    mongo_handler.create_collection(today_top_list_doc_name)
    mongo_handler.create_collection("fundamentals_of_top_list_symbols")
    today_top_list = mongo_handler.find_doc(today_top_list_doc_name, {'today_date': today_str})
    
    if len(today_top_list) > 0:
        logger.info(f"Today Top Gainers in Database Found:            {today_top_list[0]['top_list']}")
        logger.info(f"Number of Fundamentals in Database Found:       {len(mongo_handler.find_doc("fundamentals_of_top_list_symbols", {'today_date': today_str}))}")
    else:
        logger.info(f"Today Top Gainers Not Found")


    #region Get Top Gainers
    polygon_controller = PolygonController()
    top_gainers_price_data = polygon_controller.get_top_gainers_data()
    
    if debug:
        logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: 1st Top Gainers Price Data: {str(top_gainers_price_data[0])}\n")
    print()
    


    # get top gainers symbols
    top_gainers_symbols = [item['Ticker'] for item in top_gainers_price_data]
    logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Top Gainers Symbols: {str(top_gainers_symbols)}\n")

    # Filter symbols by Today_Close > 1 and < 10, Today_Volume > 100,000, Change_% > 50
    filtered_top_gainers_symbols = [item['Ticker'] for item in top_gainers_price_data if item['Min_Close'] > 1 and item['Min_Close'] < 50  and item['Change_%'] > 50 and (len(item['Ticker']) <= 4)] #and item['Min_Volume'] > 100000
    logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Filtered Top Gainers Symbols: {str(filtered_top_gainers_symbols)}\n")


    def clean_symbols(symbols):
            # Remove non-alphabetic characters to clean up stock symbols
            return [re.sub(r'[^A-Z]', '', symbol) for symbol in symbols]


    clean_filtered_top_gainers_symbols = clean_symbols(filtered_top_gainers_symbols) #['SBET', 'MBAVW', 'FAAS']

    









    """clean_filtered_top_gainers_symbols = clean_symbols(['HKD', 
                                                        'LZMH',
                                                        'PLRZ', 
                                                        'KTTA',
                                                        'MRIN', 
                                                        'FOXO', 
                                                        'CHEB']
                                                        )#debug """











    logger.info(f"{datetime.now(pytz.timezone('US/Eastern'))}: Cleaned Filtered Symbols: {str(clean_filtered_top_gainers_symbols)}\n")
    #endregion

    #region DataHandler
    data_handler = DataHandler()

    # DataHandler 流程 Process
    # step 1: 拿最新的 fundamentals (TradeZero API), get the latest fundamentals
    # step 2: 加入today_day後保存到db, 更新fundamentals, 主要是Prices

    # step 3: 看看有沒有現有的existing_suggestion, 如果有, 不是最新的, 不需要分析第二次
    # step 4: 抽出需要分析的symbols, symbols to analyze

    # step 5: 執行分析 News Summary and Suggestions
    # step 6: 把Suggestions 儲存到DB (最新沒有分析過的標的), 如果有, 不是最新的, 不需要分析第二次
    # step 6.1: 現時, DB中的資料是包括了Suggestion 和 Fundamentals的

    # step 7: 在Python 中 合併這個資料, 為merged_data, (這個資料是包括了Suggestion 和 Fundamentals的)

    # step 8: 找出沒有做過Sec Filings Analysis的標的, 並執行Sec Filings Analysis
    # step 9: 把Sec Filings Analysis 儲存到DB

    # step 10: 在Python 中 合併這個資料, 為merged_data2, 這個包括了:
    #  Fundamentals, News Summary (Suggestion),  Sec Filings Analysis

    # extra: Short Squeeze Scanner results are included in fundamentas like "float_risk"
    
    top_gainners_fundamentals, sec_analysis_results = data_handler.run(clean_filtered_top_gainers_symbols) #top_gainners_symbols contain all data of every top gainers
    #print(top_gainners_fundamentals[0])
    #print()
    #print(sec_analysis_results[0])
    # 
    # step 11 所有野SAVE左係DB, 仲差create chart

    print(top_gainners_fundamentals[0]['1m_chart_data'][0])


    #

#region Wrapped Main in a Scheduler,
# this scheduler is to check if it should run in a specific time period.
from utilities.trade_scheduler import TradingScheduler
def scheduled_main():
    scheduler = TradingScheduler()
    if scheduler.should_run_now(debug=False):
        try:
            main()
            print(f"✅ Execution completed at {datetime.now(pytz.timezone('US/Eastern'))}")
        except Exception as e:
            print(f"❌ Error during execution: {e}")
    else:
        print(f"⏳ Skipped at {datetime.now(pytz.timezone('US/Eastern'))} (Outside trading time or not the interval)")



# region Scheduler (run every minute)
import schedule
import time
def schedule_jobs(callback):
    logger.info("\n\nScheduler started. Press Ctrl+C to exit.")
    schedule.every(1).minutes.do(callback)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    #tz_auth = TzAuth()
    #tz_auth.login_and_cache_token()
    main()
    schedule_jobs(lambda: scheduled_main())
    

    