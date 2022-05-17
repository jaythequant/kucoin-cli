from sqlalchemy import Float, Text, DateTime
from progress.bar import Bar
import timedelta
import math
import datetime as dt
from kucoincli.client import Client

####################################################################################################################
# Data pipeline connecting kucoin historic OHLCV data (acquired via API) to SQL schema through SQLAlchemy engine.
####################################################################################################################

# Features I still want to add...
# Progress bar does not reach 100% if end of data is found (needs fixed)
# Logging in both client.get_kline_data and pipeline function

def pipeline(
    tickers: list, schema: str, engine, interval: int, from_date, to_date=None, 
    loop_range:int=None, loop_increment:int=1500, chunk_size:int=500, 
    if_exists:str="append", error_msg:bool=False, progress_bar:bool=True,
) -> None:
    """
    Data acquisition pipeline from KuCoin OHLCV API call ----> SQL database.

    :param tickers: list List of tickers to call Kucoin API for OHLCV data
        Tickers in list must be named the same as Kucoin's naming method (e.g., BTC-USDT)
    :param schema: str SQL schema in which to store acquired OHLCV data.
    :param engine: SQLAlchemy engine (created using "create_engine" function).
    :param client: Client object for making API calls to Kucoin server
    :param interval: OHLCV interval frequency. 
        Options: 1min, 3min, 5min, 15min, 30min, 1hour, 2hour, 4hour, 
            6hour, 8hour, 12hour, 1day, 1week
    :param start_data: Datetime object. Note that Kucoin servers are on UTC time, so it
        is highly recommended that the datetime object used is also UTC time.
        Failure to convert to UTC will result in confusing server response times.
    :param to_date: Datetime object. End date in target date range. See start_date for 
        specific notes on timezone recommendations. Note that to_date will override the
        loop_range parameter. 
    :param loop_range: int Total number of times to loop through API calls. 
        For further context, the Kucoin OHLCV data is paginated with a max return of 1500 rows of 
        OHLCV data of any given interval. Pipeline executes n calls per asset of increment x.
        Where n = loop_range and x = loop_increment. 
        Note: Loop range parameter will is invalid unless to_date = None
    :param loop_increment: int Increment control number of rows of OHLCV data obtained per call
        Max rows allowed by Kucoin per call is 1500. This is the default increment in function.
    :param chunk_size: int Chunksize param for use by Pandas to_sql function. Chunksize may be 
        optimized for better read/write performance to SQL database.
    :param if_exists: {fail, replace, append}, default=append}
        How to behave if the table already exists.
            fail: Raise a ValueError.
            replace: Drop the table before inserting new values.
            append: Insert new values to the existing table.
    :param error_msg: bool Print out any error messages recieved; Default=False
    :param progress_bar: bool Display progress bar; Default=True

    :return: None
    """
    client = Client()   # Instantiate an instance of the client

    # Dictionary keyed to kucoin OHLCV time intervals. 
    # Used to adjust timedelta increments
    increment_dict = {
        "1min": 1, "3min": 3, "5min": 5, "15min": 15, "30min": 30, 
        "1hour": 60, "2hour": 120, "4hour": 240, "6hour": 360, 
        "8hour": 480, "12hour": 720, "1day": 1440, "1week": 10_080
    }

    # Light error handling to ensure parameter entry is correct
    if loop_range:
        if loop_range <= 0:
            raise ValueError("Interval must be greater than 0")
    if interval not in increment_dict:
        raise KeyError("Param 'interval' incorrectly specified")
    if not loop_range and not to_date:
        raise ValueError("Must specify either loop_range or to_date")
    if to_date >= from_date:
        raise ValueError(
            "param 'to_date' occurs prior to param 'from_date'"
        )
    
    # Convert timedelta to appropriate increments for use in pagination
    td = timedelta.Timedelta(from_date - to_date).total.minutes
    # Divide total minutes by minutes in specified increment
    scalar = increment_dict[interval]  
    loop_range = math.ceil((td / scalar) / loop_increment)
    last_loop_increment = math.ceil((td / scalar) % loop_increment)

    print("Initializing data acquisition . . .")

    for ticker in tickers:
        # Setup progress bar if progress_bar = True
        if progress_bar:
            bar = Bar(
                f"Processing {ticker} ...", 
                max=loop_range, 
                suffix='%(percent)d%% Elapsed Time: %(elapsed)ds'
            )
        # Start-stop intervals scaled by frequency
        period_start = 0 
        period_stop = loop_increment
        for i in range(loop_range):                
            now = from_date - dt.timedelta(minutes=(period_start * increment_dict[interval]))
            begin = from_date - dt.timedelta(minutes=(period_stop * increment_dict[interval]))
            df = client.get_kline_history(
                ticker, begin, now, interval, error_msg=error_msg
            )
            if df.empty: # If the server gives us no data, break to avoid error
                break
            else:
                # If the server does give us data parse and add to db ... 
                df["asset"] = ticker.lower() # Construct asset name column
                # Generate SQL friendly name (i.e., adjust BTC-USDT -> btcusdt)
                table_name = ticker.replace("-", "").lower() 
                # Bump period start/stop increments by loop_increment
                if i == len(range(loop_range)) - 2:
                    # For final API call we only increase the period_stop by
                    # the remainder amount i.e., last_loop_increment. 
                    # This is so we only pull data between the from and to
                    # dates specified.
                    period_start = period_start + loop_increment
                    period_stop = period_stop + last_loop_increment
                else:
                    period_start = period_start + loop_increment
                    period_stop = period_stop + loop_increment
                # Write OHLCV data to our SQL database
                df.to_sql(
                    table_name,         # Table in schema
                    engine,             # SQLAlchemy engine
                    schema=schema,      # Schema to write data to
                    if_exists=if_exists,
                    index=True,
                    chunksize=chunk_size,
                    dtype={
                        "asset": Text,
                        "time": DateTime,
                        "open": Float,
                        "close": Float,
                        "high": Float,
                        "low": Float,
                        "volume": Float,
                        "turnover": Float,
                    },
                )
                if progress_bar: 
                    bar.next()  # Moves progress bar along
        if progress_bar:
            bar.finish()

