
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_handler._data_handler import DataHandler
from program_starter.class_zeropro_starter import logger
from database.class_db_2 import StockDataManager


class AnalysisRunner:
    """
    Executes fundamental and technical analysis on a list of stock symbols.
    """
    def __init__(self,db_path='database/top_gainer.db'):
        self.db_path = db_path
        
    def run(self, symbols):
        logger.info("Running data analysis...")
        data_handler = DataHandler()
        
        #region Run Data Analysin and Fundamentals
        fundamentals, analysis_results = data_handler.run(symbols)
        db_manager = StockDataManager(self.db_path)
        db_manager.process_data(fundamentals, analysis_results)
        db_manager.close()
       