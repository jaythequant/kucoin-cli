Examples
========

I've included several examples here highlighting the three main uses for the library: 

    1. Data analysis
    2. Building and maintaining datasets
    3. Deploying algorithmic trading systems 

The GitHub distribution of this package includes an `examples` folder containing the Python or Jupyter Notebook files for each example. Hopefully, after browsing these
examples, you'll feel confident enough to get to work on your own research.

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

One of the novel features of Kucoin-Cli is its in-built data acquisition pipeline. Leveraging the `kucoincli.pipe` module, users can acquire and store large amounts of OHLC(V) data in their
own SQL database. Piping data from KuCoin's server to your own is as simple as importing the module and calling a one-line function. Below, I will outline the most basic use case
for the `pipe` module and review the data that it will acquire. After reviewing this how-to, user's can find and test the program using the `pipe_example.py` file in the `examples`
folder.

First, what is OHLCV data? Let's get an understanding of what data we will be storing. OHLCV data, often called candelstick data, represents the core summary statistics for an asset over a 
discrete time interval. OHLCV itself stands for 'Open', 'High', 'Low', 'Close' and 'Volume' and, by-and-large, represents the classic data needed to perform backtesting and statistical analysis
on trading ideas. KuCoin provides an additional data point beyond classic OHLCV called 'Turnover'. Turnover represents 'Close' multiplied by 'Volume', essentially indicating volume denoted in 
the trading pair's quote currency (i.e., the denominator of the pair). Below is a short summary of what each column represents:

* `Open`: Execution price of initial trade during the period.
* `High`: Highest filled trade execution price during the period.
* `Low`: Lowest filled trade execution price during the period.
* `Close`: Execution price of final trade during period.
* `Volume`: Amount of base currency exchanged.
* `Turnover`: Amount of quote currency exchanged. Turnover is equivalent to Close x Volume.

How does the `pipe` module accomplish data acquisition? KCI's `pipe` module wraps the `ohlcv` function found in the `client` module adding on top data validation features, a SQL entry point,
and robust error handling to protect against server time outs. User's are encouraged to explore `kucoincli.client.ohlcv` to get a better understanding of the data they will be acquiring.
Essentially, `pipe`'s core function of `pipeline` takes a specified timeline and asset set and repeatedly calls Kucoin's OHLCV REST endpoint while upload resulting data to a target SQL 
database.

How will tables appear in the SQL database?

Assuming a true SQL solution is in place (e.g., mySQL or Postgres), the user will need to first create the database and schema. If the database and schema already exist, users may add tables to,
or append to tables in, the pre-existing schema. Within the schema, piped data will be added, table-by-table, as each asset is iterated over. Tables will be named as all lowercase 
with special characters removed. E.g., BTC-USDT data would generate (or append to) a table titled `btcusdt` in the target schema. The resulting table will look like this:

+----------+-------+-------+-------+-------+-------------+-----------+
|   time   |  open | close |  high |  low  |   volume    | turnover  |
+==========+=======+=======+=======+=======+=============+===========+
|2022-01-01|1001.51|1002.21|1008.32| 999.43|8.14505485512| 8157.3490 |
+----------+-------+-------+-------+-------+-------------+-----------+
|2022-01-02| 999.49|1000.80|1004.89| 995.32|9.15848158419| 9153.8091 |
+----------+-------+-------+-------+-------+-------------+-----------+

If, alternatively, the user is working with a SQLite solution, the pipeline will generate a `.db` file when none exists or append to an existing `.db` file.

There is some nuance in SQL database implementation that is outside of the scope of this example. In the closing remarks below, I've linked several resources where reader's can learn more
about the differences in SQLite, Postgres, and mySQL as well as the documentation for the SQLalchemy library which acts as the interpreter between Python and a SQL database. SQLachemy is the 
ubiquitous framework for interfacing Python into SQL and as such user's will need to familiarize themselves with the tool to fully realize the benefit of this module. 

Before we jump into the code, a final note on SQL solutions: We will be covering a SQLite implementation here as it is much easier to use and setup. In reality, users with 
aspirations of working with big data will need to explore Postgres or mySQL rather than SQLite as SQLite is rather flimsy and is not a true relational database. The `pipe` module is
primarily intended to be plugged into true relational databases and may not work as efficiently, or as intended, with SQLite databases. I have had great success with Postgres (psql) in my own 
projects and encourage readers to setup their own relational database using the resources in the closing remarks *before* loading gigabytes of data onto their machine or cloud.

Without further ado, let's put together a quick and dirty example database using Kucoin-Cli and SQLite.

Step 1. Load the neccesary modules. We will be using SQLalchemy as our SQL interface and, of course, `kucoincli.pipe` as our data pipeline. We're also going to import the logging
module to give us some quick readouts as we go. For those of you that are not familiar with logging in Python, I highly recommend taking a 5 minute break to read about it `here 
<https://docs.python.org/3/howto/logging.html>`_.

.. code-block:: python

        ##### A simple data pipeline using `kucoincli.pipe` module #####

        # Import our modules
        from sqlalchemy import create_engine
        import kucoincli.pipe as pipe
        import logging


Step 2. Now that we've imported our modules, we need to establish our database connection. As previously mentioned, establishing SQL connections using SQLalchemy is out of the scope
of this documentation, but understand that we will hook into our database by creating an *engine* object using the `create_engine` function from the SQLalchemy. For greater detail on
the process read `this SQLalchemy page <https://docs.sqlalchemy.org/en/20/core/engines.html>`_. For SQLite databases, we simply pass the string `sqlite:///name_of_our_database.db` into
`create_engine`. For this example, our database name will be `example.db`, but this is, of course, arbitrary.

.. code-block:: python

        # Create our sqlite database engine with sqlalchemy.
        # The engine will generate a new database or append
        # to a pre-existing one.
        engine = create_engine("sqlite:///example.db")

Step 3. Let's get some basic logger configurations setup. I won't go into detail on how to adjust these settings as there are plenty of resources available, but understand that this is
just giving us an "under-the-hood" look at what's going on in our console. For more details see the logger documentation link above.

.. code-block:: python

        # Add a logger to see pick up some additional output info
        # To retrieve timeout messages set logging level to DEBUG
        fmt = "%(asctime)s [%(levelname)s] %(module)s :: %(message)s"
        logging.basicConfig(level=logging.INFO, format=fmt)
        logging.getLogger(__name__)

Step 4. Establish the core constants our pipeline will use. Opening a data pipeline requires five data points:

1. `ticker`: Asset of list of assets. The pipeline can take a single asset as a string or a long list of assets. In this example, we will only acquire a single asset, but, in practice, I
typically acquire price data for all traded assets. A list of all trading pairs on KuCoin can be acquires trivially using `kucoincli.symbols().index`. Note that asset names must be listed
exactly as specified by KuCoin, i.e. they must be passed with a '-' between the quote and base and in all uppercase (e.g., `BTC-USDT`).
2. `start`: The earliest date at which to acquire data e.g., `2019-01-01`. Users may pass in a time argument such as `2019-01-01 12:00:00` and can format their argument as either a string
or a datetime objects. Technically, the `start` argument is optional and, if not passed, the pipeline will automatically query all available historic data. In practice, however, specifying 
a `start` date is preferred as early days of the exchange are riddled with data inconsistency errors.
3. `end`: The latest date at which to acquire data. This is the final data or datetime in the range to be queried. User's must specify an end date and may specify it as a string or datetime
object in the same way as they specify the start argument.
4. `interval`: Specifies the granularity at which to acquire data (e.g., daily, hourly, or weekly). KuCoin provides a range of intervals: `["1min", "3min", "5min", "15min", "30min", "1hour", 
"2hour", "4hour", "6hour", "8hour", "12hour", "1day", "1week"]`. All of these intervals are fully supported by the pipeline.
5. `engine`: We need to pass the engine we created in Step 2 to the pipeline so it knows where to direct the data it acquires.

In the below code block we specify `ticker`, `start`, `end`, and `interval` as constants.

.. code-block:: python

        # Setup constants for the pipeline.
        # `pipeline`s are highly configurable 
        # Read the docs for more information
        TICKER = "BTC-USDT"
        START = "2022-04-01"
        END = "2022-05-01"
        INTERVAL = "1min"

Step 5. With our setup complete, we can call the `pipeline` function from `kucoincli.pipe`. Passing our engine object and the relevant constants, a file called `example.db` will generate in
the current working directory.

.. code-block:: python

        # Now let's open up our pipeline ...
        pipe.pipeline(
            tickers=TICKER,     # Tickers to query OHLCV data for
            engine=engine,      # Engine to run our database
            interval=INTERVAL,  # Interval at which to obtain OHLCV
            start=START,        # Earliest date to query from
            end=END,            # Latest date to query from
        )

Conclusion:

In a few simple steps, we have generated a basic SQLite database. Let's briefly review the features of the datebase: This is a SQLite `.db` file which has now been added to the current
working directory. The database contains 30 days of OHLC(V) data between April 1st, 2022 and May 1st, 2022 for Bitcoin quoted in Tether (i.e., 'BTC-USDT') at 1 minute granularity. 

The `pipeline` function gives us a handy progress bar with a timer which is especially useful when acquiring very large datasets that may take many hours or even days to download. This 
feature can, however, be disabled by setting the `progress_bar` argument equal to `False`.

We now have a permanent SQLite database to draw from for future research, but, of course, this is just the tip of the iceberg! User's will need to learn how to use SQLalchemy to retrieve
their data back into a Python environment and will need to install and setup their own relational database to begin managing larger amounts of related data. See `Further Reading` below for some
helpful documentation on your continued journey:

.. admonition:: Further Reading

    * For information on how to connect Python to your new database see the SQLalchemy documentation (https://docs.sqlalchemy.org/en/14/)
    * For a brief introduction to SQLite check out SQLite's documentation (https://www.sqlite.org/docs.html)
    * For a heavy-duty database solution check out my preferred version of SQL, Postgres (https://www.postgresql.org/docs/)

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
    # Don't do this in real code. Use python-dotenv or add the argument to PATH
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

Our strategy will generate signals and execute trades till we kill the process or until it runs into an execution error of some sort. While this strategy may not be valid, I hope it can give
you, the reader, the basic understanding of how to convert your theorized strategy into a fully automated system. Developing this library and the strategies that I am currently running has been
very meaninful to me and I hope it can be meaningful to you as well. Best of luck.

Wrapping Up
-----------


