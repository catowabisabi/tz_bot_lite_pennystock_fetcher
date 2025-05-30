import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo # Requires Python 3.9+
import time
import pandas as pd # For formatting output in examples
import requests

# Polygon.io client
from polygon import RESTClient
from polygon.rest.models import TickerSnapshot # For type hinting
from polygon.exceptions import BadResponse, AuthError

# For .env file
from dotenv import load_dotenv
load_dotenv(override=True) # Loads environment variables from .env file

#region logger
# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("PolygonAPI")

NY_TZ = ZoneInfo("America/New_York")
#endregion

#region Polygon API Main Class
class PolygonAPI:
    """
    Main class to interact with the Polygon.io API.
    It initializes the RESTClient and provides access to nested classes
    for different API functionalities.
    """
    #region PolygonAPI Core
    def __init__(self, api_key=None, verbose_errors=False):
        """
        Initializes the PolygonAPI client and all service classes.
        :param api_key: Your Polygon.io API key. If None, tries to load from POLYGON_KEY env variable.
        :param verbose_errors: If True, logs more detailed error messages from PolygonException.
        """
        self.api_key = api_key or os.getenv("POLYGON_KEY")
        if not self.api_key:
            logger.error("Polygon API key not found. Set POLYGON_KEY environment variable or pass it to constructor.")
            raise ValueError("Polygon API key not found.")
        
        # region Initialize the RESTClient
        # You can pass `timeout=...` or other configurations here if needed.
        self.client = RESTClient(self.api_key)
        self.verbose_errors = verbose_errors
        logger.info(f"PolygonAPI initialized with key ending '...{self.api_key[-4:] if len(self.api_key) > 4 else self.api_key}'")

        # region Instantiate nested service classes
        self.reference = self.Reference(self)
        self.market = self.Market(self)
        self.news = self.News(self)
        self.movers = self.Movers(self)
        self.indicators = self.Indicators(self)
        
        # Placeholder classes similar to your Alpha Vantage script
        self.ai_suggestion = self.AISuggestion(self)
        self.db_handler = self.MongoDBHandler(self)

    #region Generate Filename
    def _generate_filename(self, endpoint_name, params_for_filename=None):
        """
        Generates a descriptive filename for saving responses.
        """
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        safe_endpoint_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in endpoint_name)
        
        param_str_parts = []
        if params_for_filename:
            for key, value in sorted(params_for_filename.items()):
                safe_value = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in str(value))
                param_str_parts.append(f"{key}_{safe_value}")
        param_str = "_".join(param_str_parts) if param_str_parts else ""

        if param_str:
            return f'{safe_endpoint_name}_{param_str}_{timestamp}'
        return f'{safe_endpoint_name}_{timestamp}'
    
    #region Save Json

    def _save_response_to_file(self, filename_base, data_content, extension=".json"):
        """
        Saves response data to a file.
        :param filename_base: Base name for the file (without timestamp or extension).
        :param data_content: The data to save (should be JSON serializable if extension is .json).
        :param extension: File extension (e.g., ".json", ".csv").
        """
        if not os.path.exists('_polygon_response'):
            try:
                os.makedirs('_polygon_response')
                logger.info("Created directory '_polygon_response'")
            except OSError as e:
                logger.error(f"Failed to create directory '_polygon_response': {e}")
                return

        filename = f'_polygon_response/{filename_base}{extension}'
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                if extension == '.json':
                    # Convert Polygon models to dicts if necessary
                    if hasattr(data_content, '__dict__'): # Single model object
                        json.dump(vars(data_content), f, indent=2, default=str) # default=str for datetime etc.
                    elif isinstance(data_content, list) and data_content and hasattr(data_content[0], '__dict__'):
                        json.dump([vars(item) if hasattr(item, '__dict__') else item for item in data_content], f, indent=2, default=str)
                    elif isinstance(data_content, dict) or isinstance(data_content, list): # Already a dict or list of dicts
                         json.dump(data_content, f, indent=2, default=str)
                    else: # Attempt to serialize directly or log warning
                        try:
                            json.dump(data_content, f, indent=2, default=str)
                        except TypeError:
                            logger.warning(f"Data for '{filename_base}' is not directly JSON serializable. Saving as string.")
                            f.write(str(data_content))
                else:
                    f.write(str(data_content)) # For CSV or other text formats
            logger.info(f"Successfully saved response to {filename}")
        except IOError as e:
            logger.error(f"Failed to write response to {filename}: {e}")
        except TypeError as e:
            logger.error(f"Data for '{filename_base}' (JSON) is not serializable: {e}. Data type: {type(data_content)}")

    #region Request Handler
    def _request_handler(self, client_method_name, endpoint_name_for_file, params_for_filename=None, **kwargs):
        method_to_call = getattr(self.client, client_method_name, None)
        if not method_to_call:
            logger.error(f"Client method '{client_method_name}' not found in Polygon RESTClient.")
            return None

        param_log_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.info(f"Attempting API call for '{endpoint_name_for_file}' with params: {param_log_str[:200]}{'...' if len(param_log_str)>200 else ''}")
        
        try:
            response_data = method_to_call(**kwargs)
            
            if hasattr(response_data, '__iter__') and not isinstance(response_data, (list, dict, str)):
                logger.info(f"Response for '{endpoint_name_for_file}' is an iterator, converting to list.")
                response_data = list(response_data)

            logger.info(f"Successfully fetched data for '{endpoint_name_for_file}'. Items: {len(response_data) if isinstance(response_data, list) else 1}")
            
            filename_base = self._generate_filename(endpoint_name_for_file, params_for_filename)
            self._save_response_to_file(filename_base, response_data)
            return response_data
        
        except AuthError as ae:
            # AuthError typically means an issue with the API key (empty, invalid).
            # The polygon-api-python library might raise this before even making a request,
            # or after a 401/403 response if it interprets it that way.
            error_message = f"Polygon API Authentication Error for '{endpoint_name_for_file}': {str(ae)}"
            # AuthError itself might not have a 'response' attribute in the same way as BadResponse.
            # We'll log the string representation of the error.
            logger.error(error_message)
            return None
        
        except BadResponse as bre:
            # BadResponse implies a non-200 HTTP response was received from the API.
            # It should contain details about the failed request.
            # The string representation of BadResponse often includes status and message.
            error_message = f"Polygon API Bad Response for '{endpoint_name_for_file}': {str(bre)}"
            
            # Try to get more details if verbose_errors is True and if BadResponse carries a response object
            # (This part is speculative, depends on how BadResponse is implemented in your lib version)
            if self.verbose_errors:
                if hasattr(bre, 'response') and bre.response is not None: # Check if it has a 'response' attribute
                    try:
                        # Assuming 'response' might be a requests.Response object or similar
                        status_code = bre.response.status_code if hasattr(bre.response, 'status_code') else "N/A"
                        error_details_text = bre.response.text if hasattr(bre.response, 'text') else ""
                        error_message += f" | Status: {status_code} | Response Text: {error_details_text[:200]}"
                    except Exception as e_detail:
                        error_message += f" | Could not extract detailed response info: {e_detail}"
                elif hasattr(bre, 'status_code') and hasattr(bre, 'message'): # If it has status_code and message directly
                     error_message += f" | Status: {bre.status_code} | Message: {bre.message}"


            logger.error(error_message)
            return None
            
        except requests.exceptions.Timeout as te:
            logger.error(f"Network timeout during API call for '{endpoint_name_for_file}': {te}")
            return None
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"Network connection error during API call for '{endpoint_name_for_file}': {ce}")
            return None
        except requests.exceptions.RequestException as e: # Catches other requests-related issues (e.g. DNS failure)
            logger.error(f"Network request error for '{endpoint_name_for_file}': {e}")
            return None
            
        except Exception as e: # Catch-all for other unexpected errors
            logger.error(f"An unexpected error occurred during API call for '{endpoint_name_for_file}': {e}", exc_info=True)
            return None
    #endregion

    #region Reference Data Nested Class
    class Reference:
        """
        Handles Polygon.io Reference Data endpoints.
        (Tickers, Exchanges, Market Status, Splits, Dividends, Financials, etc.)
        """
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api

        def get_tickers(self, ticker=None, type=None, market=None, exchange=None, cusip=None, cik=None, date=None, search=None, active=True, sort='ticker', order='asc', limit=1000):
            """
            List all tickers or search for tickers.
            Full documentation: https://polygon.io/docs/stocks/get_v3_reference_tickers
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api'] and v is not None}
            filename_params = {'search': search, 'ticker': ticker, 'market': market, 'limit': limit} # Key params for filename
            return self.parent_api._request_handler(
                client_method_name='list_tickers',
                endpoint_name_for_file='reference_tickers',
                params_for_filename=filename_params,
                **params
            )

        def get_ticker_details(self, ticker_symbol):
            """
            Get details for a single ticker.
            Full documentation: https://polygon.io/docs/stocks/get_v3_reference_tickers__ticker
            """
            return self.parent_api._request_handler(
                client_method_name='get_ticker_details',
                endpoint_name_for_file=f'reference_ticker_details_{ticker_symbol}',
                params_for_filename={'ticker': ticker_symbol},
                ticker=ticker_symbol
            )

        def get_stock_financials_vx(self, ticker, limit=5, period_of_report_date_lt=None, period_of_report_date_lte=None, period_of_report_date_gt=None, period_of_report_date_gte=None, timeframe=None, include_sources=False):
            """
            Get historical financial data for a stock ticker.
            Full documentation: https://polygon.io/docs/stocks/get_vx_reference_financials
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            return self.parent_api._request_handler(
                client_method_name='get_stock_financials_vx',
                endpoint_name_for_file=f'reference_stock_financials_{ticker}',
                params_for_filename={'ticker': ticker, 'limit': limit, 'timeframe': timeframe},
                ticker_symbol=ticker, # Note: client method uses ticker_symbol
                **params
            )
        
        def get_market_status(self):
            """
            Get the current status of the market.
            Full documentation: https://polygon.io/docs/stocks/get_v1_marketstatus_now
            """
            return self.parent_api._request_handler(
                client_method_name='get_market_status',
                endpoint_name_for_file='reference_market_status_now'
            )

        def get_market_holidays(self):
            """
            Get upcoming market holidays.
            Full documentation: https://polygon.io/docs/stocks/get_v1_marketstatus_upcoming
            """
            return self.parent_api._request_handler(
                client_method_name='get_market_holidays',
                endpoint_name_for_file='reference_market_holidays'
            )
        
        def get_splits(self, ticker=None, execution_date=None, reverse_split=None, limit=1000, sort='execution_date', order='desc'):
            """
            Get stock splits.
            Full documentation: https://polygon.io/docs/stocks/get_v3_reference_splits
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api'] and v is not None}
            filename_params = {'ticker': ticker, 'execution_date': execution_date, 'limit': limit}
            return self.parent_api._request_handler(
                client_method_name='list_splits',
                endpoint_name_for_file='reference_splits',
                params_for_filename=filename_params,
                **params
            )

        def get_dividends(self, ticker=None, ex_dividend_date=None, record_date=None, declaration_date=None, pay_date=None, frequency=None, cash_amount=None, dividend_type=None, limit=1000, sort='ex_dividend_date', order='desc'):
            """
            Get stock dividends.
            Full documentation: https://polygon.io/docs/stocks/get_v3_reference_dividends
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api'] and v is not None}
            filename_params = {'ticker': ticker, 'ex_dividend_date': ex_dividend_date, 'limit': limit}
            return self.parent_api._request_handler(
                client_method_name='list_dividends',
                endpoint_name_for_file='reference_dividends',
                params_for_filename=filename_params,
                **params
            )
    #endregion

    #region Market Data Nested Class (Stocks, Options, Forex, Crypto)
    class Market:
        """
        Handles Polygon.io Market Data endpoints.
        This class can be further sub-divided if needed (e.g., self.stocks, self.options).
        """
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api
            # You could instantiate sub-classes here:
            # self.stocks = self.Stocks(parent_api)
            # self.options = self.Options(parent_api)
            # For now, methods will specify asset class or use generic client methods.

        # --- Stocks ---
        def get_stock_aggregates(self, ticker, multiplier, timespan, from_date, to_date, adjusted=True, sort='asc', limit=5000):
            """
            Get aggregate bars for a stock ticker over a given date range.
            Full documentation: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to
            :param ticker: The ticker symbol.
            :param multiplier: Size of the timespan multiplier (e.g., 1).
            :param timespan: Timespan (e.g., 'day', 'minute', 'hour').
            :param from_date: Start date (YYYY-MM-DD or timestamp).
            :param to_date: End date (YYYY-MM-DD or timestamp).
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'from': from_date, 'to': to_date}
            return self.parent_api._request_handler(
                client_method_name='get_aggs', # Generic aggregates method
                endpoint_name_for_file=f'market_stock_aggregates_{ticker}',
                params_for_filename=filename_params,
                ticker=ticker,
                **params
            )

        def get_stock_daily_open_close(self, ticker, date):
            """
            Get the daily open, high, low, and close (OHLC) for a stock.
            Full documentation: https://polygon.io/docs/stocks/get_v1_open-close__stocksticker___date
            """
            return self.parent_api._request_handler(
                client_method_name='get_daily_open_close_agg',
                endpoint_name_for_file=f'market_stock_daily_ohlc_{ticker}_{date}',
                params_for_filename={'ticker': ticker, 'date': date},
                ticker=ticker,
                date=date
            )

        def get_stock_previous_close(self, ticker, adjusted=True):
            """
            Get the previous day's open, high, low, and close (OHLC) for a stock.
            Full documentation: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__prev
            """
            return self.parent_api._request_handler(
                client_method_name='get_previous_close_agg',
                endpoint_name_for_file=f'market_stock_previous_close_{ticker}',
                params_for_filename={'ticker': ticker},
                ticker=ticker,
                adjusted=adjusted
            )
        
        def get_stock_snapshot_ticker(self, ticker):
            """
            Get the current minute, day, and previous day’s aggregate, as well as the last trade and quote for a single stock ticker.
            Full documentation: https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_tickers__stocksticker
            """
            return self.parent_api._request_handler(
                client_method_name='get_snapshot_ticker', # This is for stocks
                endpoint_name_for_file=f'market_stock_snapshot_{ticker}',
                params_for_filename={'ticker': ticker},
                ticker=ticker
            )

        # --- Forex ---
        def get_forex_aggregates(self, ticker, multiplier, timespan, from_date, to_date, adjusted=True, sort='asc', limit=5000):
            """
            Get aggregate bars for a forex currency pair.
            Full documentation: https://polygon.io/docs/forex/get_v2_aggs_ticker__forexticker__range__multiplier___timespan___from___to
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'from': from_date, 'to': to_date}
            return self.parent_api._request_handler(
                client_method_name='get_aggs',
                endpoint_name_for_file=f'market_forex_aggregates_{ticker}',
                params_for_filename=filename_params,
                ticker=ticker, # e.g., "C:EURUSD"
                **params
            )
        
        # --- Crypto ---
        def get_crypto_aggregates(self, ticker, multiplier, timespan, from_date, to_date, adjusted=True, sort='asc', limit=5000):
            """
            Get aggregate bars for a crypto pair.
            Full documentation: https://polygon.io/docs/crypto/get_v2_aggs_ticker__cryptoticker__range__multiplier___timespan___from___to
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'from': from_date, 'to': to_date}
            return self.parent_api._request_handler(
                client_method_name='get_aggs',
                endpoint_name_for_file=f'market_crypto_aggregates_{ticker}',
                params_for_filename=filename_params,
                ticker=ticker, # e.g., "X:BTCUSD"
                **params
            )
    #endregion

    #region News Nested Class
    class News:
        """
        Handles Polygon.io News endpoints.
        """
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api

        def get_ticker_news(self, ticker=None, published_utc=None, limit=1000, sort='published_utc', order='desc'):
            """
            Get the most recent news articles relating to a stock ticker symbol.
            Full documentation: https://polygon.io/docs/stocks/get_v2_reference_news
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api'] and v is not None}
            filename_params = {'ticker': ticker, 'limit': limit, 'published_utc': published_utc}
            return self.parent_api._request_handler(
                client_method_name='list_ticker_news',
                endpoint_name_for_file='news_ticker_news',
                params_for_filename=filename_params,
                **params
            )
    #endregion
    
    #region Market Movers Nested Class
    class Movers:
        """
        Handles Polygon.io Market Movers endpoints (Gainers/Losers).
        """
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api

        def get_gainers(self, locale='us', market='stocks'):
            """
            Get the biggest gainers in a given market.
            Full documentation: https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_gainers
            """
            return self.parent_api._request_handler(
                client_method_name='get_snapshot_direction', # Generic method for gainers/losers
                endpoint_name_for_file=f'movers_gainers_{locale}_{market}',
                params_for_filename={'locale': locale, 'market': market, 'direction': 'gainers'},
                locale=locale,
                market_type=market, # client method uses market_type
                direction='gainers'
            )

        def get_losers(self, locale='us', market='stocks'):
            """
            Get the biggest losers in a given market.
            Full documentation: https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_losers
            """
            return self.parent_api._request_handler(
                client_method_name='get_snapshot_direction',
                endpoint_name_for_file=f'movers_losers_{locale}_{market}',
                params_for_filename={'locale': locale, 'market': market, 'direction': 'losers'},
                locale=locale,
                market_type=market,
                direction='losers'
            )
    #endregion

    #region Technical Indicators Nested Class
    class Indicators:
        """
        Handles Polygon.io Technical Indicator endpoints.
        """
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api

        def get_sma(self, ticker, date=None, timespan='day', adjusted=True, window=50, series_type='close', expand_underlying=False, order='desc', limit=5000):
            """
            Get Simple Moving Average (SMA) data for a ticker.
            Full documentation: https://polygon.io/docs/stocks/get_v1_indicators_sma__stockticker
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'window': window}
            return self.parent_api._request_handler(
                client_method_name='get_sma',
                endpoint_name_for_file=f'indicator_sma_{ticker}',
                params_for_filename=filename_params,
                stock_ticker=ticker, # client method uses stock_ticker
                **params
            )

        def get_ema(self, ticker, date=None, timespan='day', adjusted=True, window=50, series_type='close', expand_underlying=False, order='desc', limit=5000):
            """
            Get Exponential Moving Average (EMA) data for a ticker.
            Full documentation: https://polygon.io/docs/stocks/get_v1_indicators_ema__stockticker
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'window': window}
            return self.parent_api._request_handler(
                client_method_name='get_ema',
                endpoint_name_for_file=f'indicator_ema_{ticker}',
                params_for_filename=filename_params,
                stock_ticker=ticker,
                **params
            )

        def get_macd(self, ticker, date=None, timespan='day', adjusted=True, short_window=12, long_window=26, signal_window=9, series_type='close', expand_underlying=False, order='desc', limit=5000):
            """
            Get Moving Average Convergence/Divergence (MACD) data for a ticker.
            Full documentation: https://polygon.io/docs/stocks/get_v1_indicators_macd__stockticker
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'short_window': short_window, 'long_window': long_window}
            return self.parent_api._request_handler(
                client_method_name='get_macd',
                endpoint_name_for_file=f'indicator_macd_{ticker}',
                params_for_filename=filename_params,
                stock_ticker=ticker,
                **params
            )

        def get_rsi(self, ticker, date=None, timespan='day', adjusted=True, window=14, series_type='close', expand_underlying=False, order='desc', limit=5000):
            """
            Get Relative Strength Index (RSI) data for a ticker.
            Full documentation: https://polygon.io/docs/stocks/get_v1_indicators_rsi__stockticker
            """
            params = {k: v for k, v in locals().items() if k not in ['self', 'parent_api', 'ticker'] and v is not None}
            filename_params = {'ticker': ticker, 'timespan': timespan, 'window': window}
            return self.parent_api._request_handler(
                client_method_name='get_rsi',
                endpoint_name_for_file=f'indicator_rsi_{ticker}',
                params_for_filename=filename_params,
                stock_ticker=ticker,
                **params
            )
    #endregion

    #region Placeholder Classes
    class AISuggestion:
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api # In case it needs to access the client or logger

        def generate_suggestion(self, data):
            suggestion = "This is a placeholder for AI-generated suggestions based on the provided Polygon data."
            logger.info(f"AI Suggestion: {suggestion} (Data: {str(data)[:100]}...)")
            # Example: self.parent_api._save_response_to_file("ai_suggestion_input", data)
            return suggestion

    class MongoDBHandler:
        def __init__(self, parent_api: 'PolygonAPI'):
            self.parent_api = parent_api

        def save_data(self, collection_name, data):
            # Placeholder for saving data to MongoDB
            # Example: self.parent_api._save_response_to_file(f"mongodb_save_{collection_name}", data)
            logger.info(f"Placeholder: Data for '{collection_name}' would be saved to MongoDB here. (Data: {str(data)[:100]}...)")
            # Actual MongoDB saving logic would go here
    #endregion
#endregion


#region Usage Example
if __name__ == '__main__':
    # Ensure POLYGON_KEY is set in your .env file or pass it directly:
    # polygon_client = PolygonAPI(api_key="YOUR_POLYGON_KEY")
    try:
        polygon_client = PolygonAPI(verbose_errors=True) # Loads key from .env
    except ValueError as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)

    """ test_stock_ticker = 'AAPL'
    test_forex_ticker = 'C:EURUSD' # Note the 'C:' prefix for forex
    test_crypto_ticker = 'X:BTCUSD' # Note the 'X:' prefix for crypto

    today = date.today()
    past_date = today - timedelta(days=30)
    past_date_str = past_date.strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    logger.info("\n--- Testing Reference Data ---")
    tickers = polygon_client.reference.get_tickers(market='stocks', search='Apple', limit=2)
    if tickers and hasattr(tickers, 'results') and tickers.results:
        print(f"Found tickers for 'Apple' (first {len(tickers.results)}): {[t.ticker for t in tickers.results]}")
    
    aapl_details = polygon_client.reference.get_ticker_details(test_stock_ticker)
    if aapl_details and hasattr(aapl_details, 'results') and aapl_details.results:
        print(f"Details for {test_stock_ticker}: Name - {aapl_details.results.name}, Market Cap - {aapl_details.results.market_cap}")

    market_status = polygon_client.reference.get_market_status()
    if market_status and hasattr(market_status, 'market'):
        print(f"Current Market Status: {market_status.market}, Server Time: {datetime.fromtimestamp(market_status.server_time / 1000000000, tz=NY_TZ)}")

    # financials = polygon_client.reference.get_stock_financials_vx(test_stock_ticker, limit=1, timeframe="annual")
    # if financials and hasattr(financials, 'results') and financials.results:
    #     print(f"Latest annual financial report date for {test_stock_ticker}: {financials.results[0].end_date}")


    logger.info(f"\n--- Testing Market Data for {test_stock_ticker} ---")
    stock_aggs = polygon_client.market.get_stock_aggregates(
        ticker=test_stock_ticker, 
        multiplier=1, 
        timespan='day', 
        from_date=past_date_str, 
        to_date=today_str,
        limit=2
    )
    if stock_aggs and hasattr(stock_aggs, 'results') and stock_aggs.results:
        print(f"Daily aggregates for {test_stock_ticker} (first {len(stock_aggs.results)}):")
        for agg in stock_aggs.results:
            print(f"  Date: {datetime.fromtimestamp(agg.t / 1000).strftime('%Y-%m-%d')}, Close: {agg.c}")
    
    prev_close = polygon_client.market.get_stock_previous_close(test_stock_ticker)
    if prev_close and hasattr(prev_close, 'results') and prev_close.results:
         print(f"Previous close for {test_stock_ticker}: {prev_close.results[0].c} on {datetime.fromtimestamp(prev_close.results[0].t / 1000).strftime('%Y-%m-%d')}")


    logger.info(f"\n--- Testing Market Data for {test_forex_ticker} ---")
    forex_aggs = polygon_client.market.get_forex_aggregates(
        ticker=test_forex_ticker,
        multiplier=1,
        timespan='day',
        from_date=past_date_str,
        to_date=today_str,
        limit=2
    )
    if forex_aggs and hasattr(forex_aggs, 'results') and forex_aggs.results:
        print(f"Daily aggregates for {test_forex_ticker} (first {len(forex_aggs.results)}):")
        for agg in forex_aggs.results:
            print(f"  Date: {datetime.fromtimestamp(agg.t / 1000).strftime('%Y-%m-%d')}, Close: {agg.c}")


    logger.info("\n--- Testing News ---")
    aapl_news = polygon_client.news.get_ticker_news(ticker=test_stock_ticker, limit=1)
    if aapl_news and hasattr(aapl_news, 'results') and aapl_news.results:
        print(f"Latest news for {test_stock_ticker}: {aapl_news.results[0].title}")

    logger.info("\n--- Testing Market Movers ---")
    gainers = polygon_client.movers.get_gainers()
    if gainers and hasattr(gainers, 'tickers') and gainers.tickers: # Snapshot response structure
        print(f"Top gainers (first 2):")
        for g in gainers.tickers[:2]:
            print(f"  {g.ticker}: Change {g.todays_change_percent:.2f}%")
    
    logger.info(f"\n--- Testing Technical Indicators for {test_stock_ticker} ---")
    sma_data = polygon_client.indicators.get_sma(test_stock_ticker, window=20, limit=1)
    if sma_data and hasattr(sma_data, 'results') and hasattr(sma_data.results, 'values') and sma_data.results.values:
        latest_sma = sma_data.results.values[0]
        print(f"Latest SMA(20) for {test_stock_ticker}: {latest_sma.value} on {datetime.fromtimestamp(latest_sma.timestamp / 1000).strftime('%Y-%m-%d')}")

    logger.info("\n--- Testing Placeholder AI Suggestion ---")
    if aapl_details and hasattr(aapl_details, 'results'):
        suggestion = polygon_client.ai_suggestion.generate_suggestion(aapl_details.results)
        print(suggestion)

    logger.info("\n--- Testing Placeholder DB Handler ---")
    if gainers and hasattr(gainers, 'tickers'):
        polygon_client.db_handler.save_data("top_gainers_snapshot", gainers.tickers[:5]) # Save first 5 gainers

    logger.info("\n--- Example of fetching Forex snapshot (if needed) ---")
    # Note: The client library's get_snapshot_forex method might be specific
    # For a generic snapshot, you might need to use a more general method or check library updates
    # forex_snapshot = polygon_client.client.get_snapshot_forex_pair(from_symbol="EUR", to_symbol="USD")
    # if forex_snapshot and hasattr(forex_snapshot, 'ticker'):
    #     print(f"Snapshot for EUR/USD: Last Quote Ask - {forex_snapshot.ticker.last_quote.ask_price}")


    logger.info("\n--- All tests completed. Check 'polygon_response' directory for saved files. ---")

#endregion
 """