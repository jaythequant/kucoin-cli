from sqlalchemy import Float, DateTime
from progress.bar import Bar
import sqlalchemy
import timedelta
import math
import datetime as dt
from kucoincli.client import Client
from kucoincli.utils._helpers import _parse_date
import logging
import time

###############################################################################################################
# Data pipeline connecting kucoin historic OHLCV data (acquired via API) to SQL db through SQLAlchemy engine. #
###############################################################################################################

def pipeline(
    tickers:str or list, engine:sqlalchemy.engine, end:str or dt.datetime, 
    start:str or dt.datetime=None, interval:str="1day", loop_range:int=None, 
    loop_increment:int=1500, chunk_size:int=500, schema:str=None, 
    if_exists:str="append", progress_bar:bool=True,
) -> None:
    """Data acquisition pipeline from KuCoin OHLCV API call -> SQL database.

    Leverage `pandas`, `sqlalchemy`, and `kucoincli.client` to obtain, format,
    and catalogue OHLCV data in a permanent database. 

    Notes
    -----
        * Be aware that KuCoin servers are on UTC time. If this is not accounted for
        returns may be inaccurate. Returns may be unexpected when using naive
        datetime objects rather than strings for the `start` or `end` arguments.
        * This pipeline is a wrapper utilizing the `kucoincli.client` function 
        `ohlcv`. For details on the underlying data acquisition, reference 
        the docstring.

    Parameters
    ----------
    tickers : str or list
        Ticker or list of tickers to call Kucoin API for OHLCV data (e.g., BTC-USDT).
    engine : sqlalchemy.engine
        SQLAlchemy engine. For further information about engine objects review the
        `sqlalchemy.create_engine` documentation.
    end : datetime.datetime or str
        Latest date in range. Date input may be either string (e.g., YYYY-MM-DD or 
        YYYY-MM-DD HH:MM:SS) or a datetime object. See `kucoincli.client.ohlcv` 
        for further formatting details. 
    start : datetime.datetime or str
        (Optional) Earliest date in range. User must input either `start` or `loop_range`.
        See `end` for formatting details.
    interval : str
        (Optional) OHLCV interval frequency. Default=1day. Options: 1min, 3min, 5min, 15min, 
        30min, 1hour, 2hour, 4hour, 6hour, 8hour, 12hour, 1day, 1week
    loop_range : int 
        (Optional) Rather than specifying an earliest date, users may specify a latest date and 
        obtain data in `loop_increment` chunks for `loop_range` API calls. For example, if we 
        specify `end="2022-01-01"`, `loop_increment=100`, and `loop_range=10`, the pipeline
        will call 1000 bars at `interval` granularity starting with 2022-01-01 and walking 
        backwards.
        | Note: `loop_range` will be ignored unless `end=None`.
    loop_increment : int 
        (Optional) Used to control the max number bars of OHLCV data retrieved per call. 
        Max bars per call is 1500. Default=1500.
    schema : str 
        (Optional) SQL schema in which to store acquired OHLCV data. Default=None.
        SQLite databases may not use schema argument. mySQL or psql databases will 
        utilize default scheme if `schema=None`. For further information review
        `pandas.to_sql`.
    chunk_size : int 
        (Optional) Chunksize for use by `pandas.to_sql`. Chunksize may be 
        optimized for better read/write performance to SQL database. 
        See `pandas.to_sql` documentation for further details.
    progress_bar : bool 
        (Optional) Displays a loading bar and timer for each asset queried.
        Default=True
    if_exists : str
        (Optional) Control the pipelines behavior if a table already exists in the 
        defined database/schema. Default=`append`. Options: `fail`, `replace`, `append`.
        For further details see  `pandas.to_sql` docs.
        * `fail`: Raise a ValueError.
        * `replace`: Drop the table before inserting new values.
        * `append`: Insert new values to the existing table.

    See Also
    --------
        `kucoincli.client.ohlcv`
    """
    client = Client()   # Instantiate an instance of the client

    # Dictionary keyed to kucoin OHLCV time intervals. 
    # Used to adjust timedelta increments
    increment_dict = {
        "1min": 1, "3min": 3, "5min": 5, "15min": 15, "30min": 30, 
        "1hour": 60, "2hour": 120, "4hour": 240, "6hour": 360, 
        "8hour": 480, "12hour": 720, "1day": 1440, "1week": 10_080
    }
    
    # Convert string to iterable
    if isinstance(tickers, str):
        tickers = [tickers]
    # Parse string to datetime object
    if isinstance(start, str):
        start = _parse_date(start)
    if end:
        if isinstance(end, str):
            end = _parse_date(end)

    # Light error handling to ensure parameter entry is correct
    if loop_range:
        if loop_range <= 0:
            raise ValueError("Interval must be greater than 0")
    if interval not in increment_dict:
        raise KeyError("Param 'interval' incorrectly specified")
    if not loop_range and not end:
        raise ValueError("Must specify either loop_range or end")
    if end <= start:
        raise ValueError("'end' occurs prior to 'start'")
    
    # Convert timedelta to appropriate increments for use in pagination
    td = timedelta.Timedelta(end - start).total.minutes
    # Divide total minutes by minutes in specified increment
    scalar = increment_dict[interval]  
    loop_range = math.ceil((td / scalar) / loop_increment)
    last_loop_increment = math.ceil((td / scalar) % loop_increment)

    logging.info("Initializing data acquisition . . .")

    for ticker in tickers:
        # Setup progress bar if progress_bar = True
        if progress_bar:
            bar = Bar(
                f"Processing {ticker} ...", 
                max=loop_range, 
                suffix='%(percent)d%% Elapsed Time: %(elapsed)ds'
            )
        try:
            # Start-stop intervals scaled by frequency
            period_start = 0 
            period_stop = loop_increment
            for i in range(loop_range):                
                now = end - dt.timedelta(minutes=(period_stop * increment_dict[interval]))
                begin = end - dt.timedelta(minutes=(period_start * increment_dict[interval]))
                df = client.ohlcv(
                    ticker, begin=now, end=begin, interval=interval
                )
                if df.empty: # If the server gives us no data, break to avoid error
                    logging.info("Query returned empty response. Either incorrect asset or no more historic data.")
                    break
                else:
                    # If the server does give us data parse and add to db ... 
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
        except sqlalchemy.exc.OperationalError:
            logging.error("FATAL ERROR: the database is in recovery mode")
            logging.info("Attempting to connect in 30 seconds . . .")
            time.sleep(30)
        if progress_bar:
            bar.finish()

    logging.info("Query complete. Closing pipeline.")
