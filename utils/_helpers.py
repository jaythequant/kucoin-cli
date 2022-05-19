import datetime as dt
import timedelta
import re
import math


# Map of interval options for kline data
interval_map = {"min": "minutes", "hour": "hours", "day": "days"}
# Map of number of minutes in hours, days, weeks
minutes_map = {"min": 1, "hour": 60, "day": 1440, "week": 10_080}


def _parse_date(date_string):
    """Parse date string to datetime object"""
    if ":" in date_string:
        dt_obj = dt.datetime.strptime(
            date_string, "%Y-%m-%d %H:%M:%S"
        )
    else:
        dt_obj = dt.datetime.strptime(
            date_string, "%Y-%m-%d"
        )
    return dt_obj


def _parse_interval(begin, end, interval) -> list:
    """
    Parse date range for consumption by get_kline_history function
        in client when obtaining paganated data.

    :param begin: Datetime object. Earliest date in range
    :param end: Datetime object. Latest date in range
    :param interval: Interval at which to parse date range
    
    :return call_range: Returns a list of tuples containing beginning
        and ending date ranges. These ranges will appropriately paganate
        the kline data returned from get_kline_data call in Client
    """
    max_bars = 1500

    _, num, inc = re.split('(\d+)', interval)  # Parse interval
    if inc == "week":   # Special handling for week increment
        num = 7
        inc = "day"
    delt = timedelta.Timedelta(end - begin)
    # Calculate total number of bars needed
    bars = getattr(delt.total, interval_map[inc]) / int(num)

    if bars < max_bars:
        return [(begin, end)]
    else:
        call_ranges = []
        # Calculate number of calls and split to int calls and
        # residual float call
        f, i = math.modf(bars / max_bars) 
        n = 1500 * minutes_map[inc] * int(num)
        begin = begin
        end = end
        for _ in range(int(i)):
            begin = end - dt.timedelta(minutes=n)
            call_ranges.append((begin, end))
            end = begin
        n = int(n * f)
        end = begin
        begin = end - dt.timedelta(minutes=n)
        call_ranges.append((begin, end))
        return call_ranges
