Examples
========

I've included several examples here highlighting the three main uses for the library: (1) Data analysis, (2) Building and maintaining datasets, and (3) Leveraging statistical research into 
algorithmic trading systems. The GitHub distribution of this package includes an `examples` folder containing the `.py` / `.ipynb` files for each example. Hopefully after browsing these
examples you'll feel confident enough yourself to get to work on your own research.

Basics of Data Analysis
-----------------------

At the core of Kucoin-Cli, or KCI, is data acquisition functionality. While there are numerous other REST wrappers and order execution/management libraries available, none match the level of 
out-of-box detail paid by KCI. Below we will go through a quick code snippet showcasing some of the more important research functions the library has to offer as well as conducting a quick
analysis on live data. I strongly encourage readers to skim the below code block and notes, then visit the `examples` folder where there is a Jupyter Notebook containing the same code in
deeper detail. Note that this example was built on KCI version 1.4.6 or greater. Some functions may not run on older versions of the library.

.. code-block:: python

    pass

Data Pipeline Setup
-------------------

Below is a simple code example describing how to setup a SQL database using `kucoincli.pipe` module. In `kucoin-cli` distributions later 
than 1.0.0, this code is included in the examples folder labels `pipe_example.py`.

.. code-block:: python

        """"
        ##### A simple data pipeline using `kucoincli.pipe` module #####

        Database created will look like this ...... 

        +----------+-------+-------+-------+-------+-------------+-----------+
        |   time   |  open | close |  high |  low  |   volume    | turnover  |
        +----------+-------+-------+-------+-------+-------------+-----------+
        |2022-01-01|1001.51|1002.21|1008.32| 999.43|8.14505485512| 8157.3490 |
        |2022-01-02| 999.49|1000.80|1004.89| 995.32|9.15848158419| 9153.8091 |
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

Viola, we have generated a database in as little as few dozen lines of code. Let's briefly review the features of the datebase: This is a SQLite .db file which has now been added to the current
working directory. The database contains 30 days of OHLC(V) data between April 1st, 2022 and May 1st, 2022 for Bitcoin quoted in Tether at 1 minute granularity. Our database consists of six
columns: 

* `Open`: Execution price of initial trade during the period.
* `High`: Highest filled trade execution price during the period.
* `Low`: Lowest filled trade execution price during the period.
* `Close`: Execution price of final trade during period.
* `Volume`: Amount of base currency exchanged.
* `Turnover`: Amount of quote currency exchanged. Turnover is equivalent to Close x Volume.

The `pipeline` function gives us a handy progress bar print out with a timer, but this can be disabled via the `progress_bar` argument should user's prefer a less verbose output.

Simple as that, we've laid out the entire pipeline! We now have a permanent SQLite database to draw from for future research. 

.. admonition:: Further Reading

    * For information on how to connect Python to your new database see the SQLalchemy documentation (https://docs.sqlalchemy.org/en/14/)
    * For a brief introduction to SQLite check out SQLite's documentation (https://www.sqlite.org/docs.html)
    * For a much more heavy-duty database solution check out my preferred SQL database language, Postgres (https://www.postgresql.org/docs/)

Deploying An Algorithm
----------------------

So you've built yourself a database. You've plugged into all the historic data on the exchange. You've thought about key relationships and inefficiencies that might exist in the
volatile, fragmented world of crypto and you've done your quantitative and qualitative research to test your hypothesis. You used your favorite backtesting platform (VectorBT, anyone?),
to run a cross-validated simulation on historic data and amazingly its doing great even out of sample. Now it's time to for the real test: Live trading. I will add a word 
of caution here: Live trading behaves quite differently than your backtest. Market dynamics change quickly and order slippage and market impact are tough to measure in a backtest.
Unlike the nicely sanitized simulatation world you tested in, algorithms living in a cloud somewhere and constantly interfacing with an exchange will run into glitches, connection issues, 
and other malicious and unanticipated issues. Going from the rigorous theoretical landscape you lived in to develop the strategy to the treacherous engineering landscape ahead will require 
quite a different set of skills and knowledge. Manage risk wisely, don't push all in, and stabilize your execution engines **before** you scale them. If you do not, bad things will happen.

A final note. In my own live trading, I use this library as my sole backend engine because it's important to me to have full control over the code. I want things to behave exactly how I want
them to and, if an issue comes up, I feel that I can't afford to have my PnL in someone else's hands. In reality, there are some wonderful libraries available for order execution that you
may want to review and consider before commiting to this one. Namely, CCXT, the official SDK for KuCoin's exchange. I have not used CCXT in live situations myself, but it is extremely
well built and may provide additional functionality for your execution needs that this library doesn't support (See this note on stop losses in the FAQ). That said, I have found this 
library more than adequate for my live execution needs and it was built explicitly with high-frequency, long-short execution in mind.

**As stated in the README, this is an unofficial implementation of the KuCoin Rest and Websocket API v2. Use this package at your own risk.**

Without further adieu, let's take a look at an extremely niave (read that as bad) SMA cross strategy using intraday OHLC(V) data. Be fully aware, this is for education purposes only. I have
not tested or backtested this strategy. Moreover, SMA cross strategies empirically do not work [citation here]. What I want to accomplish here is a demonstration of how you, the user, should 
structure your own algorithms, should you choose KCI as your execution backend.

.. code-block:: python

    pass

Now that we've created our Strategy class, we are ready to load up the strategy and kick off some live trades. Doing so is very easy:

.. code-block:: python

    # Your own credentials here 
    # Don't do this in real code. Use python-dotenv or add the variable to PATH
    API_KEY = 'api_key' 
    API_SECRET = 'api_secret' 
    API_PASSPHRASE = 'api_passphrase' 

    # Let's establish our strategy constants
    ASSET = 'BTC-USDT'      # The strategy will run against Bitcoin quoted in Tether
    FAST_SMA = 50           # Calculate our "fast" simple moving average based on 50 days of data
    SLOW_SMA = 200          # Calculate our "slow" simple moving average based on 200 days of data
    GRANULARITY = '1hour'   # Moving averages will calculate using 1 hour granularity data
    ORDER_SIZE = 10         # Open new orders with a fixed 10 USDT size

    # Now we initialize our order class by loading it with our trade params and API info.
    strategy = SMACross(
        asset=ASSET,
        fast_sma=FAST_SMA,
        slow_sma=SLOW_SMA,
        interval=GRANULARITY,
        order_size=ORDER_SIZE,
        api_key=API_KEY,
        api_secret=API_SECRET,
        api_passphrase=API_PASSPHRASE,
    )

    # Finally, we will call the execute function and let the strategy go about its business
    strategy.execute()

Our strategy will generate signals and execute trades till we kill the process or it till it runs into an execution error of some sort. While this strategy may not be valid, I hope it can give
you, the reader, the basic understanding of how to convert your theorized strategy into a fully automated system. Developing this library and the strategies that I am currently running has been
very meaninful to me and I hope it can be meaningful to you as well. Best of luck.