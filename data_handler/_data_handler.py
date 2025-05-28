import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_handler.merge_data import DataMerge
from data_handler.short_squeeze_scanner2 import ShortSqueezeScanner

from tz_api.api_stock_fundamental import FundamentalsFetcher
from tz_api.api_news_fetcher import NewsFetcher
from tz_api.api_chart import ChartAnalyzer

from get_sec_filings.get_sec_filings_5_demo import SECFinancialAnalyzer

from database._mongodb.mongo_handler import MongoHandler
from datetime import datetime
from zoneinfo import ZoneInfo
from program_starter.class_zeropro_starter import logger


ny_today = datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d')


class SymbolMerger:
    """
    A utility class responsible for merging stock symbol data from different sources.
    
    This class takes data from fundamental analysis and price results and combines them
    into a unified data structure for each symbol, ensuring consistency across all data points.
    
    Attributes:
        all_keys (list): A comprehensive list of all possible data keys that might appear
                        in the merged results.
    """
    def __init__(self, all_keys):
        self.all_keys = all_keys
        

    def merge(self, list_of_symbols, fundamentals, price_results):
        """
        Merges data from different sources for each symbol in the provided list.
        
        Creates a comprehensive record for each symbol by combining fundamental data
        and price data, using a consistent structure defined by all_keys.
        
        Args:
            list_of_symbols (list): List of stock symbols to process
            fundamentals (list): List of dictionaries containing fundamental data for symbols
            price_results (list): List of dictionaries containing price-related data for symbols
            
        Returns:
            list: A list of merged dictionaries, each containing all available data for a symbol
        """
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


#region MAIN ENTRY
"""
MAIN ENTRY
"""	

class DataHandler:
    """
    Main class for handling stock data acquisition, processing, and analysis.
    
    This class orchestrates the entire data flow from fetching fundamentals and price data
    to performing analysis, merging different data sources, and preparing results for
    consumption. It interfaces with multiple APIs and analysis tools to provide comprehensive
    stock information.
    
    The class can process individual symbols or lists of symbols, calculate short squeeze
    potential, and combine analytical results with news data for holistic stock evaluations.
    
    Attributes:
        fundamentals_fetcher: Service for retrieving stock fundamental data
        fundamentals: List to store fundamental data for all processed symbols
        suggestions: List to store news-based suggestions for symbols
        merged_data: Dictionary containing the final merged data from all sources
        analysis_results: Dictionary containing detailed analysis results
    """
    def __init__(self):
        self.fundamentals_fetcher = FundamentalsFetcher()
        self.mongo_handler = MongoHandler()
        self.mongo_handler.create_collection('fundamentals_of_top_list_symbols')
        self.fundamentals = []
        self.suggestions = []
        self.merged_data = {}
        self.analysis_results = {}
        

    def get_fundamentals(self, symbol):
        """
        Fetches fundamental data for a single symbol.
        
        Args:
            symbol (str): The stock symbol to fetch data for
            
        Returns:
            dict: Fundamental data for the requested symbol
        """
        return self.fundamentals_fetcher.fetch(symbol)
    
    def get_list_of_fundamentals(self, list_of_symbols):
        """
        Fetches fundamental data for multiple symbols.
        
        Args:
            list_of_symbols (list): List of stock symbols to fetch data for
            
        Returns:
            list: List of dictionaries containing fundamental data for each symbol
        """
        return self.fundamentals_fetcher.fetch_symbols(list_of_symbols)
    

    def handle_symbol(self, symbol):
        """
        Processes a single symbol to get chart and price-related data.
        
        Uses the ChartAnalyzer to get price and chart data for a specific symbol,
        then outputs the result in a formatted JSON.
        
        Args:
            symbol (str): The stock symbol to analyze
            
        Returns:
            dict: Chart and price analysis results for the symbol
        """
        print(f"\n\n====================Getting chart data for symbol: {symbol}====================")  
        analyzer = ChartAnalyzer(symbol)
        result = analyzer.run()
        #print(json_util.dumps(result, indent=2, ensure_ascii=False))
        return result

    def handle_symbols(self, list_of_symbols):
        """
        Processes multiple symbols to collect price data, fundamental data,
        and perform short squeeze analysis.
        
        This method coordinates the collection of different types of data for each symbol
        and merges them into a unified data structure. It also performs short squeeze
        potential analysis on each symbol.
        
        Args:
            list_of_symbols (list): List of stock symbols to process
            
        Returns:
            list: A list of dictionaries containing comprehensive data for each symbol
        """
        self.squeeze_scanner = ShortSqueezeScanner()
        
        # Process price data
        price_results = []
        for symbol in list_of_symbols:
            result = self.handle_symbol(symbol)
            price_results.append(result)

            


        #print(f"\n\n\n\n\nHandle Symbols: Price results (Raw): {price_results}")

        # Process fundamental data
        fundamentals = self.get_list_of_fundamentals(list_of_symbols)

        

        # Define all possible fields (can be expanded)
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

        # Merge data
        merger = SymbolMerger(all_keys)
        self.fundamentals = merger.merge(list_of_symbols, fundamentals, price_results)

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

        self.fundamentals = merger.merge(list_of_symbols, self.fundamentals, list_of_short_squeeze_results)

        return self.fundamentals
    
    def get_positions(self):
        """
        Placeholder for retrieving current positions from trading account.
        This method is not yet implemented.
        """
        pass

    def get_accounts(self):
        """
        Placeholder for retrieving account information.
        This method is not yet implemented.
        """
        pass


    def print_readable_suggestions(self, suggestions: list[dict]):
        """
        Prints suggestions in a human-readable format.
        
        Takes a list of suggestion dictionaries and formats them for easy reading,
        displaying the symbol and corresponding suggestion.
        
        Args:
            suggestions (list): List of dictionaries containing suggestions for symbols
        """
        for item in suggestions:
            symbol = item.get("symbol", "Unknown symbol")
            suggestion = item.get("suggestion", "(No suggestion content)")

            print("====================================")
            print(f"📌 Suggestion for {symbol}:\n\n")
            print(suggestion)
            print("\n")  # Empty line for separation

    

    #region Run
    def run(self, list_of_symbols):
        logger.info(f"Running DataHandler with symbols: {list_of_symbols}")
        """
        Main execution method that orchestrates the entire data collection and analysis process.
        
        This method coordinates fetching fundamental data, price data, news, and performs
        SEC filings analysis. It then merges all the collected data into a unified structure
        for each symbol and returns the comprehensive results.
        
        Args:
            list_of_symbols (list): List of stock symbols to process
            
        Returns:
            tuple: A tuple containing (merged_data, analysis_results)
                  - merged_data: Dictionary with combined data for each symbol
                  - analysis_results: Dictionary with detailed analysis results
        """
        self.list_of_symbols = list_of_symbols
        #self.handle_symbols(list_of_symbols)

        #region Fundamentals Collection
        # Step 1: 拿最新的 fundamentals, get the latest fundamentals
        self.fundamentals = self.handle_symbols(self.list_of_symbols)
        for fundamental in self.fundamentals:
            fundamental["today_date"] = ny_today
            self.mongo_handler.upsert_doc(
                "fundamentals_of_top_list_symbols", 
                {"symbol": fundamental["symbol"]}, 
                fundamental)#加入新的top list fundamentals
            
        #endregion


        #region Find Suggestion
        # Step 2: 拿所有已有的 suggestions，不管是不是今天才分析 (get existing suggestions)
        existing_suggestions = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {"symbol": {"$in": self.list_of_symbols}, 
             "today_date": ny_today,
             
             "suggestion": {"$exists": True}}
        )


        #region Filter new symbols
        # Step 3: 找出還沒分析的 symbols (find unanalyzed symbols)
        analyzed_symbols = {doc["symbol"] for doc in existing_suggestions}
        symbols_to_analyze = [s for s in self.list_of_symbols if s not in analyzed_symbols]


        #region 插入新的suggestions
        # Step 4: AI 新分析（若有）(AI analysis)
        self.news_fetcher = NewsFetcher()
        new_suggestions = self.news_fetcher.get_symbols_news_and_analyze(symbols_to_analyze)
        for suggestion in new_suggestions:
            self.mongo_handler.upsert_doc(
                "fundamentals_of_top_list_symbols", 
                {"symbol": suggestion["symbol"], "today_date": ny_today}, 
                {"suggestion":suggestion["suggestion"]}
                )
            
        # Step 5: 合併新的和舊的 suggestion (merge suggestions)
        self.all_suggestions = existing_suggestions + new_suggestions
        
        # Step 6: 合併資料 (merge data)
        self.merger = DataMerge(self.fundamentals, self.all_suggestions, self.list_of_symbols)
        self.merged_data = self.merger.merge_data_by_symbol()
        

        # Step 7: 印出建議和合併資料 (print readable suggestions and merged data)
        self.print_readable_suggestions(new_suggestions)
        #print(json.dumps(self.merged_data, indent=2, ensure_ascii=False, default=str))


        # Step 8: 拿所有已有的分析 (get existing analysis results)
        already_analyzed_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": self.list_of_symbols},
                "today_date": ny_today,
                "sec_filing_analysis": {"$exists": True}
            }
        )
        already_analyzed_symbols = set(doc["symbol"] for doc in already_analyzed_docs)


        # Step 9: 找出還沒分析的 symbols
        symbols_to_analyze = [s for s in self.list_of_symbols if s not in already_analyzed_symbols]

        # Step 10: 對未分析的 symbols 做 SEC filings analysis
        self.sec_filing_financial_analysis_results = []
        if symbols_to_analyze:
            self.analyzer = SECFinancialAnalyzer()
            self.analyzer.SYMBOL_LIST = symbols_to_analyze
            self.sec_filing_financial_analysis_results = self.analyzer.run_analysis()

            # Step 11: 把分析結果 update 到相對應 symbol 的 document 中
            for analysis_result in self.sec_filing_financial_analysis_results:
                symbol = analysis_result["Symbol"]
                self.mongo_handler.upsert_doc(
                    "fundamentals_of_top_list_symbols",
                    {"symbol": symbol, "today_date": ny_today},
                    {"sec_filing_analysis": analysis_result}
                )
        
        """ # Step 12: 建立 merged_data2：在 merged_data 基礎上加入 sec_filing_analysis
        merged_data2 = []
        for entry in self.merged_data:
            symbol = entry["symbol"]
            doc = self.mongo_handler.find_doc(
                "fundamentals_of_top_list_symbols",
                {"symbol": symbol, "today_date": ny_today}
            )
            if doc and "sec_filing_analysis" in doc:
                entry["sec_filing_analysis"] = doc["sec_filing_analysis"]
            merged_data2.append(entry) """

        # 先從 DB 撈出所有今天的資料（有可能是 full list）
        today_fundamentals_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": self.list_of_symbols},
                "today_date": ny_today
            }
        )

        # 建立 symbol -> suggestion 映射
        suggestion_map = {s["symbol"]: s["suggestion"] for s in self.suggestions if "suggestion" in s}
        sec_filing_analysis_map = {s["symbol"]: s["sec_filing_analysis"] for s in self.sec_filing_financial_analysis_results if "sec_filing_analysis" in s}

        # merged_data2: 每一筆 today 的資料都收集起來
        self.merged_fundamentals = []
        for doc in today_fundamentals_docs:
            symbol = doc["symbol"]
            merged = {
                "symbol": symbol,
                "fundamental": doc,
            }

            # 加入 suggestion（如果有）
            if symbol in suggestion_map:
                merged["suggestion"] = suggestion_map[symbol]

            
            if symbol in sec_filing_analysis_map:
                merged["sec_filing_analysis"] = sec_filing_analysis_map[symbol]
           

            self.merged_fundamentals.append(merged)



        

        #print("""\n\n\nMerged Fundamentals Data:""")
        #print("""Merged Fundamentals Data: Hidden""")
        #print(json.dumps(self.merged_data, indent=2, ensure_ascii=False, default=str))

        #print("""\nAnalysis Results:""")
        #print("""Analysis Results: Hidden\n\n""")
        #print(json.dumps(self.analysis_results, indent=2, ensure_ascii=False, default=str))

        #print(self.merged_fundamentals)
        new_filing_financial_analysis_results = []
        for entry in self.merged_fundamentals:
            sec_filing_analysis = entry['fundamental']["sec_filing_analysis"]
            new_filing_financial_analysis_results.append(sec_filing_analysis)

        new_fundamentals = []
        for entry in self.merged_fundamentals:
            fundamental = entry['fundamental']
            new_fundamentals.append(fundamental)
            new_fundamentals.append(entry)
        

        return new_fundamentals, new_filing_financial_analysis_results



#region MAIN ENTRY 
if __name__ == "__main__":
    list_of_symbols =  ['FOXO', 'KTTA', 'MRIN']

    data_handler = DataHandler()
    data_handler.run(list_of_symbols)
    


    

    """  bot = TelegramBot()
    message = bot.format_table_for_telegram(
        title="Today's Hot Stocks",
        headers=["Symbol", "Name", "Change"],
        data=[
            {"Symbol": "TSLA", "Name": "Tesla", "Change": "+5.6%"},
            {"Symbol": "AAPL", "Name": "Apple", "Change": "+2.3%"}
        ]
    )
    bot.send_telegram_message(message)
    


     """