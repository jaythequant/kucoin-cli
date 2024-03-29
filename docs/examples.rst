Examples
========

I've included three example highlighting the three main uses for the library: (1) Data analysis, (2) Building and maintaining datasets, and (3) Leverage statistical research into algorithmic
trading systems. The GitHub distribution of this package includes an `examples` folder containing the `.py` files for each of the three below examples.

A Quick Data Example
--------------------

At the core of Kucoin-Cli, or KCI, is data acquisition functionality. While there are numerous other REST wrappers and order execution/management libraries available, none match the level of 
out-of-box detail paid by KCI. Below we will go through a quick code snippet showcasing some of the more important research functions the library has to offer as well as conducting a quick
analysis on live data. I strongly encourage readers to skim the below code block and notes, then visit the `examples` folder where there is a Jupyter Notebook containing the same code in
deeper detail. Note that this example was built on KCI version 1.4.6 or greater. Some functions may not run on older versions of the library.


Data Pipeline Setup
-------------------

Below is a simple code example describing how to setup a SQL database using `kucoincli.pipe` module. In `kucoin-cli` distributions later 
than 1.0.0, this code is included in the examples folder labels `pipe_example.py`.

.. code-block:: python

        """"
        ##### A simple data pipeline using `kucoincli.pipe` module #####

        Database created will look like this ...... 

        +----------+-------+-------+-------+-------+-------------+ 
        |   time   |  open | close |  high |  low  |   volume    |  
        +----------+-------+-------+-------+-------+-------------+ 
        |2022-01-01|1001.51|1002.21|1008.32| 999.43|8.14505485512|
        |2022-01-02| 999.49|1000.80|1004.89| 995.32|9.15848158419|
        ...
        ...
        ...
        """

        # Import our modules
        from kucoincli.pipe import pipeline
        from sqlalchemy import create_engine
        import logging

        # Create our sqlite database engine with sqlalchemy.
        # The engine will generate a new database or append
        # to a pre-existing one.
        engine = create_engine("sqlite:///example.db")

        # Add a logger to see pick up some additional output info
        # To retrieve timeout messages set logging level to DEBUG
        fmt = "%(asctime)s [%(levelname)s] %(module)s :: %(message)s"
        logging.basicConfig(level=logging.INFO, format=fmt)
        logging.getLogger(__name__)

        # Setup constants for the pipeline.
        # `pipeline`s are highly configurable 
        # Read the docs for more information
        TICKER = "BTC-USDT"
        START = "2022-04-01"
        END = "2022-05-01"
        INTERVAL = "1min"

        # Now let's open up our pipeline ...
        pipeline(
            tickers=TICKER,     # Tickers to query OHLCV data for
            engine=engine,      # Engine to run our database
            interval=INTERVAL,  # Interval at which to obtain OHLCV
            start=START,        # Earliest date to query from
            end=END,            # Latest date to query from
        )

        # Viola, we have generated a database. 

        # This current pipeline will obtain 30 days of minutely data for our `TICKER` const
        # and store it in an SQLite .db file in our examples folder. 
        # Default it will track its progress with a progress bar and let the user know 
        # when it has finished retrieving and filing the data.

        ## Thats the entire pipeline! As easy as that we have created a permanent ##
        ## SQLite database to draw from for future research. See the SQLalchemy   ##  
        ## documentation (https://docs.sqlalchemy.org/en/14/) for details on how  ##
        ## to interact with our new database.                                     ##


Deploying An algorithms
-----------------------

