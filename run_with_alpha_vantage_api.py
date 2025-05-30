import logging
import os
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # Requires Python 3.9+
import time

# Assuming alpha_vantage_api_refactored.py contains the AlphaVantageAPI and service classes
# In a real project, you'd import them like:
# from alpha_vantage_api_module import AlphaVantageAPI, TopMovers, Charts, ...
# For this example, I'll assume they are defined in the same scope or imported if this were a separate file.
# If running this standalone, you'd need to copy those class definitions here or import them properly.

# Placeholder for AlphaVantageAPI and its service classes if not directly imported
# These would be the classes from your 'alpha_vantage_api_refactored' immersive
# class AlphaVantageAPI: ...
# class TopMovers: ... (and so on for Charts, Market, News, Fundamentals, SECFiling, EconomicIndicators, Analysis)
# For this snippet to be runnable, these classes must be defined or imported.
# I will proceed assuming they are available in the execution scope.

# Using the classes from the provided 'alpha_vantage_api_refactored' immersive
# Make sure the file containing these classes is in your PYTHONPATH or same directory
# For demonstration, let's assume it's named alpha_vantage_services.py
try:
    from alpha_vantage_api.alpha_vantage_api_refactored import (
        AlphaVantageAPI, TopMovers, Charts, Market, News, 
        Fundamentals, SECFiling, EconomicIndicators, Analysis
    )
except ImportError:
    # This is a fallback for environments where the direct import might not work.
    # In a structured project, ensure proper module paths.
    print("Warning: Could not import AlphaVantage service classes. Define them or ensure correct path.")
    # Define dummy classes if import fails, so the rest of the script doesn't break immediately for structure review
    class AlphaVantageAPI: 
        def __init__(self, api_keys): 
            self.api_keys = api_keys
    
    class TopMovers: 
        def __init__(self, api): 
            self.api = api
            self.data = None
        
        def fetch_top_movers_data(self):
            return {}
        
        def get_top_gainers(self):
            return []
    
    class Charts: 
        def __init__(self, api): 
            self.api = api
        
        def get_quote(self, symbol):
            return {}
        
        def get_intraday_time_series(self, symbol, interval='1min', outputsize='compact'):
            return {}
    
    class Market: 
        def __init__(self, api): 
            self.api = api
    
    class News: 
        def __init__(self, api): 
            self.api = api
        
        def get_news_sentiment(self, tickers=None, limit=5):
            return {}
    
    class Fundamentals: 
        def __init__(self, api): 
            self.api = api
        
        def get_company_overview(self, symbol):
            return {}
    
    class SECFiling: 
        def __init__(self, api): 
            self.api = api
        
        def get_sec_filings(self, symbol):
            return {}
    
    class Analysis: 
        def __init__(self, api): 
            self.api = api
        
        def get_sma(self, symbol, interval='daily', time_period='20'):
            return {}


from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv(override=True) # Load environment variables from .env file

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AlphaVantageMain")

# Timezone
NY_TZ = ZoneInfo("America/New_York")

class MongoHandler:
    def __init__(self, mongodb_connection_string=None, db_name=None):
        try:
            mongo_uri = mongodb_connection_string or os.getenv("MONGODB_CONNECTION_STRING")
            if not mongo_uri:
                raise ValueError("MongoDB connection string not found. Set MONGODB_CONNECTION_STRING environment variable.")
            
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) # Increased timeout
            # Ping the server to ensure connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB.")

            default_db_name = os.getenv("MONGO_DBNAME", "TradeZero_Bot") # Default DB if not specified
            self.db_name = db_name or default_db_name
            self.db = self.client[self.db_name]
            logger.info(f"Using MongoDB database: {self.db_name}")

        except ConnectionFailure as e:
            logger.error(f"MongoDB ConnectionFailure: {e}")
            self.client = None
            self.db = None
        except Exception as e:
            logger.error(f"Error initializing MongoHandler: {e}")
            self.client = None
            self.db = None

    def is_connected(self):
        if not self.client:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except ConnectionFailure:
            logger.warning("MongoDB connection lost.")
            return False

    def _get_collection(self, collection_name):
        if not self.is_connected():
            logger.error("Not connected to MongoDB. Cannot get collection.")
            return None
        if not collection_name:
            logger.error("Collection name cannot be empty.")
            return None
        return self.db[collection_name]

    def create_collection_if_not_exists(self, collection_name):
        if not self.is_connected() or not collection_name:
            return False
        if collection_name not in self.db.list_collection_names():
            try:
                self.db.create_collection(collection_name)
                logger.info(f"Collection '{collection_name}' created in database '{self.db_name}'.")
                return True
            except Exception as e:
                logger.error(f"Failed to create collection '{collection_name}': {e}")
                return False
        return True # Collection already exists

    def upsert_doc(self, collection_name, query_filter: dict, document_data: dict):
        collection = self._get_collection(collection_name)
        if not collection:
            return None
        
        # Ensure today_date is in the document if not already present in query_filter
        if "today_date" not in document_data and "today_date" not in query_filter:
             document_data["today_date"] = datetime.now(NY_TZ).strftime('%Y-%m-%d')
        elif "today_date" in query_filter and "today_date" not in document_data:
             document_data["today_date"] = query_filter["today_date"]


        # Add/update a timestamp for the upsert operation
        document_data["last_updated_db_utc"] = datetime.utcnow().isoformat()

        try:
            result = collection.update_one(
                filter=query_filter,
                update={"$set": document_data},
                upsert=True
            )
            log_msg = ""
            if result.upserted_id:
                log_msg = f"Inserted new document with ID {result.upserted_id} into '{collection_name}'."
            elif result.modified_count > 0:
                log_msg = f"Updated existing document in '{collection_name}' matching filter {query_filter}."
            else:
                log_msg = f"No change for document in '{collection_name}' matching filter {query_filter} (data might be identical)."
            logger.info(log_msg)
            return {
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "upserted_id": str(result.upserted_id) if result.upserted_id else None
            }
        except Exception as e:
            logger.error(f"Error during upsert to '{collection_name}': {e}")
            return None

    def find_docs(self, collection_name, query_filter: dict, projection: dict = None):
        collection = self._get_collection(collection_name)
        if not collection:
            return []
        try:
            return list(collection.find(query_filter, projection))
        except Exception as e:
            logger.error(f"Error finding documents in '{collection_name}': {e}")
            return []

# --- Helper Functions ---
def clean_symbol(symbol_string):
    """Removes non-alphabetic characters from a stock symbol."""
    return re.sub(r'[^A-Z]', '', symbol_string) if symbol_string else None

def convert_av_financial_str(value_str):
    """Converts Alpha Vantage financial strings (like "123.45M", "1.23B", "None", percentages) to float."""
    if value_str is None or value_str == "None" or value_str == "-":
        return None
    if isinstance(value_str, (int, float)):
        return float(value_str)
    
    text = str(value_str).strip()
    if not text: return None

    if text.endswith('%'):
        try:
            return float(text[:-1]) / 100.0
        except ValueError:
            return None
    
    multiplier = 1
    if text.endswith('M'):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith('B'):
        multiplier = 1_000_000_000
        text = text[:-1]
    elif text.endswith('T'): # Trillion, less common but possible
        multiplier = 1_000_000_000_000
        text = text[:-1]
    
    try:
        return float(text) * multiplier
    except ValueError:
        logger.warning(f"Could not convert financial string to float: {value_str}")
        return None

# --- Main Application Logic ---
def process_symbols_alpha_vantage(alpha_vantage_api: AlphaVantageAPI, symbols_to_process: list, mongo_handler: MongoHandler, target_collection: str, today_date_str: str):
    """
    Fetches data for a list of symbols using Alpha Vantage and stores it in MongoDB.
    """
    if not symbols_to_process:
        logger.info("No symbols to process.")
        return

    # Instantiate Alpha Vantage service classes
    charts_service = Charts(alpha_vantage_api)
    news_service = News(alpha_vantage_api)
    fundamentals_service = Fundamentals(alpha_vantage_api)
    sec_filing_service = SECFiling(alpha_vantage_api)
    analysis_service = Analysis(alpha_vantage_api)

    for symbol_raw in symbols_to_process:
        symbol = clean_symbol(symbol_raw)
        if not symbol:
            logger.warning(f"Skipping invalid raw symbol: {symbol_raw}")
            continue
        
        logger.info(f"--- Processing symbol: {symbol} for date: {today_date_str} ---")
        
        # Check if data already exists and if we need to update (optional logic)
        # For now, we'll just upsert, overwriting/updating existing data for the day.

        symbol_data_record = {
            "symbol": symbol,
            "today_date": today_date_str, # Ensure this is the processing date
            "data_source": "AlphaVantage"
        }

        try:
            # 1. Company Overview (Fundamentals)
            overview = fundamentals_service.get_company_overview(symbol)
            if overview and not overview.get("Error Message") and not overview.get("Note"):
                symbol_data_record["overview"] = {
                    "name": overview.get("Name"),
                    "description": overview.get("Description"),
                    "sector": overview.get("Sector"),
                    "industry": overview.get("Industry"),
                    "market_cap": convert_av_financial_str(overview.get("MarketCapitalization")),
                    "pe_ratio": convert_av_financial_str(overview.get("PERatio")),
                    "beta": convert_av_financial_str(overview.get("Beta")),
                    "shares_outstanding": convert_av_financial_str(overview.get("SharesOutstanding")),
                    "float_shares": convert_av_financial_str(overview.get("FloatShares")), # Often premium
                    "dividend_yield": convert_av_financial_str(overview.get("DividendYield")),
                    "eps": convert_av_financial_str(overview.get("EPS")),
                    "52_week_high": convert_av_financial_str(overview.get("52WeekHigh")),
                    "52_week_low": convert_av_financial_str(overview.get("52WeekLow")),
                    # Add more fields as needed
                }
            else: logger.warning(f"Could not fetch overview for {symbol} or API limit/error: {overview}")


            # 2. Global Quote (Current Day's Price Info)
            quote = charts_service.get_quote(symbol)
            if quote and quote.get("Global Quote") and not quote.get("Note"):
                global_quote = quote["Global Quote"]
                symbol_data_record["quote"] = {
                    "open": convert_av_financial_str(global_quote.get("02. open")),
                    "high": convert_av_financial_str(global_quote.get("03. high")),
                    "low": convert_av_financial_str(global_quote.get("04. low")),
                    "price": convert_av_financial_str(global_quote.get("05. price")),
                    "volume": convert_av_financial_str(global_quote.get("06. volume")),
                    "latest_trading_day": global_quote.get("07. latest trading day"),
                    "previous_close": convert_av_financial_str(global_quote.get("08. previous close")),
                    "change": convert_av_financial_str(global_quote.get("09. change")),
                    "change_percent": convert_av_financial_str(global_quote.get("10. change percent")),
                }
            else: logger.warning(f"Could not fetch quote for {symbol} or API limit/error: {quote}")

            # 3. News Sentiment
            news_sentiment = news_service.get_news_sentiment(tickers=symbol, limit=5) # Get top 5 news items
            if news_sentiment and news_sentiment.get("feed") and not news_sentiment.get("Note"):
                symbol_data_record["news_sentiment"] = news_sentiment["feed"]
            else: logger.warning(f"Could not fetch news for {symbol} or API limit/error: {news_sentiment}")

            # 4. SEC Filings List
            # Note: SEC_FILINGS endpoint is premium. This might not work with free keys.
            # filings = sec_filing_service.get_sec_filings(symbol)
            # if filings and isinstance(filings, list) and not (isinstance(filings, dict) and (filings.get("Note") or filings.get("Error Message"))):
            #     symbol_data_record["sec_filings_list"] = filings
            # elif filings and (filings.get("Note") or filings.get("Error Message")):
            #     logger.warning(f"Could not fetch SEC filings for {symbol} (API Note/Error): {filings}")
            # else: 
            #     logger.warning(f"Could not fetch SEC filings for {symbol} or unexpected response: {filings}")
            # For now, commenting out premium SEC filings to avoid errors with free keys.
            symbol_data_record["sec_filings_list"] = "Premium endpoint - not fetched with free key"


            # 5. 1-min Intraday Data (Chart Data) - fetch a small amount for example
            intraday_1min = charts_service.get_intraday_time_series(symbol, interval='1min', outputsize='compact')
            if intraday_1min and intraday_1min.get("Time Series (1min)") and not intraday_1min.get("Note"):
                # Store a few recent data points or summary
                recent_1min_data = list(intraday_1min["Time Series (1min)"].items())[:5] # Get last 5 available minutes
                symbol_data_record["intraday_1min_sample"] = dict(recent_1min_data)
            else: logger.warning(f"Could not fetch 1-min intraday for {symbol} or API limit/error: {intraday_1min}")
            
            # 6. Example Technical Indicator (SMA)
            sma_20 = analysis_service.get_sma(symbol, interval='daily', time_period='20')
            if sma_20 and sma_20.get("Technical Analysis: SMA") and not sma_20.get("Note"):
                latest_sma_date = list(sma_20["Technical Analysis: SMA"].keys())[0] # Most recent date
                symbol_data_record["sma_20_daily"] = {
                    "date": latest_sma_date,
                    "value": convert_av_financial_str(sma_20["Technical Analysis: SMA"][latest_sma_date]["SMA"])
                }
            else: logger.warning(f"Could not fetch SMA for {symbol} or API limit/error: {sma_20}")

            # Upsert data to MongoDB
            mongo_handler.upsert_doc(
                collection_name=target_collection,
                query_filter={"symbol": symbol, "today_date": today_date_str},
                document_data=symbol_data_record
            )
            logger.info(f"Successfully processed and attempted to save data for {symbol}.")
            time.sleep(13) # Alpha Vantage free tier limit: 5 calls per minute. ~12 seconds per call.
                           # With multiple calls per symbol, this needs to be higher or managed better.
                           # For 5 calls per symbol: 5 * 12 = 60 seconds per symbol.
                           # If you have a premium key, you can reduce this.

        except RuntimeError as e: # From _try_request if all keys fail
            logger.error(f"RuntimeError processing {symbol}: {e}. Skipping symbol.")
            time.sleep(13) # Wait after a failed symbol too
        except Exception as e:
            logger.error(f"Unexpected error processing {symbol}: {e}", exc_info=True)
            time.sleep(13)


def main_alpha_vantage(debug=False):
    logger.info("Starting Alpha Vantage main process...")
    ny_time_now = datetime.now(NY_TZ)
    today_str = ny_time_now.strftime('%Y-%m-%d')
    
    # --- Configuration ---
    # Ensure API keys are loaded from .env or set directly
    alpha_vantage_api_keys = [key.strip() for key in os.getenv("ALPHA_VANTAGE_API_KEYS", "").split(',') if key.strip()]
    if not alpha_vantage_api_keys:
        logger.error("ALPHA_VANTAGE_API_KEYS environment variable not set or empty. Please provide API keys.")
        return

    mongo_db_collection_name = "TradeZero_Bot_V2" # Target collection

    # --- Initialize handlers ---
    try:
        av_api = AlphaVantageAPI(api_keys=alpha_vantage_api_keys)
        mongo = MongoHandler() # Uses MONGO_DBNAME from .env or default "TradeZero_Bot"
    except ValueError as ve: # For API key issues
        logger.error(f"Initialization error: {ve}")
        return
    except Exception as e:
        logger.error(f"Failed to initialize API or MongoDB handlers: {e}")
        return

    if not mongo.is_connected():
        logger.error("MongoDB is not connected. Exiting.")
        return
    
    mongo.create_collection_if_not_exists(mongo_db_collection_name)

    # --- Check if already run for today (optional) ---
    # Example: check a control document or if any symbol for today exists
    # For simplicity, this example will run and upsert data regardless.

    # --- Fetch Top Gainers ---
    top_movers_service = TopMovers(av_api)
    try:
        logger.info("Fetching top movers data from Alpha Vantage...")
        movers_raw_data = top_movers_service.fetch_top_movers_data() # Fetches and stores in service.data
        if not movers_raw_data or movers_raw_data.get("Note") or movers_raw_data.get("Error Message"):
            logger.error(f"Failed to fetch top movers or API error/note: {movers_raw_data}")
            return
        
        top_gainers_list = top_movers_service.get_top_gainers() # Extracts from self.data
        if not top_gainers_list:
            logger.info("No top gainers found in the data.")
            return
        
        logger.info(f"Successfully fetched {len(top_gainers_list)} top gainers.")
        if debug and top_gainers_list:
            logger.info(f"Sample top gainer: {top_gainers_list[0]}")

    except RuntimeError as e:
        logger.error(f"Could not fetch top movers from Alpha Vantage: {e}")
        return
    except Exception as e:
        logger.error(f"Unexpected error fetching top movers: {e}", exc_info=True)
        return

    # --- Filter Top Gainers ---
    # Original filter: Min_Close > 1 and < 50, Change_% > 50, len(Ticker) <= 4, Min_Volume > 100000
    # AlphaVantage `top_gainers` fields: 'ticker', 'price', 'change_amount', 'change_percentage', 'volume'
    filtered_symbols_for_processing = []
    for gainer in top_gainers_list:
        try:
            ticker = gainer.get('ticker')
            price_str = gainer.get('price')
            change_percent_str = gainer.get('change_percentage') # e.g., "10.5263%"
            volume_str = gainer.get('volume')

            if not all([ticker, price_str, change_percent_str, volume_str]):
                logger.warning(f"Skipping gainer due to missing data: {gainer}")
                continue

            price = float(price_str)
            change_percent = float(change_percent_str.rstrip('%'))
            volume = int(volume_str)

            # Apply filters
            if (1 < price < 50 and
                change_percent > 50 and # Assuming > 50%
                len(ticker) <= 4 and    # Standard ticker length
                volume > 100000):
                cleaned = clean_symbol(ticker)
                if cleaned:
                    filtered_symbols_for_processing.append(cleaned)
            
        except ValueError as ve:
            logger.warning(f"Could not parse data for gainer {gainer.get('ticker')}: {ve}")
        except Exception as e:
            logger.error(f"Unexpected error filtering gainer {gainer.get('ticker')}: {e}", exc_info=True)
            
    logger.info(f"Filtered {len(filtered_symbols_for_processing)} symbols for detailed processing: {filtered_symbols_for_processing}")

    if debug and filtered_symbols_for_processing:
        logger.info(f"Cleaned and filtered symbols: {filtered_symbols_for_processing[:5]}") # Log first 5

    # --- Process Filtered Symbols ---
    if filtered_symbols_for_processing:
        # Limit number of symbols to process if in debug or to avoid API limits quickly
        symbols_to_run = filtered_symbols_for_processing[:5] if debug else filtered_symbols_for_processing[:10] # Process only a few
        logger.info(f"Will run detailed processing for: {symbols_to_run}")
        
        process_symbols_alpha_vantage(
            alpha_vantage_api=av_api,
            symbols_to_process=symbols_to_run,
            mongo_handler=mongo,
            target_collection=mongo_db_collection_name,
            today_date_str=today_str
        )
    else:
        logger.info("No symbols met the filtering criteria for detailed processing.")

    logger.info(f"Alpha Vantage main process finished at {datetime.now(NY_TZ)}.")


# --- Scheduler (adapted from your original code) ---
class TradingScheduler: # Basic scheduler logic
    def __init__(self):
        self.market_open_hour_ny = 9
        self.market_open_minute_ny = 30
        self.market_close_hour_ny = 16
        self.processing_end_hour_ny = 17 # Stop new runs after 5 PM NY time
        self.run_interval_minutes = 15 # How often to check if we should run the main logic

    def is_market_hours_for_processing(self, current_ny_time):
        """Check if current time is within typical market activity for fetching fresh data."""
        # Example: Allow processing from just before market open to an hour after close
        # This is a simplified check. Real market hours can vary.
        start_time = current_ny_time.replace(hour=self.market_open_hour_ny -1, minute=0, second=0, microsecond=0)
        end_time = current_ny_time.replace(hour=self.processing_end_hour_ny, minute=0, second=0, microsecond=0)
        return start_time <= current_ny_time < end_time

    def should_run_now(self, debug=False):
        """Determines if the main logic should run based on time and interval."""
        # This is a placeholder for more sophisticated scheduling.
        # The original `TradingScheduler` might have more complex logic.
        # For this example, it will always allow a run if called by the external scheduler,
        # but you could add checks for specific times of day or intervals here.
        current_ny_time = datetime.now(NY_TZ)
        if debug:
            logger.info(f"Debug mode: Allowing run at {current_ny_time.strftime('%H:%M:%S %Z')}")
            return True
        
        # Only run during extended market/processing hours
        if not self.is_market_hours_for_processing(current_ny_time):
            logger.info(f"Skipping run: Outside processing hours ({current_ny_time.strftime('%H:%M:%S %Z')}).")
            return False
        
        # This method could also check if the last run was too recent, etc.
        # For now, if called by schedule, it runs if within processing hours.
        logger.info(f"Allowing run within processing hours at {current_ny_time.strftime('%H:%M:%S %Z')}.")
        return True


def scheduled_main_task():
    """The task to be called by the scheduler."""
    logger.info(f"Scheduler triggered task at {datetime.now(NY_TZ)}")
    
    # Initialize your scheduler logic if needed to decide to run main_alpha_vantage
    # For this example, TradingScheduler is basic.
    # scheduler_check = TradingScheduler() # You might have more stateful scheduler
    # if scheduler_check.should_run_now(debug=False): # Set debug=True for testing schedule
    
    # Simplified: directly call main, assuming external scheduler handles intervals
    try:
        main_alpha_vantage(debug=False) # Set debug=True to process fewer symbols and get more logs
        logger.info(f"✅ Scheduled execution completed at {datetime.now(NY_TZ)}")
    except Exception as e:
        logger.error(f"❌ Error during scheduled execution: {e}", exc_info=True)
    # else:
    # logger.info(f"⏳ Main logic run skipped by TradingScheduler at {datetime.now(NY_TZ)}")


if __name__ == "__main__":
    logger.info("Application started.")
    
    # Run once immediately
    # main_alpha_vantage(debug=True) 

    # --- Schedule subsequent runs ---
    # Using a simple time.sleep loop for scheduling as `schedule` library is not imported here.
    # If you have `schedule` library:
    # import schedule
    # schedule.every(15).minutes.do(scheduled_main_task)
    # logger.info("Scheduler started. Main task will run every 15 minutes. Press Ctrl+C to exit.")
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)

    # Simplified loop for demonstration if `schedule` is not available/used:
    run_interval_seconds = 15 * 60 # 15 minutes
    logger.info(f"Starting simple scheduler. Main task will attempt to run every {run_interval_seconds // 60} minutes.")
    logger.info("Run `main_alpha_vantage(debug=True)` manually if you want an immediate test run without waiting for schedule.")
    
    # Perform an initial run for testing if needed:
    # logger.info("Performing initial run...")
    # scheduled_main_task() # Call the task directly for an initial run
    # logger.info(f"Initial run complete. Next run in {run_interval_seconds // 60} minutes.")

    while True:
        logger.info(f"Scheduler check at {datetime.now(NY_TZ)}. Next check in {run_interval_seconds // 60} minutes.")
        # Here, you'd typically check if it's time to run based on your TradingScheduler logic
        # For simplicity, this example just calls the task.
        # A more robust scheduler would be external or use the `schedule` library correctly.
        
        # This is a basic way to simulate a scheduled task without the `schedule` library
        # In a production system, use a proper scheduler like `schedule`, APScheduler, or cron.
        
        # For this example, let's assume TradingScheduler's logic is inside scheduled_main_task
        # or that scheduled_main_task itself decides if it's time.
        # The current TradingScheduler.should_run_now() is more of a gate.
        
        # Let's use a simple check based on TradingScheduler
        trading_scheduler = TradingScheduler()
        if trading_scheduler.should_run_now(debug=False): # Set debug=True to force run for testing
            scheduled_main_task()
        else:
            logger.info(f"Skipped main task based on TradingScheduler decision at {datetime.now(NY_TZ)}.")

        time.sleep(run_interval_seconds)

