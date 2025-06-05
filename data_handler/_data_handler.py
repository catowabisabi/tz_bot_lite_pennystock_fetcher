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
    調試版本的 DataHandler - 添加詳細日誌以找出保存問題
    """
    
    def __init__(self):
        self.fundamentals_fetcher = FundamentalsFetcher()
        self.mongo_handler = MongoHandler()
        self.mongo_handler.create_collection('fundamentals_of_top_list_symbols')
        self.news_fetcher = NewsFetcher()
        self.squeeze_scanner = ShortSqueezeScanner()
        
        # 數據存儲屬性
        self.fundamentals = []
        self.list_of_symbols = []
        self._db_cache = {}

    def _get_db_documents(self, symbols=None, force_refresh=False):
        """統一的數據庫文檔獲取方法，帶緩存機制"""
        if symbols is None:
            symbols = self.list_of_symbols
            
        cache_key = f"{'-'.join(sorted(symbols))}_{ny_today}"
        
        if not force_refresh and cache_key in self._db_cache:
            logger.info(f"Using cached data for {len(symbols)} symbols")
            return self._db_cache[cache_key]
        
        logger.info(f"Querying database for {len(symbols)} symbols on {ny_today}")
        documents = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": symbols},
                "today_date": ny_today
            }
        )
        
        logger.info(f"Found {len(documents)} documents in database")
        self._db_cache[cache_key] = documents
        return documents

    def check_merge_errors(self):
        """檢查合併錯誤"""
        error_data = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {"close_change_percentage": {"$exists": False}}
        )
        print(f"Length of error data: {len(error_data)}")
        if len(error_data) > 0:
            logger.warning(f"Error: 已找到 {len(error_data)} 個錯誤: Symbols: {error_data[0]['symbol']}")
            logger.warning(f"Error in fundamental data for symbol: {error_data[0]['symbol']}")
            logger.warning(f"退出程式")
            exit()
        logger.info(f"No errors in fundamental data")
        return False

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
            logger.info(f"Short Squeeze Analysis for {fundamental['symbol']} Ready!")
            #self.squeeze_scanner.print_readable_analysis()

        logger.info(f"Short Squeeze Analysis Lengths: {len(list_of_short_squeeze_results)}")
        
        # 優化的合併方法：直接字典更新
        squeeze_results_map = {item['symbol']: item for item in list_of_short_squeeze_results if item.get('symbol')}
        
        for fundamental_item in self.fundamentals:
            symbol = fundamental_item.get('symbol')
            if symbol and symbol in squeeze_results_map:
                # 直接更新現有的 fundamental 字典，避免覆蓋重要字段
                squeeze_data = squeeze_results_map[symbol].copy()
                squeeze_data.pop('symbol', None)  # 移除 symbol 鍵避免重複
                fundamental_item.update(squeeze_data)
                logger.info(f"Short Squeeze Analysis Merged into Fundamentals for {symbol} !")
        
        logger.info(f"Successfully merged short squeeze analysis for {len(squeeze_results_map)} symbols")
        return self.fundamentals

    def handle_symbols(self, list_of_symbols):
        """Process symbols to get fundamentals, price data, and short squeeze analysis."""
        logger.info(f"處理 {len(list_of_symbols)} 個符號的數據")
        
        # Get price analysis results
        price_analyzer_results = self.get_price_analyzer_results(list_of_symbols)
        logger.info(f"獲取到 {len(price_analyzer_results)} 個價格分析結果")
        
        # Get fundamental data
        fundamentals = self.get_list_of_fundamentals(list_of_symbols)
        logger.info(f"獲取到 {len(fundamentals)} 個基本面數據")
        
        # Merge fundamental and price data
        self.fundamentals = self.merge_fundamentals_and_price_data(list_of_symbols, fundamentals, price_analyzer_results)
        logger.info(f"合併後的基本面數據長度: {len(self.fundamentals)}")
        
        # 檢查合併後數據的結構
        if self.fundamentals:
            sample_keys = list(self.fundamentals[0].keys())
            logger.info(f"樣本數據字段: {sample_keys[:10]}...")  # 只顯示前10個字段
        
        # Perform short squeeze analysis
        return self.perform_short_squeeze_analysis() #return fundamentals with short squeeze analysis

    def store_fundamentals_in_db(self):
        """Store or update fundamental data in MongoDB - 添加詳細調試信息"""
        logger.info(f"開始保存 {len(self.fundamentals)} 個基本面數據到數據庫")
        
        # 檢查數據完整性
        for i, fundamental in enumerate(self.fundamentals):
            if not fundamental.get('symbol'):
                logger.error(f"第 {i} 個基本面數據缺少 symbol 字段: {fundamental}")
                continue
            
            # 檢查是否有必要的價格數據
            required_fields = ['day_close', 'close_change_percentage']
            missing_fields = [field for field in required_fields if field not in fundamental or fundamental[field] is None]
            if missing_fields:
                logger.warning(f"Symbol {fundamental['symbol']} 缺少字段: {missing_fields}")
        
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        ny_today = ny_time.strftime('%Y-%m-%d')
        date_list = [(ny_time - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        
        logger.info(f"查詢最近 7 天的數據: {date_list}")

        # Query recent fundamental documents
        recent_fundamental_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": [f["symbol"] for f in self.fundamentals]},
                "today_date": {"$in": date_list}
            }
        )
        
        logger.info(f"找到 {len(recent_fundamental_docs)} 個最近的基本面文檔")
        recent_symbols = set(doc["symbol"] for doc in recent_fundamental_docs)
        
        # 保存計數器
        saved_count = 0
        updated_count = 0

        for fundamental in self.fundamentals:
            symbol = fundamental["symbol"]
            fundamental["today_date"] = ny_today

            # 取出這個 symbol 最近 7 天的舊資料
            recent_docs = [doc for doc in recent_fundamental_docs if doc["symbol"] == symbol]
            
            if recent_docs:
                # 找到最新的那筆（若有多筆）
                latest_doc = max(recent_docs, key=lambda d: d["today_date"])

                # 保留舊資料中其他字段，更新為新資料（新資料優先）
                merged_data = {**latest_doc, **fundamental}
                merged_data["today_date"] = ny_today  # 一定是今天

                try:
                    result = self.mongo_handler.upsert_doc(
                        "fundamentals_of_top_list_symbols",
                        {"symbol": symbol, "today_date": ny_today},
                        merged_data
                    )
                    logger.info(f"更新 {symbol}：合併舊資料後保存為今天的資料")
                    updated_count += 1
                except Exception as e:
                    logger.error(f"更新 {symbol} 時出錯: {e}")
            else:
                # 沒有舊資料，直接插入今天的資料
                try:
                    result = self.mongo_handler.upsert_doc(
                        "fundamentals_of_top_list_symbols",
                        {"symbol": symbol, "today_date": ny_today},
                        fundamental
                    )
                    logger.info(f"新增 {symbol} 為今天的新資料")
                    saved_count += 1
                except Exception as e:
                    logger.error(f"儲存 {symbol} 時出錯: {e}")

        
        # 驗證保存結果
        time.sleep(1)
        verification_docs = self.mongo_handler.find_doc(
            "fundamentals_of_top_list_symbols",
            {
                "symbol": {"$in": [f["symbol"] for f in self.fundamentals]},
                "today_date": ny_today
            }
        )
        logger.info(f"驗證: 數據庫中找到 {len(verification_docs)} 個今日文檔")
        
        # 檢查是否所有數據都已保存
        saved_symbols = set(doc["symbol"] for doc in verification_docs)
        missing_symbols = set(f["symbol"] for f in self.fundamentals) - saved_symbols
        if missing_symbols:
            logger.error(f"以下符號的數據未能保存到數據庫: {missing_symbols}")
        else:
            logger.info("所有基本面數據已成功保存到數據庫")

    def process_suggestions(self):
        """統一處理建議的方法"""
        logger.info("Processing suggestions...")
        
        # 獲取數據庫中已有建議的文檔
        documents = self._get_db_documents()
        existing_suggestions_symbols = {
            doc["symbol"] for doc in documents 
            if doc.get("suggestion")
        }
        
        logger.info(f"找到 {len(existing_suggestions_symbols)} 個已有建議的符號")
        
        # 找出需要分析的新符號
        symbols_to_analyze = [
            symbol for symbol in self.list_of_symbols 
            if symbol not in existing_suggestions_symbols
        ]
        
        # 為新符號獲取AI分析
        if symbols_to_analyze:
            logger.info(f"正在為 {len(symbols_to_analyze)} 個新符號分析建議")
            time.sleep(1)
            new_suggestions = self.news_fetcher.get_symbols_news_and_analyze(symbols_to_analyze)
            
            # 直接更新到數據庫，不保存副本
            for suggestion in new_suggestions:
                try:
                    result = self.mongo_handler.upsert_doc(
                        "fundamentals_of_top_list_symbols", 
                        {"symbol": suggestion["symbol"], "today_date": ny_today}, 
                        {"suggestion": suggestion["suggestion"]}
                    )
                    logger.info(f"保存建議 {suggestion['symbol']}: {result}")
                except Exception as e:
                    logger.error(f"保存建議 {suggestion['symbol']} 時出錯: {e}")
            
            # 刷新緩存
            self._get_db_documents(force_refresh=True)
            
            # 打印新建議
            self.print_readable_suggestions(new_suggestions)
            
            return len(new_suggestions)
        
        logger.info("No new symbols need suggestion analysis")
        return 0

    def process_sec_analysis(self):
        """統一處理SEC分析的方法"""
        logger.info("Processing SEC filing analysis...")
        
        # 獲取已有SEC分析的符號
        documents = self._get_db_documents()
        analyzed_symbols = {
            doc["symbol"] for doc in documents 
            if doc.get("sec_filing_analysis")
        }
        
        logger.info(f"找到 {len(analyzed_symbols)} 個已有SEC分析的符號")
        
        # 找出需要分析的符號
        symbols_to_analyze = [
            symbol for symbol in self.list_of_symbols 
            if symbol not in analyzed_symbols
        ]
        
        if symbols_to_analyze:
            logger.info(f"正在為 {len(symbols_to_analyze)} 個符號分析SEC文件")
            analyzer = SECFinancialAnalyzer()
            analyzer.SYMBOL_LIST = symbols_to_analyze
            analysis_results = analyzer.run_analysis()

            # 直接更新到數據庫
            for analysis_result in analysis_results:
                symbol = analysis_result["Symbol"]
                try:
                    result = self.mongo_handler.upsert_doc(
                        "fundamentals_of_top_list_symbols",
                        {"symbol": symbol, "today_date": ny_today},
                        {"sec_filing_analysis": analysis_result}
                    )
                    logger.info(f"保存SEC分析 {symbol}: {result}")
                except Exception as e:
                    logger.error(f"保存SEC分析 {symbol} 時出錯: {e}")
            
            # 刷新緩存
            self._get_db_documents(force_refresh=True)
            
            return len(analysis_results)
        
        logger.info("No new symbols need SEC analysis")
        return 0

    def build_final_results(self):
        """構建最終結果"""
        logger.info("Building final results...")
        
        # 獲取所有今日的基本面文檔
        documents = self._get_db_documents()
        
        # 構建最終結果
        final_fundamentals = []
        final_sec_analyses = []
        
        for doc in documents:
            # 基本面數據
            final_fundamentals.append(doc)
            
            # SEC分析結果（如果存在）
            if "sec_filing_analysis" in doc:
                final_sec_analyses.append(doc["sec_filing_analysis"])
        
        logger.info(f"Final results: {len(final_fundamentals)} fundamentals, {len(final_sec_analyses)} SEC analyses")
        
        return final_fundamentals, final_sec_analyses

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
        調試版本的主執行方法
        """
        logger.info(f"=== 開始運行 DataHandler，處理 {len(list_of_symbols)} 個符號 ===")
        logger.info(f"符號列表: {list_of_symbols}")
        
        self.list_of_symbols = list_of_symbols
        self._db_cache.clear()  # 清空緩存
        
        # Step 1: 處理符號並獲取基本面數據和分析
        logger.info("=== Step 1: 處理符號和基本面數據 ===")
        self.fundamentals = self.handle_symbols(self.list_of_symbols) #return fundamentals with short squeeze analysis
        
        if not self.fundamentals:
            logger.error("❌ 沒有獲取到任何基本面數據！")
            return [], []
        
        logger.info(f"✅ 成功處理 {len(self.fundamentals)} 個基本面數據")
        
        # Step 2: 將基本面數據存儲到數據庫
        logger.info("=== Step 2: 存儲基本面數據到數據庫 ===")
        self.store_fundamentals_in_db()
        
        # Step 3: 處理建議
        logger.info("=== Step 3: 處理建議 ===")
        new_suggestions_count = self.process_suggestions()
        
        # Step 4: 處理SEC分析
        logger.info("=== Step 4: 處理SEC分析 ===")
        new_analyses_count = self.process_sec_analysis()
        
        # Step 5: 構建最終結果
        logger.info("=== Step 5: 構建最終結果 ===")
        final_fundamentals, final_sec_analyses = self.build_final_results()
        
        # Step 6: 檢查合併錯誤
        logger.info("=== Step 6: 檢查合併錯誤 ===")
        self.check_merge_errors()
        
        logger.info(f"""
        === 處理完成！ ===
        - 處理符號數量: {len(self.list_of_symbols)}
        - 新建議數量: {new_suggestions_count}
        - 新SEC分析數量: {new_analyses_count}
        - 返回基本面數據: {len(final_fundamentals)}
        - 返回SEC分析: {len(final_sec_analyses)}
        """)
        
        return final_fundamentals, final_sec_analyses