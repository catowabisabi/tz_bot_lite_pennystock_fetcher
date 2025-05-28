import sqlite3
import os
import json
import pytz
from datetime import timedelta
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import pandas as pd


class StockDataManager:
    def __init__(self, db_path: str):
        """
        初始化 StockDataManager 類
        
        Args:
            db_path: SQLite 資料庫的路徑
        """
        # 如果資料夾不存在，先建立資料夾
        folder = os.path.dirname(db_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        print(f"Connected to database: {db_path}")
        
        # 創建表格（如果不存在）
        self._create_tables()
    
    def _create_tables(self):
        """建立所需的資料表"""
        # 建立股票資訊表
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            name TEXT,
            listingexchange TEXT,
            securitytype TEXT,
            countrydomicile TEXT,
            countryincorporation TEXT,
            isin TEXT,
            sector TEXT,
            industry TEXT,
            lastsplitinfo TEXT,
            lastsplitdate TEXT,
            lotsize REAL,
            optionable INTEGER,
            earningspershare REAL,
            earningspersharettm REAL,
            forwardearningspershare REAL,
            nextearnings TEXT,
            annualdividend REAL,
            last12monthdividend REAL,
            lastdividend REAL,
            exdividend TEXT,
            dividendfrequency TEXT,
            beta REAL,
            averagevolume3m REAL,
            turnoverpercentage REAL,
            bookvalue REAL,
            sales REAL,
            outstandingshares INTEGER,
            float INTEGER,
            premarket_high REAL,
            premarket_low REAL,
            market_open_high REAL,
            market_open_low REAL,
            day_high REAL,
            day_low REAL,
            day_close REAL,
            yesterday_close REAL,
            high_change_percentage REAL,
            close_change_percentage REAL,
            most_volume_high REAL,
            most_volume_low REAL,
            key_levels TEXT,
            float_risk TEXT,
            squeeze_score REAL,
            short_signal INTEGER,
            atm_urgency INTEGER,
            hype_score INTEGER,
            suggestion TEXT,
            cik TEXT,
            cash_usd INTEGER,
            cash TEXT,
            debt_usd INTEGER,
            debt TEXT,
            cash_debt_ratio TEXT,
            burn_rate TEXT,
            total_shelf_filings INTEGER,
            valid_shelf_filings INTEGER,
            last_shelf_date TEXT,
            atm_risk_level TEXT,
            risk_reason TEXT,
            industry_cash_benchmark TEXT,
            data_date TEXT,
            trading_recommendation TEXT,
            recommendation_confidence TEXT,
            recommendation_reasons TEXT,
            trading_strategy TEXT,
            short_squeeze_risk TEXT,
            error TEXT,
            est_time TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """)
        
        # 創建唯一索引，用于快速查找
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stock_symbol 
        ON stock_data (symbol)
        """)
        
        self.conn.commit()
    
    def fetch_one(self, query: str, params: tuple = ()):
        """執行查詢並返回一筆資料"""
        self.cursor.execute(query, params)
        return self.cursor.fetchone()
    
    def insert(self, table_name: str, columns: List[str], values: tuple):
        """將資料插入資料表"""
        cols = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(values))
        sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
        self.cursor.execute(sql, values)
        self.conn.commit()
    
    def _get_current_est_time(self) -> str:
        """獲取當前美東時間"""
        return datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S')
    
    def _format_datetime(self, dt_str: str) -> str:
        """格式化日期時間字串"""
        if dt_str and dt_str != "null" and dt_str != "None":
            try:
                return dt_str.split('T')[0]  # 只保留日期部分
            except:
                return dt_str
        return None
    
    def _convert_to_json(self, data: Any) -> Optional[str]:
        """將資料轉換為 JSON 字串"""
        if data is not None:
            if isinstance(data, (list, dict)):
                return json.dumps(data)
            return str(data)
        return None
    
    def _should_create_new_record(self, symbol: str) -> bool:
        """
        判斷是否需要為此股票建立新記錄
        
        如果股票已經存在並且上次更新在24小時內，則不需要新記錄
        """
        query = "SELECT updated_at FROM stock_data WHERE symbol = ? ORDER BY updated_at DESC LIMIT 1"
        result = self.fetch_one(query, (symbol,))
        
        if not result:
            return True  # 資料庫中無此股票，需要新記錄
        
        last_updated = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        last_updated = pytz.timezone('US/Eastern').localize(last_updated)
        
        now_est = datetime.now(pytz.timezone('US/Eastern'))
        
        # 如果上次更新在24小時以上，需要新記錄
        return (now_est - last_updated) > timedelta(hours=24)
    
    def process_data(self, merged_data1: List[Dict], merged_data2: List[Dict]):
        """
        處理兩組合併的資料，並寫入資料庫
        
        Args:
            merged_data1: 第一組股票資料
            merged_data2: 第二組股票資料（包含財務信息）
        """
        # 合併兩組資料，以 symbol 為鍵
        all_symbols = set()
        combined_data = {}
        
        # 處理第一組資料
        for item in merged_data1:
            symbol = item.get('symbol')
            if symbol:
                all_symbols.add(symbol)
                combined_data[symbol] = item
        
        # 處理第二組資料並合併
        for item in merged_data2:
            symbol = item.get('Symbol')
            if symbol:
                all_symbols.add(symbol)
                if symbol not in combined_data:
                    combined_data[symbol] = {}
                
                # 檢查是否有錯誤
                if 'Error' in item:
                    combined_data[symbol]['error'] = item['Error']
                
                # 合併其他資料
                for key, value in item.items():
                    if key != 'Symbol':  # 避免重複
                        # 轉換鍵名為小寫並移除空格
                        sanitized_key = key.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
                        combined_data[symbol][sanitized_key] = value
        
        # 當前美東時間
        now_est = self._get_current_est_time()
        
        # 處理每個股票的資料
        for symbol in all_symbols:
            item_data = combined_data.get(symbol, {})
            
            # 決定是更新現有記錄還是建立新記錄
            if self._should_create_new_record(symbol):
                # 建立新記錄
                self._insert_new_record(symbol, item_data, now_est)
            else:
                # 更新現有記錄的動態欄位
                self._update_existing_record(symbol, item_data, now_est)
    
    def _insert_new_record(self, symbol: str, data: Dict, now_est: str):
        """插入新的股票記錄"""
        columns = ['symbol', 'est_time', 'created_at', 'updated_at']
        values = [symbol, now_est, now_est, now_est]
        
        # 處理基本資訊
        for field in [
            'name', 'listingexchange', 'securitytype', 'countrydomicile', 
            'countryincorporation', 'isin', 'sector', 'industry', 'lastsplitinfo'
        ]:
            columns.append(field)
            values.append(data.get(field))
        
        # 處理日期欄位
        for field in ['lastsplitdate', 'nextearnings', 'exdividend']:
            columns.append(field)
            values.append(self._format_datetime(data.get(field)))
        
        # 處理數值欄位
        for field in [
            'lotsize', 'earningspershare', 'earningspersharettm', 'forwardearningspershare',
            'annualdividend', 'last12monthdividend', 'lastdividend', 'beta', 'averagevolume3m',
            'turnoverpercentage', 'bookvalue', 'sales', 'outstandingshares', 'float'
        ]:
            columns.append(field)
            values.append(data.get(field))
        
        # 處理布爾值欄位
        for field in ['optionable', 'short_signal']:
            columns.append(field)
            value = data.get(field)
            if value is not None:
                values.append(1 if value else 0)
            else:
                values.append(None)
        
        # 處理市場資料
        for field in [
            'premarket_high', 'premarket_low', 'market_open_high', 'market_open_low',
            'day_high', 'day_low', 'day_close', 'yesterday_close', 'high_change_percentage',
            'close_change_percentage', 'most_volume_high', 'most_volume_low', 'squeeze_score',
            'atm_urgency', 'hype_score'
        ]:
            columns.append(field)
            values.append(data.get(field))
        
        # 處理陣列和特殊欄位
        columns.append('key_levels')
        values.append(self._convert_to_json(data.get('key_levels')))
        
        # 處理風險和建議
        for field in ['float_risk', 'suggestion']:
            columns.append(field)
            values.append(data.get(field))
        
        # 處理第二組資料中的欄位
        for db_field, data_field in [
            ('cik', 'cik'),
            ('cash_usd', 'cash_usd'),
            ('cash', 'cash'),
            ('debt_usd', 'debt_usd'),
            ('debt', 'debt'),
            ('cash_debt_ratio', 'cash_debt_ratio'),
            ('burn_rate', 'burn_rate_months'),
            ('total_shelf_filings', 'total_shelf_filings'),
            ('valid_shelf_filings', 'valid_shelf_filings'),
            ('last_shelf_date', 'last_shelf_date'),
            ('atm_risk_level', 'atm_risk_level'),
            ('risk_reason', 'risk_reason'),
            ('industry_cash_benchmark', 'industry_cash_benchmark'),
            ('data_date', 'data_date'),
            ('trading_recommendation', 'trading_recommendation'),
            ('recommendation_confidence', 'recommendation_confidence'),
            ('recommendation_reasons', 'recommendation_reasons'),
            ('trading_strategy', 'trading_strategy'),
            ('short_squeeze_risk', 'short_squeeze_risk'),
            ('error', 'error')
        ]:
            columns.append(db_field)
            
            if data_field == 'recommendation_reasons':
                # 特別處理陣列欄位
                values.append(self._convert_to_json(data.get(data_field)))
            else:
                values.append(data.get(data_field))
        
        # 插入資料
        self.insert('stock_data', columns, tuple(values))
    
    def _update_existing_record(self, symbol: str, data: Dict, now_est: str):
        """更新現有的股票記錄的動態欄位"""
        # 首先獲取最新的記錄ID
        self.cursor.execute("""
            SELECT id FROM stock_data 
            WHERE symbol = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (symbol,))
        result = self.cursor.fetchone()
        
        if not result:
            return  # 沒有找到記錄
        
        record_id = result[0]
        
        # 只更新會變動的欄位
        dynamic_fields = [
            'premarket_high', 'premarket_low', 'market_open_high', 'market_open_low',
            'day_high', 'day_low', 'day_close', 'yesterday_close', 'high_change_percentage',
            'close_change_percentage', 'most_volume_high', 'most_volume_low', 'squeeze_score',
            'short_signal', 'atm_urgency', 'hype_score', 'est_time', 'updated_at'
        ]
        
        # 建立 SET 子句
        set_clauses = []
        values = []
        
        for field in dynamic_fields:
            if field in ['short_signal']:
                # 處理布爾值
                value = data.get(field)
                if value is not None:
                    set_clauses.append(f"{field} = ?")
                    values.append(1 if value else 0)
            elif field in ['est_time', 'updated_at']:
                # 更新時間戳
                set_clauses.append(f"{field} = ?")
                values.append(now_est)
            else:
                # 一般欄位
                if field in data:
                    set_clauses.append(f"{field} = ?")
                    values.append(data.get(field))
        
        if set_clauses:
            # 執行更新
            values.append(record_id)  # WHERE 條件的參數
            sql = f"UPDATE stock_data SET {', '.join(set_clauses)} WHERE id = ?"
            self.cursor.execute(sql, tuple(values))
            self.conn.commit()
    
    def close(self):
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()