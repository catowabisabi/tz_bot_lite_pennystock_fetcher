import re
import sqlite3
import schedule
import time
from datetime import datetime, time as dt_time
import pytz

from program_starter.class_zeropro_starter import logger 
from program_starter.class_zeropro_starter import ZeroProAutomation
from get_gainer.zero_pro_inspector.zp_inspector import DynamicUIFinder 
from data_handler._data_handler import DataHandler    

from database.class_db import SQLiteDB , WatchListProcessor
from database.class_db_2 import StockDataManager




def should_run_now():
    """Determine if the current time falls within any of the active trading periods (excluding weekends)"""
    est = pytz.timezone('US/Eastern')
    now_dt = datetime.now(est)
    now = now_dt.time()

    # Skip weekends
    if now_dt.weekday() >= 8:  # 5 = Saturday, 6 = Sunday
        return False

    # Define the time periods and their corresponding intervals
    trading_periods = [
        {'start': dt_time(4, 0), 'end': dt_time(9, 8), 'interval_minutes': 15},
        {'start': dt_time(9, 9), 'end': dt_time(9, 45), 'interval_minutes': 1},
        {'start': dt_time(9, 46), 'end': dt_time(10, 32), 'interval_minutes': 5},
        {'start': dt_time(10, 33), 'end': dt_time(20, 0), 'interval_minutes': 15}
    ]

    now_minutes = now.hour * 60 + now.minute

    for period in trading_periods:
        start = period['start']
        end = period['end']
        interval = period['interval_minutes']

        if start <= now <= end:
            start_minutes = start.hour * 60 + start.minute
            return (now_minutes - start_minutes) % interval == 0

    return False

# 檢查表格是否存在, 
def table_exists(db, table_name):
    # 使用 SQL 查詢來檢查指定名稱的資料表是否存在於 SQLite 資料庫中
    # Use SQL query to check if a table with the given name exists in the SQLite database
    db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return db.cursor.fetchone() is not None


def run_main():
    if should_run_now():
        try:
            main()
            print(f"Execution completed at {datetime.now(pytz.timezone('US/Eastern'))}")
        except Exception as e:
            print(f"Error during execution: {e}")
    else:
        print(f"⏳ Skipped at {datetime.now(pytz.timezone('US/Eastern'))} (Outside trading time or not the interval)")


def clean_symbols(symbols):
    # 移除每個 symbol 中非大寫英文字母的字元
    # Remove all non-uppercase letters from each symbol    
    return [re.sub(r'[^A-Z]', '', symbol) for symbol in symbols]

# 使用範例
def setup_database(db, table_name):
    """
    建立資料表（如果不存在）並新增缺少的欄位。
    Create table if it does not exist and add missing columns.
    """
    if not table_exists(db, table_name):
        logger.info(f"Table '{table_name}' not found. Creating table...")
        db.create_table(table_name,
        """
        Symbol TEXT PRIMARY KEY,
        Last REAL,
        Percent_Change REAL,
        Latest_Percent_Change REAL,
        Volume REAL,
        Mkt_Cap REAL,
        Free_Float_Mkt_Cap REAL,
        Float REAL,
        est_time TEXT,
        created_at TEXT,
        updated_at TEXT,
        Last_Split_Date TEXT,
        Exchange TEXT
        """
        )
    else:
        logger.info(f"Table '{table_name}' exists.")

    try:
        logger.info("Adding 'Latest_Percent_Change' column...")
        db.cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN Latest_Percent_Change REAL DEFAULT 0.0")
        db.conn.commit()
        print("✅ Column 'Latest_Percent_Change' added.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ Column 'Latest_Percent_Change' already exists.")
        else:
            raise


def initialize_zeropro():
    """
    啟動 ZeroPro，並獲取主視窗代碼（HWND）
    Launch ZeroPro and get the main window handle.
    """
    zp = ZeroProAutomation()
    hwnd = zp.find_main_window()

    if not hwnd:
        logger.error("\nMain window not found, attempting to start ZeroPro...")
        zp.force_run()
        hwnd = zp.find_main_window()
    
    logger.info(f"\n✅ Found main window, HWND: {hwnd}")
    return hwnd




def get_top_list_data(hwnd):
    """
    從 UI 擷取漲幅榜資料並轉換欄位名稱
    Fetch gainer list from UI and rename columns
    """
    logger.info("\n\nFinding gainers...")   
    finder = DynamicUIFinder()
    top_list_symbols, top_list_df = finder.get_list_of_gainers_and_save_md_with_hwnd(hwnd)
    top_list_df = top_list_df.rename(columns={'% Change': 'Percent_Change'})
    
    logger.info(f"\nTop List: {top_list_symbols}")  
    logger.info("\nCleaning symbols...")
    cleaned_symbols = clean_symbols(top_list_symbols)

    
    #print(f"\n\nmost_active_symbols: {most_active_symbols}")
    #most_active_symbols, most_active_df =finder.get_list_of_gainers_and_save_md_with_hwnd(hwnd, data_name="Most Active")


    return top_list_df, cleaned_symbols


def process_watch_list(top_list_df, db, table_name):
    """
    將漲幅榜資料寫入資料庫
    Insert watch list data into database
    """
    processor = WatchListProcessor()
    processor.insert_to_db(top_list_df, db, table_name)


def run_data_analysis(symbols):
    """
    執行個股基本面與技術分析，並儲存至本地資料庫
    Run fundamental and technical analysis, then store to local DB
    """
    logger.info("\n\nRunning data handler...")
    data_handler = DataHandler()
    fundamentals, analysis_results = data_handler.run(symbols)

    db_manager = StockDataManager('output/stock_data.db')
    print("\n寫入數據...")
    db_manager.process_data(fundamentals, analysis_results)
    db_manager.close()


def main():

    """
    主流程控制：資料表建立、啟動 ZeroPro、擷取與分析資料。
    Main program logic: setup DB, launch ZeroPro, retrieve and analyze stock data.
    """
    logger.info("\n\nProgram starting...")

    db = SQLiteDB("database/top_gainer.sqlite")
    table_name = 'top_list_watch_list'

    # 建立資料表與欄位 # create table in sqlite
    setup_database(db, table_name) 
    
    # 啟動 UI 並取得主視窗
    hwnd = initialize_zeropro()
    
    # 擷取漲幅榜資料
    top_list_df, cleaned_symbols = get_top_list_data(hwnd)

    # 寫入 watchlist 資料表 Write watch list data to database
    process_watch_list(top_list_df, db, table_name)

    # 執行分析並寫入 local DB
    run_data_analysis(cleaned_symbols)





if __name__ == "__main__":
    print("Scheduler started. Press Ctrl+C to exit.")

    # Schedule the job to run every minute
    schedule.every(1).minutes.do(run_main)

    while True:
        schedule.run_pending()
        time.sleep(1)