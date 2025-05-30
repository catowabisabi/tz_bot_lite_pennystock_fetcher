import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import logging
import json
from datetime import datetime

# 設定 logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlphaVantageAPI:
    def __init__(self, api_keys):
        self.api_keys = [key for key in api_keys if key and key.strip()] # Ensure keys are not empty or just whitespace
        if not self.api_keys:
            raise ValueError("API key list is empty or contains only invalid keys.")
        self.base_url = 'https://www.alphavantage.co/query'

    def _try_request(self, params, name=None):
        """
        Attempts to make a request to the Alpha Vantage API using a list of API keys.
        Retries with the next key if a request fails or if the API returns an error/note.
        """
        if name is None:
            name = params.get('function', 'unknown_function')

        # Ensure datatype is json if not specified, for most endpoints
        if 'datatype' not in params and params.get('function') not in ['LISTING_STATUS', 'EARNINGS_CALENDAR', 'IPO_CALENDAR']: # These might default to CSV
            params['datatype'] = 'json'
        elif params.get('function') in ['LISTING_STATUS', 'EARNINGS_CALENDAR', 'IPO_CALENDAR'] and 'datatype' not in params:
            # For these, we explicitly ask for JSON, though AV might not always honor it.
            params['datatype'] = 'json'


        for key_index, key in enumerate(self.api_keys):
            params['apikey'] = key
            logger.info(f"Attempting API call for '{name}' with key ending '...{key[-4:] if len(key) > 4 else key}' (Key {key_index + 1}/{len(self.api_keys)})")
            try:
                response = requests.get(self.base_url, params=params, timeout=20) # Increased timeout
                response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
                
                # Check if response content is valid JSON
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    # This can happen if AV returns CSV for an endpoint that should be JSON, or an HTML error page
                    logger.warning(f"Failed to decode JSON response for '{name}' with key ...{key[-4:]}. Response text (first 200 chars): {response.text[:200]}...")
                    # If it's one of the known CSV-prone endpoints, we might want to return raw text
                    if params.get('function') in ['LISTING_STATUS', 'EARNINGS_CALENDAR', 'IPO_CALENDAR'] and params.get('datatype') == 'csv':
                         logger.info(f"Returning raw text for CSV endpoint {name}.")
                         self._save_response_to_file(name, response.text, ".csv")
                         return response.text # Or parse CSV here if needed
                    continue # Try next key for other JSON decode errors

                # Check for Alpha Vantage specific error messages or notes
                if isinstance(data, dict): # Ensure data is a dict before checking keys
                    if "Note" in data:
                        logger.warning(f"API key ...{key[-4:]} for '{name}' returned a note: {data['Note']}")
                        continue # Try next key, as this key might be exhausted or call limit reached
                    if "Error Message" in data:
                        logger.warning(f"API key ...{key[-4:]} for '{name}' returned an error: {data['Error Message']}")
                        continue # Try next key

                logger.info(f"Successfully fetched data for '{name}' with key ...{key[-4:]}")
                self._save_response_to_json(name, data) # Save the parsed JSON data
                return data
            
            except requests.exceptions.Timeout:
                logger.warning(f"Request timed out for '{name}' with key ...{key[-4:]}")
                continue 
            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error for '{name}' with key ...{key[-4:]}: {e}")
                continue
            except requests.RequestException as e:
                logger.warning(f"General request error for '{name}' with key ...{key[-4:]}: {e}")
                continue

        logger.error(f"All API keys failed for function '{name}'. Parameters: {params}")
        raise RuntimeError(f"All API keys failed to retrieve data for function '{name}'.")

    def _save_response_to_file(self, name, data_content, extension):
        """Saves response data to a file with the given extension."""
        if not os.path.exists('av_response'):
            try:
                os.makedirs('av_response')
                logger.info("Created directory 'av_response'")
            except OSError as e:
                logger.error(f"Failed to create directory 'av_response': {e}")
                return

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
        filename = f'av_response/{safe_name}-{timestamp}{extension}'
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                if extension == '.json':
                    json.dump(data_content, f, indent=2)
                else:
                    f.write(data_content)
            logger.info(f"Successfully saved response for '{name}' to {filename}")
        except IOError as e:
            logger.error(f"Failed to write response to {filename}: {e}")
        except TypeError as e: # For json.dump issues
             logger.error(f"Data for '{name}' (JSON) is not serializable: {e}")


    def _save_response_to_json(self, name, data):
        """Saves the API response data (dictionary) to a JSON file."""
        self._save_response_to_file(name, data, ".json")


class TopMovers:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api
        self.data = None # To store the fetched movers data

    def fetch_top_movers_data(self):
        """Fetches and stores the top movers data from the API."""
        params = {'function': 'TOP_GAINERS_LOSERS'}
        name = "top_movers_data"
        self.data = self.api._try_request(params, name)
        if not self.data:
             logger.error("Failed to fetch top movers data.")
        return self.data
    
    def get_all_movers_data(self):
        """Returns all fetched top movers data. Fetches if not already available."""
        if self.data is None:
            self.fetch_top_movers_data()
        return self.data

    def get_top_gainers(self):
        """Extracts 'top_gainers' from the fetched data."""
        if self.data is None: self.fetch_top_movers_data()
        top_gainers = self.data.get('top_gainers', []) if self.data else []
        if top_gainers: logger.info(f"Top Gainers (first item): {top_gainers[0]}")
        else: logger.info("No Top Gainers data found.")
        return top_gainers

    def get_top_gainers_symbols(self):
        """Extracts ticker symbols from 'top_gainers'."""
        top_gainers = self.get_top_gainers()
        symbols = [item['ticker'] for item in top_gainers if 'ticker' in item]
        logger.info(f"Top Gainers Symbols: {symbols}")
        return symbols

    def get_top_losers(self):
        """Extracts 'top_losers' from the fetched data."""
        if self.data is None: self.fetch_top_movers_data()
        top_losers = self.data.get('top_losers', []) if self.data else []
        if top_losers: logger.info(f"Top Losers (first item): {top_losers[0]}")
        else: logger.info("No Top Losers data found.")
        return top_losers

    def get_top_losers_symbols(self):
        """Extracts ticker symbols from 'top_losers'."""
        top_losers = self.get_top_losers()
        symbols = [item['ticker'] for item in top_losers if 'ticker' in item]
        logger.info(f"Top Losers Symbols: {symbols}")
        return symbols

    def get_most_actively_traded(self):
        """Extracts 'most_actively_traded' from the fetched data."""
        if self.data is None: self.fetch_top_movers_data()
        most_active = self.data.get('most_actively_traded', []) if self.data else []
        if most_active: logger.info(f"Most Actively Traded (first item): {most_active[0]}")
        else: logger.info("No Most Actively Traded data found.")
        return most_active

    def get_most_actively_traded_symbols(self):
        """Extracts ticker symbols from 'most_actively_traded'."""
        most_active = self.get_most_actively_traded()
        symbols = [item['ticker'] for item in most_active if 'ticker' in item]
        logger.info(f"Most Actively Traded Symbols: {symbols}")
        return symbols

class Charts:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_intraday_time_series(self, symbol, interval='5min', adjusted='true', extended_hours='true', month=None, outputsize='compact'):
        """Fetches intraday time series. Intervals: 1min, 5min, 15min, 30min, 60min."""
        function = 'TIME_SERIES_INTRADAY_EXTENDED' if month else 'TIME_SERIES_INTRADAY'
        params = {
            'function': function, 'symbol': symbol, 'interval': interval,
            'adjusted': adjusted, 'outputsize': outputsize
        }
        if function == 'TIME_SERIES_INTRADAY_EXTENDED':
            if not month: raise ValueError("Month (YYYY-MM) is required for TIME_SERIES_INTRADAY_EXTENDED.")
            params['month'] = month
        if function == 'TIME_SERIES_INTRADAY': params['extended_hours'] = extended_hours
        name = f"intraday_time_series_{symbol}_{interval}{'_'+month if month else ''}"
        return self.api._try_request(params, name)

    def get_daily_time_series(self, symbol, outputsize='compact', adjusted=False):
        """Fetches daily time series. Set adjusted=True for adjusted prices."""
        function = 'TIME_SERIES_DAILY_ADJUSTED' if adjusted else 'TIME_SERIES_DAILY'
        params = {'function': function, 'symbol': symbol, 'outputsize': outputsize}
        name = f"daily_time_series_{symbol}{'_adjusted' if adjusted else ''}"
        return self.api._try_request(params, name)

    def get_weekly_time_series(self, symbol, adjusted=False):
        """Fetches weekly time series. Set adjusted=True for adjusted prices."""
        function = 'TIME_SERIES_WEEKLY_ADJUSTED' if adjusted else 'TIME_SERIES_WEEKLY'
        params = {'function': function, 'symbol': symbol}
        name = f"weekly_time_series_{symbol}{'_adjusted' if adjusted else ''}"
        return self.api._try_request(params, name)

    def get_monthly_time_series(self, symbol, adjusted=False):
        """Fetches monthly time series. Set adjusted=True for adjusted prices."""
        function = 'TIME_SERIES_MONTHLY_ADJUSTED' if adjusted else 'TIME_SERIES_MONTHLY'
        params = {'function': function, 'symbol': symbol}
        name = f"monthly_time_series_{symbol}{'_adjusted' if adjusted else ''}"
        return self.api._try_request(params, name)

    def get_quote(self, symbol):
        """Fetches the latest price and trading information for a symbol."""
        params = {'function': 'GLOBAL_QUOTE', 'symbol': symbol}
        name = f"quote_{symbol}"
        return self.api._try_request(params, name)

    def get_batch_stock_quotes(self, symbols_list):
        """Fetches quotes for multiple symbols. symbols_list should be a list of strings."""
        symbols_str = ",".join(symbols_list)
        params = {'function': 'BATCH_STOCK_QUOTES', 'symbols': symbols_str}
        name = f"batch_stock_quotes_{'_'.join(symbols_list)}"
        return self.api._try_request(params, name)

    def search_symbol(self, keywords):
        """Searches for stock symbols matching the given keywords."""
        params = {'function': 'SYMBOL_SEARCH', 'keywords': keywords}
        name = f"search_symbol_{keywords}"
        return self.api._try_request(params, name)

class Market:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_global_market_status(self):
        """Fetches the current status of major global stock exchanges."""
        params = {'function': 'MARKET_STATUS'}
        name = "global_market_status"
        return self.api._try_request(params, name)

class News:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_news_sentiment(self, tickers=None, topics=None, time_from=None, time_to=None, sort='LATEST', limit=50):
        """
        Fetches news and sentiment data.
        tickers: Comma-separated string of stock symbols (e.g., "AAPL,MSFT").
        topics: Comma-separated string of topics (e.g., "technology,earnings").
        time_from, time_to: YYYYMMDDTHHMM format.
        sort: 'LATEST', 'EARLIEST', 'RELEVANCE'.
        limit: Number of results (max 1000 for premium).
        """
        params = {'function': 'NEWS_SENTIMENT', 'sort': sort, 'limit': str(limit)}
        if tickers: params['tickers'] = tickers
        if topics: params['topics'] = topics
        if time_from: params['time_from'] = time_from
        if time_to: params['time_to'] = time_to
        
        name_parts = ["news_sentiment"]
        if tickers: name_parts.append(tickers.replace(",", "_"))
        if topics: name_parts.append(topics.replace(",", "_"))
        name = "_".join(name_parts)
        return self.api._try_request(params, name)

    def get_earning_call_transcripts(self, symbol, quarter=None, year=None): # year was not in AV docs for this func.
        """
        Fetches earning call transcripts for a given symbol and quarter.
        quarter: e.g., 'Q1', 'Q2'. If None, latest available.
        year: The fiscal year, e.g., 2023. (Note: AV docs for this function don't explicitly list 'year', but it's often used with quarter.
              The function is `EARNINGS_CALL_TRANSCRIPTS`. The API only lists `symbol` and `quarter` (optional) as params.)
              Revisiting AV docs: `EARNINGS_CALL_TRANSCRIPTS` takes `symbol` and `quarter` (optional). No `year`.
        """
        params = {'function': 'EARNINGS_CALL_TRANSCRIPTS', 'symbol': symbol}
        if quarter:
            params['quarter'] = quarter
        # if year: # Not a documented parameter for this specific function
        #     params['year'] = year 
        name = f"earning_call_transcript_{symbol}{'_'+quarter if quarter else '_latest'}"
        return self.api._try_request(params, name)


class Fundamentals:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_company_overview(self, symbol):
        params = {'function': 'OVERVIEW', 'symbol': symbol}
        name = f"company_overview_{symbol}"
        return self.api._try_request(params, name)

    def get_income_statement(self, symbol):
        params = {'function': 'INCOME_STATEMENT', 'symbol': symbol}
        name = f"income_statement_{symbol}"
        return self.api._try_request(params, name)

    def get_balance_sheet(self, symbol):
        params = {'function': 'BALANCE_SHEET', 'symbol': symbol}
        name = f"balance_sheet_{symbol}"
        return self.api._try_request(params, name)

    def get_cash_flow(self, symbol):
        params = {'function': 'CASH_FLOW', 'symbol': symbol}
        name = f"cash_flow_{symbol}"
        return self.api._try_request(params, name)

    def get_earnings(self, symbol): # Removed horizon as it's for EARNINGS_CALENDAR
        params = {'function': 'EARNINGS', 'symbol': symbol}
        name = f"company_earnings_{symbol}"
        return self.api._try_request(params, name)

    def get_listing_status(self, date=None, state='active'):
        """Date format: YYYY-MM-DD."""
        params = {'function': 'LISTING_STATUS', 'state': state, 'datatype': 'json'} # Explicitly request JSON
        if date: params['date'] = date
        name = f"listing_status_{state}{'_'+date if date else ''}"
        return self.api._try_request(params, name)

    def get_earnings_calendar(self, symbol=None, horizon='3month'):
        """Horizon: 3month, 6month, 12month."""
        params = {'function': 'EARNINGS_CALENDAR', 'horizon': horizon, 'datatype': 'json'} # Explicitly request JSON
        if symbol: params['symbol'] = symbol
        name = f"earnings_calendar_{horizon}{'_'+symbol if symbol else ''}"
        return self.api._try_request(params, name) # This returns CSV by default from AV, JSON may or may not work.

    def get_ipo_calendar(self):
        params = {'function': 'IPO_CALENDAR', 'datatype': 'json'} # Explicitly request JSON
        name = "ipo_calendar"
        return self.api._try_request(params, name) # This returns CSV by default from AV, JSON may or may not work.

class SECFiling:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_sec_filings(self, symbol, filing_type=None, cik=None): # Added filing_type and cik as per AV docs
        """
        Fetches SEC filings for a company.
        symbol: Company symbol.
        filing_type: Optional. e.g., 10-K, 10-Q, 8-K, etc.
        cik: Optional. Company CIK.
        """
        params = {'function': 'SEC_FILINGS', 'symbol': symbol}
        if filing_type:
            params['filing_type'] = filing_type
        if cik: # If CIK is provided, symbol might be redundant but AV docs list both.
            params['cik'] = cik
        
        name_parts = ["sec_filings", symbol]
        if cik: name_parts.append(f"cik_{cik}")
        if filing_type: name_parts.append(filing_type)
        name = "_".join(name_parts)
        return self.api._try_request(params, name)

class EconomicIndicators:
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_real_gdp(self, interval='quarterly'):
        params = {'function': 'REAL_GDP', 'interval': interval}
        return self.api._try_request(params, f"real_gdp_{interval}")

    def get_real_gdp_per_capita(self):
        params = {'function': 'REAL_GDP_PER_CAPITA'}
        return self.api._try_request(params, "real_gdp_per_capita")

    def get_treasury_yield(self, interval='monthly', maturity='10year'):
        params = {'function': 'TREASURY_YIELD', 'interval': interval, 'maturity': maturity}
        return self.api._try_request(params, f"treasury_yield_{maturity}_{interval}")

    def get_federal_funds_rate(self, interval='monthly'):
        params = {'function': 'FEDERAL_FUNDS_RATE', 'interval': interval}
        return self.api._try_request(params, f"federal_funds_rate_{interval}")

    def get_cpi(self, interval='monthly'):
        params = {'function': 'CPI', 'interval': interval}
        return self.api._try_request(params, f"cpi_{interval}")

    def get_inflation(self):
        params = {'function': 'INFLATION'}
        return self.api._try_request(params, "inflation")
    
    def get_inflation_expectation(self):
        params = {'function': 'INFLATION_EXPECTATION'}
        return self.api._try_request(params, "inflation_expectation")

    def get_consumer_sentiment(self):
        params = {'function': 'CONSUMER_SENTIMENT'}
        return self.api._try_request(params, "consumer_sentiment")

    def get_retail_sales(self):
        params = {'function': 'RETAIL_SALES'}
        return self.api._try_request(params, "retail_sales")

    def get_durables(self):
        params = {'function': 'DURABLES'}
        return self.api._try_request(params, "durables")

    def get_unemployment_rate(self):
        params = {'function': 'UNEMPLOYMENT'}
        return self.api._try_request(params, "unemployment_rate")

    def get_nonfarm_payroll(self):
        params = {'function': 'NONFARM_PAYROLL'}
        return self.api._try_request(params, "nonfarm_payroll")

class Analysis: # Technical Indicators
    def __init__(self, api: AlphaVantageAPI):
        self.api = api

    def get_technical_indicator(self, indicator_function_name, symbol, interval, time_period=None, series_type=None, 
                                fastlimit=None, slowlimit=None, matype=None, fastperiod=None, slowperiod=None,
                                signalperiod=None, fastmatype=None, slowmatype=None, signalmatype=None,
                                nbdevup=None, nbdevdn=None, acceleration=None, maximum=None,
                                fastkperiod=None, slowkperiod=None, slowdperiod=None, slowkmatype=None, slowdmatype=None,
                                **kwargs):
        """
        Fetches data for a specified technical indicator.
        Refer to Alpha Vantage documentation for parameters specific to each indicator.
        Common params: symbol, interval, time_period, series_type ('close', 'open', 'high', 'low')
        Example indicator_function_names: SMA, EMA, MACD, RSI, BBANDS, STOCH etc.
        """
        params = {
            'function': indicator_function_name.upper(), 'symbol': symbol, 'interval': interval
        }
        if time_period: params['time_period'] = time_period
        if series_type: params['series_type'] = series_type
        if fastlimit is not None: params['fastlimit'] = fastlimit # Allow 0
        if slowlimit is not None: params['slowlimit'] = slowlimit # Allow 0
        if matype is not None: params['matype'] = matype # Allow 0
        if fastperiod: params['fastperiod'] = fastperiod
        if slowperiod: params['slowperiod'] = slowperiod
        if signalperiod: params['signalperiod'] = signalperiod
        if fastmatype is not None: params['fastmatype'] = fastmatype
        if slowmatype is not None: params['slowmatype'] = slowmatype
        if signalmatype is not None: params['signalmatype'] = signalmatype
        if nbdevup: params['nbdevup'] = nbdevup
        if nbdevdn: params['nbdevdn'] = nbdevdn
        if acceleration: params['acceleration'] = acceleration
        if maximum: params['maximum'] = maximum
        if fastkperiod: params['fastkperiod'] = fastkperiod
        if slowkperiod: params['slowkperiod'] = slowkperiod
        if slowdperiod: params['slowdperiod'] = slowdperiod
        if slowkmatype is not None: params['slowkmatype'] = slowkmatype
        if slowdmatype is not None: params['slowdmatype'] = slowdmatype
        
        params.update(kwargs) # Add any other specific kwargs passed
        name = f"tech_{indicator_function_name}_{symbol}_{interval}"
        return self.api._try_request(params, name)

    def get_sma(self, symbol, interval, time_period, series_type='close'):
        return self.get_technical_indicator('SMA', symbol, interval, time_period=time_period, series_type=series_type)

    def get_ema(self, symbol, interval, time_period, series_type='close'):
        return self.get_technical_indicator('EMA', symbol, interval, time_period=time_period, series_type=series_type)

    def get_rsi(self, symbol, interval, time_period, series_type='close'):
        return self.get_technical_indicator('RSI', symbol, interval, time_period=time_period, series_type=series_type)

    def get_macd(self, symbol, interval, series_type='close', fastperiod=12, slowperiod=26, signalperiod=9):
        return self.get_technical_indicator('MACD', symbol, interval, series_type=series_type, 
                                            fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)

    def get_bbands(self, symbol, interval, time_period, series_type='close', nbdevup=2, nbdevdn=2, matype=0):
        return self.get_technical_indicator('BBANDS', symbol, interval, time_period=time_period, series_type=series_type,
                                            nbdevup=nbdevup, nbdevdn=nbdevdn, matype=matype)
    
    def get_stoch(self, symbol, interval, fastkperiod=5, slowkperiod=3, slowdperiod=3, slowkmatype=0, slowdmatype=0):
        return self.get_technical_indicator('STOCH', symbol, interval, fastkperiod=fastkperiod, slowkperiod=slowkperiod,
                                            slowdperiod=slowdperiod, slowkmatype=slowkmatype, slowdmatype=slowdmatype)

class AISuggestion:
    def __init__(self):
        pass # Placeholder

    def generate_suggestion(self, data):
        suggestion = "This is a placeholder for AI-generated suggestions based on the provided data."
        logger.info(f"AI Suggestion: {suggestion}")
        return suggestion

class MongoDBHandler:
    def __init__(self):
        pass # Placeholder for MongoDB connection initialization

    def save_data(self, collection_name, data):
        # Placeholder for saving data to MongoDB
        logger.info(f"Placeholder: Data for {collection_name} would be saved to MongoDB here.")


# 使用示範
if __name__ == '__main__':
    # IMPORTANT: Replace 'YOUR_API_KEY' with your actual Alpha Vantage API key.
    # You can use a list of keys if you have multiple: ['KEY1', 'KEY2']
    api_keys = ['YOUR_API_KEY', "91KHXVQG2QAUVI2P"] 
    
    # Filter out placeholder keys before initializing
    actual_api_keys = [key for key in api_keys if key and key != 'YOUR_API_KEY' and key.strip()]
    if not actual_api_keys:
        logger.error("No valid API key provided. Please replace 'YOUR_API_KEY' with your actual key.")
        exit()

    api = AlphaVantageAPI(actual_api_keys)

    # Instantiate service classes
    top_movers_service = TopMovers(api)
    charts_service = Charts(api)
    market_service = Market(api)
    news_service = News(api)
    fundamentals_service = Fundamentals(api)
    sec_filing_service = SECFiling(api)
    economic_indicators_service = EconomicIndicators(api)
    analysis_service = Analysis(api)
    
    ai_suggestion_service = AISuggestion() # Placeholder
    mongo_handler_service = MongoDBHandler() # Placeholder

    test_symbol = 'IBM' # Using a common symbol for tests

    try:
        logger.info("\n--- Testing Top Movers ---")
        movers_data = top_movers_service.fetch_top_movers_data() # Fetch once
        if movers_data:
            print(f"Top Gainers (first 1): {json.dumps(top_movers_service.get_top_gainers()[:1], indent=2)}")
            print(f"Top Losers Symbols: {top_movers_service.get_top_losers_symbols()[:5]}")
        
        logger.info(f"\n--- Testing Charts for {test_symbol} ---")
        daily_data = charts_service.get_daily_time_series(test_symbol, outputsize='compact', adjusted=True)
        if daily_data and daily_data.get("Time Series (Daily)"):
            first_day = list(daily_data["Time Series (Daily)"].keys())[0]
            print(f"Adjusted Daily Data for {test_symbol} (first entry {first_day}): {daily_data['Time Series (Daily)'][first_day]}")
        
        quote_data = charts_service.get_quote(test_symbol)
        if quote_data and quote_data.get("Global Quote"):
             print(f"Quote for {test_symbol}: Price {quote_data['Global Quote'].get('05. price')}")

        batch_quotes = charts_service.get_batch_stock_quotes(['AAPL', 'MSFT'])
        if batch_quotes and batch_quotes.get("Stock Quotes"):
            print(f"Batch Quotes (AAPL, MSFT): {json.dumps(batch_quotes['Stock Quotes'][:1], indent=2)}") # First quote

        logger.info("\n--- Testing Market Status ---")
        market_status = market_service.get_global_market_status()
        if market_status and market_status.get("markets"):
            print(f"Market Status (first market): {json.dumps(market_status['markets'][:1], indent=2)}")

        logger.info(f"\n--- Testing News for {test_symbol} ---")
        news_data = news_service.get_news_sentiment(tickers=test_symbol, limit=2)
        if news_data and news_data.get("feed"):
            print(f"News Sentiment for {test_symbol} (first item title): {news_data['feed'][0].get('title')}")
        
        # Note: EARNINGS_CALL_TRANSCRIPTS is a premium endpoint. This might fail with a free key.
        # logger.info(f"\n--- Testing Earning Call Transcript for {test_symbol} (Q1 2023) ---")
        # transcript_data = news_service.get_earning_call_transcripts(test_symbol, quarter='Q1') # Year is not a param
        # if transcript_data: # Response structure for transcripts can vary.
        #     print(f"Earning Call Transcript for {test_symbol} Q1 (snippet): {str(transcript_data)[:200]}...")


        logger.info(f"\n--- Testing Fundamentals for {test_symbol} ---")
        overview = fundamentals_service.get_company_overview(test_symbol)
        if overview and overview.get("Symbol"):
            print(f"Company Overview for {test_symbol}: Name - {overview.get('Name')}, Sector - {overview.get('Sector')}")

        # IPO Calendar often returns CSV-like data even when JSON is requested or is empty.
        # logger.info("\n--- Testing IPO Calendar ---")
        # ipo_cal = fundamentals_service.get_ipo_calendar()
        # if ipo_cal:
        # print(f"IPO Calendar (first 200 chars): {str(ipo_cal)[:200]}...")


        logger.info(f"\n--- Testing SEC Filings for {test_symbol} ---")
        sec_filings = sec_filing_service.get_sec_filings(test_symbol, filing_type="10-K")
        if sec_filings and sec_filings.get("filings"):
             print(f"SEC Filings (10-K) for {test_symbol} (first filing date): {sec_filings['filings'][0].get('filingDate') if sec_filings['filings'] else 'N/A'}")


        logger.info("\n--- Testing Economic Indicators ---")
        real_gdp = economic_indicators_service.get_real_gdp(interval='annual')
        if real_gdp and real_gdp.get("data"):
            print(f"Annual Real GDP (latest): {json.dumps(real_gdp['data'][0], indent=2)}")

        logger.info(f"\n--- Testing Technical Analysis (SMA) for {test_symbol} ---")
        sma_data = analysis_service.get_sma(test_symbol, interval='daily', time_period='20')
        if sma_data and sma_data.get("Technical Analysis: SMA"):
            first_sma_date = list(sma_data["Technical Analysis: SMA"].keys())[0]
            print(f"SMA for {test_symbol} (first entry {first_sma_date}): {sma_data['Technical Analysis: SMA'][first_sma_date]}")
            
        # Placeholder examples
        logger.info("\n--- AI Suggestion (Placeholder) ---")
        suggestion = ai_suggestion_service.generate_suggestion({"data_point": "some_value"})
        print(suggestion)

        logger.info("\n--- MongoDB Save (Placeholder) ---")
        if movers_data:
            mongo_handler_service.save_data('top_movers_collection', movers_data)

    except ValueError as ve:
        logger.error(f"Configuration Error: {ve}")
    except RuntimeError as e:
        logger.error(f"API Request Error: {e}")
    except Exception as ex:
        logger.error(f"An unexpected error occurred: {ex}", exc_info=True)

