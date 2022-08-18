======================================================
Kucoin-Cli: Pandas-oriented REST and Websocket Wrapper
======================================================
A data science focused Python API implementation
------------------------------------------------

.. image:: https://img.shields.io/pypi/v/kucoin-cli.svg
    :target: https://pypi.org/project/kucoin-cli/

.. image:: https://img.shields.io/pypi/l/kucoin-cli.svg
    :target: https://pypi.org/project/kucoin-cli/

.. image:: https://img.shields.io/badge/Maintained-YES-green.svg
    :target: https://pypi.org/project/kucoin-cli/


Why use this library over `python-kucoin <https://github.com/sammchardy/python-kucoin>`_ or the `official SDK <https://github.com/Kucoin/kucoin-python-sdk>`_?
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

This package was written by a data analyst for data analysts. Specifically designed for fast, efficient data acquisition and high complexity 
trades such as HFT, market-making, and long-short strategies. Wherever possible, endpoints have been neatly wrapped to pandas Dataframes, key data 
acquisition enpoints have been thoughtfully constructed to have rich configurability reducing time needed to clean and filter data. Trading functions are
explicitly geared towards simplicity with seamless margin integration. Of special note, OHLCV acquisition from the KuCoin REST API is a has been overhauled
to enable to user to query a list of assets over any time period rather than the standard single asset with a limit of 1500 bars of historic data. For large scale
ML projects, leverage the ``kucoincli.pipe`` module for a one-line function capable of piping large amounts of OHLCV data directly into the user's SQL database structures.

* Automate the generation of a enormous SQL databases with ``kucoincli.pipe``
* Take complex trading algorithms live via websockets using ``kucoincli.socket`` [work in progress]
* Quickly obtain, clean, and organize large amounts of data for use in RL/ML models with ``kucoincli.client``

**Disclaimer: This is an unofficial implementation of the KuCoin Rest and Websocket API v2. Use this package at your own risk.**

Roadmap
+++++++
| [ ] Finish writing documentation
| [ ] Clean-up websocket implemention and improve ease of use
| [ ] Add stop-loss order capabilities
| [ ] Add schema configuration functionality to data pipeline
| [ ] Add futures API access
| [ ] Develop an asynchronous REST client

Features
++++++++
* One-line database pipeline. Open a high stability pipe from the KuCoin OHLC(V) endpoint to your SQL database

  - Automatically creates database or adds to pre-existing db
  - Capable of handling multi-day data acqusitions sessions through dynamic timeout mechanism
  - Take a look at a pre-built example in the ``examples`` folder available at `my github <https://github.com/jaythequant/kucoin-cli>`_
  
* Highly configurable data acquisitions endpoints

  - Spend less time cleaning and managing data
  - Checkout ``.ohlcv``, ``.orderbook``, ``.symbols``, and ``.all_tickers``
  
* Access to 99%+ of KuCoin REST and Websocket endpoints
* Seamless order management between Spot and Margin markets

Quickstart
++++++++++
1. Register for an account at `KuCoin <https://www.kucoin.com/>`_
2. `Generate an API <https://www.kucoin.com/account/api>`_
3. Download kucoin-cli using pip

.. code-block:: bash

    pip install kucoin-cli

4. Try out some functions! 

.. code-block:: python

  from kucoincli.client import Client

  # Your own credentials here
  api_key = 'api_key' 
  api_secret = 'api_secret' 
  api_passphrase = 'api_passphrase' 

  client = Client(api_key, api_secret, api_passphrase)

  # Pull details for all marginable currencies quoted in BTC terms
  marginable_btc_curr = client.symbols(quote="BTC", marginable=True)

  # Pull buy/sell orders for BTC-USDT
  order_df = client.get_order_histories("BTC-USDT")

  # Query one month of minutely data for BTC-USDT and ETH-USDT
  ohlcv_df = client.ohlcv(
      tickers=["BTC-USDT", "ETH-USDT"],
      begin="2022-01-01",
      end="2022-02-01",
      interval="1min",
  )

  # Buy 500 USDT of ETH on the spot market
  order = client.order(
      symbol="ETH-USDT",
      side="buy",
      price=500,
  )

  # Place a 10 minute Good-to-Time margin limit sell order for 1 BTC @ 24,000 USDT
  order = client.order(
      symbol="BTC-USDT",
      side="sell",
      price=24_000,
      size=1.0000,
      tif="GTT",
      cancel_after=600,
      margin=True,
      type="limit",
  )

  # Obtain the full orderbook depth for XRP-USDT as a namedtuple containing numpy arrays
  orderbook = client.orderbook("XRP-USDT", depth="full", format="numpy")
  
  # Specify `format="pd"` to obtain an identical result wrapped in a pandas dataframe
  orderbook = client.orderbook("XRP-USDT", depth="full", format="pd") 


Why `KuCoin <https://www.kucoin.com/>`_? 
++++++++++++++++++++++++++++++++++++++++
* **For U.S. based customers, KuCoin is one of the few non-KYC exchanges**
* Industry low transactions fees 
* High liquidity across coins and a wide offering of alts
* Frequent new coin listings
  
Consider donating:
++++++++++++++++++

| Etherium Wallet: 0x109CcCCEc0449E80336039c983e969DD23B9CE3E
| Bitcoin Wallet: 3L47AT1SoLGs65RFHYBdVmbCdtQNxZFry6

Distributions & Info:
+++++++++++++++++++++
* `KuCoin-Cli Documentation on readthedocs <https://kucoin-cli.readthedocs.io/en/latest/>`_
* `Kucoin-Cli on PyPI <https://pypi.org/project/kucoin-cli/>`_
* `Kucoin-Cli on Github <https://github.com/jaythequant/kucoin-cli>`_
* `Official Kucoin API Documenation <https://docs.kucoin.com/#general>`_
