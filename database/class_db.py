
import sqlite3
from typing import List, Tuple, Any, Optional
import os
import pytz
#import datetime
from datetime import datetime
import pandas as pd

class SQLiteDB:
    def __init__(self, db_path):
        # 如果資料夾不存在，先建立資料夾
        folder = os.path.dirname(db_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        print(f"Connected to database: {db_path}")

    def fetch_one(self, sql: str, params: Tuple[Any] = None) -> Optional[Tuple[Any]]:
        """
        執行查詢並返回單一結果
        
        :param sql: SQL查詢語句
        :param params: 查詢參數（可選）
        :return: 單一結果元組，如果沒有結果則返回None
        """
        if params:
            self.cursor.execute(sql, params)
        else:
            self.cursor.execute(sql)
        return self.cursor.fetchone()

    def create_table(self, table_name: str, columns: str):
        """建立資料表，如：columns='id INTEGER PRIMARY KEY, name TEXT, age INTEGER'"""
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
        self.cursor.execute(sql)
        self.conn.commit()

    def insert(self, table_name: str, columns: List[str], values: Tuple[Any]):
        """插入資料，columns為欄位名清單，values為對應的值"""
        cols = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(values))
        sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
        self.cursor.execute(sql, values)
        self.conn.commit()

    def read(self, table_name: str, conditions: Optional[str] = None) -> List[Tuple[Any]]:
        """讀取資料，可選條件式，如：'WHERE age > 20'"""
        sql = f"SELECT * FROM {table_name} {conditions or ''}"
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def update(self, table_name: str, set_clause: str, conditions: Optional[str] = None):
        """更新資料，如：set_clause='age=30', conditions='WHERE name="Alice"'"""
        sql = f"UPDATE {table_name} SET {set_clause} {conditions or ''}"
        self.cursor.execute(sql)
        self.conn.commit()

    def delete(self, table_name: str, conditions: Optional[str] = None):
        """刪除資料，如：conditions='WHERE age < 18'"""
        sql = f"DELETE FROM {table_name} {conditions or ''}"
        self.cursor.execute(sql)
        self.conn.commit()

    def close(self):
        """關閉連線"""
        self.conn.close()

class WatchListProcessor:
    def __init__(self):
        pass

    def _format_numeric_value(self, x, is_percent=False):
        return round(x, 2) if not is_percent else round(x, 2)

    def _clean_and_format_data(self, df):
        if not df.empty:
            df = df.iloc[1:].reset_index(drop=True)

        numeric_cols = ['Last', '% Change', 'Volume', 'Mkt. Cap',
                        'Free Float Mkt. Cap', 'Float']

        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].replace(['Mkt. Cap', 'Free Float Mkt. Cap', 'Last Split Date', 'Float'], '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce')
                is_percent = '%' in col
                df[col] = df[col].apply(
                    lambda x: self._format_numeric_value(x, is_percent) if pd.notna(x) else ''
                )

        return df
    
    def insert_to_db(self, df: pd.DataFrame, db: SQLiteDB, table_name: str):
        now_est = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S')
        df['est_time'] = now_est
        df['created_at'] = now_est
        df['updated_at'] = now_est

        if 'Latest_Percent_Change' not in df.columns:
            df['Latest_Percent_Change'] = df['Percent_Change']

        df = self._sanitize_column_names(df)

        for _, row in df.iterrows():
            symbol = row['Symbol']
            existing = db.fetch_one(f"SELECT * FROM {table_name} WHERE Symbol = ?", (symbol,))
            if existing:
                # Update specific columns only
                db.cursor.execute(f"""
                    UPDATE {table_name}
                    SET 
                        Latest_Percent_Change = ?,
                        Last = ?,
                        Volume = ?,
                        Mkt_Cap = ?,
                        Free_Float_Mkt_Cap = ?,
                        updated_at = ?
                    WHERE Symbol = ?
                """, (
                    row['Latest_Percent_Change'],
                    row['Last'],
                    row['Volume'],
                    row['Mkt_Cap'],
                    row['Free_Float_Mkt_Cap'],
                    now_est,
                    symbol
                ))
            else:
                db.insert(
                    table_name,
                    list(row.index),
                    tuple(row.values)
                )

        db.conn.commit()
    
        
    def _sanitize_column_names( self,df: pd.DataFrame) -> pd.DataFrame:
        # 將欄位名轉為合法 SQLite 欄位名（只留字母、數字、底線）
        
        df.columns = [
            col.strip().replace('%', 'Percent')
                    .replace(' ', '_')
                    .replace('.', '')
                    .replace('-', '_')
            for col in df.columns
        ]
        return df


if __name__ == '__main__':
    db = SQLiteDB("example.db")

    # 建立表格
    db.create_table("users2", "id INTEGER PRIMARY KEY, name TEXT, age INTEGER, sex TEXT")

    # 新增資料
    db.insert("users2", ["name", "age"], ("Alice", 25))
    db.insert("users2", ["name", "age"], ("Bob", 30))
    db.insert("users2", ["name", "age", 'sex'], ("BoTom", 30, 'male'))  # 新增一筆資料，包含新增欄位b", 30))

    # 讀取資料
    print(db.read("users2"))  # 全部讀取
    print(db.read("users2", "WHERE age > 26"))  # 條件讀取

    # 更新資料
    db.update("users", "age=31", "WHERE name='Bob'")

    # 刪除資料
    db.delete("users", "WHERE age < 30")

    # 關閉資料庫連線
    db.close()
