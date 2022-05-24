# Kucoin-Cli: Pandas-oriented REST and Websocket API _(alpha release)_
## A data science focused Python API implementation 

<img src="https://img.shields.io/pypi/v/kucoin-cli"> <img src="https://img.shields.io/pypi/l/kucoin-cli"> <img src="https://img.shields.io/badge/Maintained-YES-green">

### Why use this library over [python-kucoin](https://github.com/sammchardy/python-kucoin) or the [official SDK](https://github.com/Kucoin/kucoin-python-sdk)?
This package was written by a data analyst for data analysts. Specifically designed for fast, efficient data acquisition and high complexity trades such as HFT, market-making, and long-short strategies. Essentially all REST endpoints output to pandas Dataframes, key data acquisition functions include rich features for acquiring large amounts of historic data easily, and the trading side of the package specializes in the managment of margin where I found other packages to be lacking. Of special note, OHLC(V) acquisition from the KuCoin REST API is a bit of a bear to handle as you can only query a single ticker at a time to a max of 1500 bars. Thanks to the magic of pandas, this package has a one-liner capable of calling as many tickers or bars as desired. Perhaps best of all, the package comes with a fully-built one-line data pipeline able to create and update your very own SQL database with almost no effort. 

I have used this package to:
- Automate the generation of a PSQL database with over 400M rows of OHLC(V) data
- Take a complex statistical arbitrage trading algorithm live via websockets
- Feed and train ML/RL algorithms for future deployment into live trading sessions

_**Disclaimer: This is an unofficial implementation of the [KuCoin Rest and Websocket API v2](https://docs.kucoin.com/#general). Use this package at your own risk.**_

### Roadmap
- [ ] Clean-up websocket implemention and improve ease of use
- [ ] Improve logging across the package
- [ ] Write better docstrings and update features for lesser used functions
- [ ] Add stop-loss order capabilities
- [ ] Add schema configuration functionality to data pipeline
- [ ] Add futures API access
- [ ] Develop an asynchronous REST client

### Features
- One-line database pipeline. Open a high stability pipe from kucoin's OHLC(V) endpoint to a database of your creation
  - Automatically creates database or adds to pre-existing db
  - Can handle multi-day data acqusitions sessions through dynamic timeout mechanism
- Feature rich OHLC(V) acquisition
  - Query multiple currencies simultaneously 
  - Obtain clean pandas DataFrame output of paganated data 
- Access to 99%+ of REST and Websocket endpoints
- Fully implemented margin trading features

### Quickstart
1. Register for an account at [KuCoin](https://www.kucoin.com/)
2. [Generate an API](https://www.kucoin.com/account/api)
3. Download kucoin-cli using pip

    `pip install kucoin-cli`

4. Try out some functions! 

```
import kucoincli.client as Client

# Your own credentials here
api_key = 'api_key' 
api_secret = 'api_secret' 
api_passphrase = 'api_passphrase' 

client = Client(api_key, api_secret, api_passphrase)

# Get recent margin dataflow for Bitcoin
margin_df = client.get_margin_data("BTC")

# Pull buy/sell orders for BTC-USDT
order_df = client.get_order_histories("BTC-USDT")

# Query one month of minutely data for BTC-USDT and ETH-USDT
ohlvc_df = client.get_kline_history(
    tickers=["BTC-USDT", "ETH-USDT"],
    begin="2022-01-01",
    end="2022-02-01",
    interval="1min",
)

# Place a margin limit order to sell 1 BTC good for 10 minutes
order = client.margin_limit_order(
    symbol="BTC-USDT",
    side="sell",
    size=1.0000,
    tif="GTT",
    cancel_after=600,
)

# Buy 0.015 ETH-USDT at market price
order = client.market_order(
    symbol="ETH-USDT",
    side="buy",
    size="0.015",
)
```

#### Why [KuCoin](https://www.kucoin.com/)? 
- _**For U.S. based customer this is one of the last remaining "chaotic" exchanges**_
- Industry low transactions fees 
- High liquidity across coins and a wide offering of shitcoins
- Frequent additions of speculative coins 
- Among the least regulated exchanges

##### Distributions & Info:
- [Kucoin-Cli on PyPI](https://pypi.org/project/kucoin-cli/)
- [Kucoin-Cli on Github](https://github.com/jaythequant/kucoin-cli)
- [Kucoin API Documenation](https://docs.kucoin.com/#general)

##### Consider donating:
- Etherium Wallet: 0x109CcCCEc0449E80336039c983e969DD23B9CE3E
- Bitcoin Wallet: 3L47AT1SoLGs65RFHYBdVmbCdtQNxZFry6
