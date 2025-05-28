import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),  '..', '..')))
from program_starter.class_zeropro_starter import logger 
from get_gainer.zero_pro_inspector.zp_inspector import DynamicUIFinder
import re
from database._mongodb.mongo_handler import MongoHandler
from datetime import datetime
from zoneinfo import ZoneInfo


ny_time = datetime.now(ZoneInfo("America/New_York"))
today_str = ny_time.strftime('%Y-%m-%d')

class TopListHandler:
    """
    Handles retrieval and cleanup of the top gainers list from the UI.
    """

    def __init__(self):
        self.mongo_handler = MongoHandler()

    def get_data(self, hwnd):

        collection_name = "today_top_list"
        
        #print("debug anchor =============================================== 1 ===get_data")
        print(f"Collection is created: {self.mongo_handler.create_collection(collection_name)}")

        finder = DynamicUIFinder()
        logger.info("Fetching gainers list...")
        top_list_symbols, top_list_df = finder.get_list_of_gainers_and_save_md_with_hwnd(hwnd)
        #print("debug anchor =============================================== 2 ===get_data")
        top_list_df = top_list_df.rename(columns={'% Change': 'Percent_Change'})
        #print("debug anchor =============================================== 3 ===get_data")
        cleaned_symbols = self.clean_symbols(top_list_symbols)
        #print("debug anchor =============================================== 4 ===get_data")

        logger.info(f"Top List: {cleaned_symbols}")
        result = self.mongo_handler.upsert_top_list("today_top_list", cleaned_symbols)
        print(f"Today Top List Updated in MongoDB: {result}")
        #print("debug anchor =============================================== 5 ===get_data")
        
        

        return top_list_df, cleaned_symbols

    def clean_symbols(self, symbols):
        # Remove non-alphabetic characters to clean up stock symbols
        return [re.sub(r'[^A-Z]', '', symbol) for symbol in symbols]