import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),  '..', '..')))
import pytz
from datetime import datetime, time as dt_time


class TradingScheduler:
    """
    Determines if the current time is within defined trading windows,
    and whether a task should run based on configured intervals.
    """

    def should_run_now(self, debug=False):
        est = pytz.timezone('US/Eastern')
        now_dt = datetime.now(est)
        now = now_dt.time()

        if not debug:
            if now_dt.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                return False

        # Define trading periods and their execution intervals (in minutes)
        trading_periods = [
            {'start': dt_time(4, 0), 'end': dt_time(7, 45), 'interval_minutes': 5},
            {'start': dt_time(7, 46), 'end': dt_time(9, 45), 'interval_minutes': 1},
            {'start': dt_time(9, 46), 'end': dt_time(10, 32), 'interval_minutes': 2},
            {'start': dt_time(10, 33), 'end': dt_time(20, 0), 'interval_minutes': 5}
        ]

        if debug:
            trading_periods = [{'start': dt_time(0, 0), 'end': dt_time(23, 59), 'interval_minutes': 1}]

        now_minutes = now.hour * 60 + now.minute

        for period in trading_periods:
            start = period['start']
            end = period['end']
            interval = period['interval_minutes']
            if start <= now <= end:
                start_minutes = start.hour * 60 + start.minute
                return (now_minutes - start_minutes) % interval == 0
        return False