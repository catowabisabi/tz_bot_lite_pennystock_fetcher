import schedule
import time
import pytz
import datetime
from datetime import datetime

from program_starter.class_zeropro_starter import logger 
from utilities.trade_scheduler import TradingScheduler
from data_handler.anaylsis_runner import AnalysisRunner
from data_handler.top_list_handler import TopListHandler
from database.db_manager import DatabaseManager
from database.class_db import SQLiteDB , WatchListProcessor
from get_gainer.zero_pro_inspector.zp_controller import ZeroProController
from database._mongodb.mongo_handler import MongoHandler
from zoneinfo import ZoneInfo


ny_time = datetime.now(ZoneInfo("America/New_York"))
today_str = ny_time.strftime('%Y-%m-%d')

class MainController:
    """
    Orchestrates the execution flow: from data acquisition, cleaning, analysis, to storage.
    """

    def __init__(self):
        logger.info(f"Initializing MainController at {datetime.now(pytz.timezone('US/Eastern'))}")
        self.table_name = 'top_list_watch_list' # a list of top gainers of that day {date: "YYYY-MM-DD" symbols: ["AAPL", "MSFT"]}
        
        self.mongo_handler = MongoHandler()
        self.db_path='database/top_gainer.db'
        self.scheduler = TradingScheduler()
        self.db = SQLiteDB(self.db_path)
        
        self.db_manager = DatabaseManager(self.db, self.table_name)
        self.zeropro = ZeroProController()
        self.top_list_handler = TopListHandler()
        self.analysis_runner = AnalysisRunner(db_path=self.db_path)
        
        

    
    def create_mongo_collection(self, collection_name):
        self.mongo_handler.create_collection(collection_name)
        logger.info(f"Created collection: {collection_name}")
        
    
    def find_mongo_collection(self, collection_name):
        return self.mongo_handler.find_collection(collection_name)


    #region Main
    def main(self):
        logger.info("🚀 Program starting...")

        # Ensure database table is ready
        self.db_manager.setup_table()
        self.create_mongo_collection(self.table_name)

        
        print(f"Document is created: {self.mongo_handler.find_doc("today_top_list", {'today_date': today_str})}")
    
        # Initialize ZeroPro and capture window handle
        hwnd = self.zeropro.initialize()




        # Fetch gainers list and clean symbols
        top_list_df, cleaned_symbols = self.top_list_handler.get_data(hwnd) # cleaned_symbols is already in MongoDB


        print("\n\n一開始的upsert")
        self.mongo_handler.upsert_doc(self.table_name, {"today_date": today_str}, {"symbols":cleaned_symbols})




        # Insert to database
        processor = WatchListProcessor()
        processor.insert_to_db(top_list_df, self.db, self.table_name)


        # Run analysis on top symbols
        self.analysis_runner.run(cleaned_symbols)









    #region Run Main
    def run_main(self):
        """
        Main wrapper for scheduled execution. Checks if it should run, and then executes.
        """
        if self.scheduler.should_run_now(debug=True):
            try:
                self.main()
                print(f"✅ Execution completed at {datetime.now(pytz.timezone('US/Eastern'))}")
            except Exception as e:
                print(f"❌ Error during execution: {e}")
        else:
            print(f"⏳ Skipped at {datetime.now(pytz.timezone('US/Eastern'))} (Outside trading time or not the interval)")


# Entry point for script execution
if __name__ == "__main__":
    logger.info("\n\nScheduler started. Press Ctrl+C to exit.")
    controller = MainController()
    schedule.every(1).minutes.do(controller.run_main)

    while True:
        schedule.run_pending()
        time.sleep(1)
