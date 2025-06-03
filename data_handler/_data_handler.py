import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_handler.merge_data import DataMerge
from data_handler.short_squeeze_scanner2 import ShortSqueezeScanner

from api_tradezero.api_stock_fundamental import FundamentalsFetcher
from api_tradezero.api_news_fetcher import NewsFetcher
from api_tradezero.api_chart import ChartAnalyzer

from get_sec_filings.get_sec_filings_5_demo import SECFinancialAnalyzer

from database._mongodb.mongo_handler import MongoHandler

from zoneinfo import ZoneInfo
from program_starter.class_zeropro_starter import logger
from datetime import datetime, timedelta

import time


ny_today = datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d')


class SymbolMerger:
    def __init__(self, all_keys):
        self.all_keys = all_keys
        
    def merge(self, list_of_symbols, fundamentals, price_results):
        # Create mappings from symbols to their respective data
        symbol_map_fundamentals = {item['symbol']: item for item in fundamentals if item.get('symbol')}
        symbol_map_prices = {item['symbol']: item for item in price_results if item.get('symbol')}

        merged_results = []
        for symbol in list_of_symbols:
            record = {key: None for key in self.all_keys}
            record['symbol'] = symbol

            if symbol in symbol_map_fundamentals:
                record.update(symbol_map_fundamentals[symbol])
            if symbol in symbol_map_prices:
                record.update(symbol_map_prices[symbol])

            merged_results.append(record)

        return merged_results


class DataHandler:
    """
    Main class for handling stock data acquisition, processing, and analysis.
    
    This class orchestrates the entire data flow from fetching fundamentals and price data
    to performing analysis, merging different data sources, and preparing results for
    consumption. It interfaces with multiple APIs and analysis tools to provide comprehensive
    stock information.
    """
    
    def __init__(self):
        self.fundamentals_fetcher = FundamentalsFetcher()
        self.mongo_handler = MongoHandler()
        self.mongo_handler.create_collection('fundamentals_of_top_list_symbols')
        self.news_fetcher = NewsFetcher()
        self.squeeze_scanner = ShortSqueezeScanner()
        
        # Data storage attributes
        self.fundamentals = []
        self.suggestions = []
        self.all_suggestions = []
        self.merged_data = {}
        self.merged_fundamentals = []
        self.sec_filing_financial_analysis_results = []
        self.list_of_symbols = []

    def get_fundamentals(self, symbol):
        """Get fundamental data for a single symbol."""
        return self.fundamentals_fetcher.fetch(symbol)
    
    def get_list_of_fundamentals(self, list_of_symbols):
        """Get fundamental data for multiple symbols."""
        return self.fundamentals_fetcher.fetch_symbols(list_of_symbols)

    def get_analyzer_data(self, symbol):
        """Get chart analysis data for a single symbol."""
        print(f"\n\n====================Getting chart data for symbol: {symbol}====================")  
        analyzer = ChartAnalyzer(symbol)
        result = analyzer.run()
        return result

    def get_price_analyzer_results(self, list_of_symbols):
        """Get price analysis results for multiple symbols."""
        price_analyzer_results = []
        for symbol in list_of_symbols:
            result = self.get_analyzer_data(symbol)
            price_analyzer_results.append(result)
        return price_analyzer_results

    def merge_fundamentals_and_price_data(self, list_of_symbols, fundamentals, price_analyzer_results):
        """Merge fundamental data with price analysis data."""
        # Define all possible fields
        all_keys = [
            'symbol', 'name', 'listingExchange', 'securityType', 'countryDomicile', 'countryIncorporation',
            'isin', 'sector', 'industry', 'lastSplitInfo', 'lastSplitDate', 'lotSize', 'optionable',
            'earningsPerShare', 'earningsPerShareTTM', 'forwardEarningsPerShare', 'nextEarnings',
            'annualDividend', 'last12MonthDividend', 'lastDividend', 'exDividend', 'dividendFrequency',
            'beta', 'averageVolume3M', 'turnoverPercentage', 'bookValue', 'sales', 'outstandingShares', 'float',
            # Add price fields
            'premarket_high', 'premarket_low', 'market_open_high', 'market_open_low', 'day_high', 'day_low',
            'day_close', 'yesterday_close', 'high_change_percentage', 'close_change_percentage',
            'most_volume_high', 'most_volume_low'
        ]

        merger = SymbolMerger(all_keys)
        return merger.merge(list_of_symbols, fundamentals, price_analyzer_results)

    def perform_short_squeeze_analysis(self):
        """Perform short squeeze analysis on fundamental data."""
        logger.info("Starting Short Squeeze Analysis")
        list_of_short_squeeze_results = []
        
        for fundamental in self.fundamentals:
            short_squeeze_results = self.squeeze_scanner.run(
                new_stock_data=fundamental,
                current_price=fundamental['day_close'],
                intraday_high=fundamental['day_high'],
                short_interest=None,
                as_json=True
            )
            list_of_short_squeeze_results.append(short_squeeze_results)
            self.squeeze_scanner.print_readable_analysis()

        logger.info(f"list_of_short_squeeze_results Lengths: {len(list_of_short_squeeze_results)}")
        
        # Merge short squeeze results back
        merger = SymbolMerger([])  # Will be updated in merge method
        self.fundamentals = merger.merge(self.list_of_symbols, self.fundamentals, list_of_short_squeeze_results)
        
        return self.fundamentals

    def handle_symbols(self, list_of_symbols):
        """Process symbols to get fundamentals, price data, and short squeeze analysis."""
        # Get price analysis results
        price_analyzer_results = self.get_price_analyzer_results(list_of_symbols)
        
        # Get fundamental data
        fundamentals = self.get_list_of_fundamentals(list_of_symbols)
        
        # Merge fundamental and price data
        self.fundamentals = self.merge_fundamentals_and_price_data(list_of_symbols, fundamentals, price_analyzer_results)
        
        logger.info(f"Fundamentals Lengths: {len(self.fundamentals)}")
        
        # Perform short squeeze analysis
        return self.perform_short_squeeze_analysis()

    def store_fundamentals_in_db(self):
        """Store or update fundamental data in MongoDB."""
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        date_list = [(ny_time - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        # Query recent fundamental documents
        recent_fundamental_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": [f["symbol"] for f in self.fundamentals]},
                "today_date": {"$in": date_list}
            }
        )
        recent_symbols = set(doc["symbol"] for doc in recent_fundamental_docs)

        # Update fundamentals with recent dates and store in DB
        for fundamental in self.fundamentals:
            if fundamental["symbol"] in recent_symbols:
                dates = [doc["today_date"] for doc in recent_fundamental_docs if doc["symbol"] == fundamental["symbol"]]
                if dates:
                    latest_date = max(dates)
                    fundamental["today_date"] = latest_date
                    self.mongo_handler.upsert_doc(
                        "fundamentals_of_top_list_symbols",
                        {"symbol": fundamental["symbol"], "today_date": latest_date},
                        fundamental
                    )
        time.sleep(1)

    def get_existing_suggestions(self):
        """Get existing suggestions from MongoDB."""
        existing_suggestions = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {"symbol": {"$in": self.list_of_symbols}, 
             "today_date": ny_today,
             "suggestion": {"$exists": True}}
        )
        return existing_suggestions

    def analyze_new_symbols_for_suggestions(self, existing_suggestions):
        """Analyze symbols that haven't been analyzed yet for suggestions."""
        # Find unanalyzed symbols
        analyzed_symbols = {doc["symbol"] for doc in existing_suggestions}
        symbols_to_analyze = [s for s in self.list_of_symbols if s not in analyzed_symbols]

        # Get AI analysis for new symbols
        new_suggestions = []
        if symbols_to_analyze:
            time.sleep(1)
            new_suggestions = self.news_fetcher.get_symbols_news_and_analyze(symbols_to_analyze)
            
            # Store new suggestions in DB
            for suggestion in new_suggestions:
                self.mongo_handler.upsert_doc(
                    "fundamentals_of_top_list_symbols", 
                    {"symbol": suggestion["symbol"], "today_date": ny_today}, 
                    {"suggestion": suggestion["suggestion"]}
                )
        
        return new_suggestions

    def merge_all_suggestions(self, existing_suggestions, new_suggestions):
        """Merge existing and new suggestions."""
        self.all_suggestions = existing_suggestions + new_suggestions
        self.suggestions = self.all_suggestions
        
        # Merge data by symbol
        self.merger = DataMerge(self.fundamentals, self.all_suggestions, self.list_of_symbols)
        self.merged_data = self.merger.merge_data_by_symbol()
        
        return self.all_suggestions

    def get_existing_sec_analysis(self):
        """Get existing SEC filing analysis from MongoDB."""
        already_analyzed_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": self.list_of_symbols},
                "today_date": ny_today,
                "sec_filing_analysis": {"$exists": True}
            }
        )
        already_analyzed_symbols = set(doc["symbol"] for doc in already_analyzed_docs)
        return already_analyzed_symbols

    def perform_sec_filing_analysis(self, already_analyzed_symbols):
        """Perform SEC filing analysis for unanalyzed symbols."""
        # Find symbols that need analysis
        symbols_to_analyze = [s for s in self.list_of_symbols if s not in already_analyzed_symbols]

        sec_filing_results = []
        if symbols_to_analyze:
            analyzer = SECFinancialAnalyzer()
            analyzer.SYMBOL_LIST = symbols_to_analyze
            sec_filing_results = analyzer.run_analysis()

            # Store analysis results in DB
            for analysis_result in sec_filing_results:
                symbol = analysis_result["Symbol"]
                self.mongo_handler.upsert_doc(
                    "fundamentals_of_top_list_symbols",
                    {"symbol": symbol, "today_date": ny_today},
                    {"sec_filing_analysis": analysis_result}
                )
        
        return sec_filing_results

    def build_final_merged_data(self):
        """Build the final merged data structure from all sources."""
        # Get all today's fundamental documents
        today_fundamentals_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": self.list_of_symbols},
                "today_date": ny_today
            }
        )

        # Create mapping dictionaries
        suggestion_map = {s["symbol"]: s["suggestion"] for s in self.suggestions if "suggestion" in s}
        sec_filing_analysis_map = {s["Symbol"]: s["sec_filing_analysis"] for s in self.sec_filing_financial_analysis_results if "sec_filing_analysis" in s}

        # Build merged fundamentals
        self.merged_fundamentals = []
        for doc in today_fundamentals_docs:
            symbol = doc["symbol"]
            merged = {
                "symbol": symbol,
                "fundamental": doc,
            }

            # Add suggestion if available
            if symbol in suggestion_map:
                merged["suggestion"] = suggestion_map[symbol]

            # Add SEC filing analysis if available
            if symbol in sec_filing_analysis_map:
                merged["sec_filing_analysis"] = sec_filing_analysis_map[symbol]

            self.merged_fundamentals.append(merged)

        return self.merged_fundamentals

    def extract_final_results(self):
        """Extract and format final results."""
        # Extract SEC filing analysis results
        new_filing_financial_analysis_results = []
        try:
            for entry in self.merged_fundamentals:
                sec_filing_analysis = entry['fundamental'].get('sec_filing_analysis')
                if sec_filing_analysis:
                    new_filing_financial_analysis_results.append(sec_filing_analysis)
        except Exception as e:
            logger.warning(f"Error extracting sec_filing_analysis: {e}")

        # Extract fundamentals
        new_fundamentals = []
        try:
            for entry in self.merged_fundamentals:
                fundamental = entry['fundamental']
                new_fundamentals.append(fundamental)
        except Exception as e:
            logger.warning(f"Error extracting fundamentals: {e}")

        return new_fundamentals, new_filing_financial_analysis_results

    def print_readable_suggestions(self, suggestions: list[dict]):
        """Print suggestions in a human-readable format."""
        for item in suggestions:
            symbol = item.get("symbol", "Unknown symbol")
            suggestion = item.get("suggestion", "(No suggestion content)")

            print("====================================")
            print(f"📌 Suggestion for {symbol}:\n\n")
            print(suggestion)
            print("\n")

    def get_positions(self):
        """Placeholder for retrieving current positions from trading account."""
        pass

    def get_accounts(self):
        """Placeholder for retrieving account information."""
        pass

    def run(self, list_of_symbols):
        """
        Main execution method that orchestrates the entire data processing pipeline.
        
        Args:
            list_of_symbols (list): List of stock symbols to analyze
            
        Returns:
            tuple: (new_fundamentals, new_filing_financial_analysis_results)
        """
        logger.info(f"Running DataHandler with symbols: {list_of_symbols}")
        
        self.list_of_symbols = list_of_symbols
        
        # Step 1: Process symbols and get fundamentals with analysis
        self.fundamentals = self.handle_symbols(self.list_of_symbols)
        
        # Step 2: Store fundamentals in database
        self.store_fundamentals_in_db()
        
        # Step 3: Handle suggestions
        existing_suggestions = self.get_existing_suggestions()
        new_suggestions = self.analyze_new_symbols_for_suggestions(existing_suggestions)
        self.merge_all_suggestions(existing_suggestions, new_suggestions)
        
        # Step 4: Print new suggestions
        self.print_readable_suggestions(new_suggestions)
        
        # Step 5: Handle SEC filing analysis
        already_analyzed_symbols = self.get_existing_sec_analysis()
        self.sec_filing_financial_analysis_results = self.perform_sec_filing_analysis(already_analyzed_symbols)
        
        # Step 6: Build final merged data
        self.build_final_merged_data()
        
        # Step 7: Extract and return final results
        new_fundamentals, new_filing_financial_analysis_results = self.extract_final_results()
        
        logger.info(f"Processing completed. Returning {len(new_fundamentals)} fundamentals and {len(new_filing_financial_analysis_results)} SEC analyses.")
        
        return new_fundamentals, new_filing_financial_analysis_results