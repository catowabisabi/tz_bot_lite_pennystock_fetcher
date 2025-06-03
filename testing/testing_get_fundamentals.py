import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_handler._data_handler import DataHandler

dh = DataHandler()
fundamentals = dh.get_list_of_fundamentals(["REVB", "AAPL", "TSLA"])
print(fundamentals)
