import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),  '..', '..')))
import sqlite3
from program_starter.class_zeropro_starter import logger 


class DatabaseManager:
    """
    Handles checking and creating SQLite tables, and adding columns if needed.
    """
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name

    def table_exists(self):
        # Check if the table already exists in the database
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.table_name,))
        return self.db.cursor.fetchone() is not None

    def setup_table(self):
        # Create table if it doesn't exist
        if not self.table_exists():
            logger.info(f"Table '{self.table_name}' not found. Creating...")
            self.db.create_table(self.table_name,
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
            logger.info(f"Table '{self.table_name}' exists.")

        # Try to add new column if not exists
        try:
            self.db.cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN Latest_Percent_Change REAL DEFAULT 0.0")
            self.db.conn.commit()
            print("✅ Column 'Latest_Percent_Change' added.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("ℹ️ Column 'Latest_Percent_Change' already exists.")
            else:
                raise
