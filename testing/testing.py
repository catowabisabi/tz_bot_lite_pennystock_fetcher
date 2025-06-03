import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database._mongodb.mongo_handler import MongoHandler
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


mongo_handler = MongoHandler()


def setup_date():
    #region Setting up Date
    ny_time = datetime.now(ZoneInfo("America/New_York"))
    today_str = ny_time.strftime('%Y-%m-%d')
    yesterday = ny_time - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')
    return today_str, yesterday_str


    
def insert_top_gainers_to_db(list_of_tickers):
    today_str, yesterday_str = setup_date()
    existing_top_gainers = mongo_handler.find_doc("today_top_list", {'today_date': today_str})
    # get the top_list from existing_top_gainers
    if not existing_top_gainers:
        print("No top gainers found")
    else:       
        print("Top gainers found")
        mongo_handler.upsert_top_list("today_top_list", list_of_tickers)
        print("Top gainers updated")
        existing_top_gainers = mongo_handler.find_doc("today_top_list", {'today_date': today_str})
        print(existing_top_gainers)


top_gainers_data = ["XXXX", "MSFT"]

insert_top_gainers_to_db(top_gainers_data)
