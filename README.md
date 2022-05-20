## Kucoin-Cli: Pandas-oriented REST and Websocket API
### A data science focused Python API implementation 

<img src="https://img.shields.io/pypi/v/kucoin-cli"> <img src="https://img.shields.io/pypi/l/kucoin-cli"> <img src="https://img.shields.io/badge/Maintained-YES-green">

#### Why use this library over [python-kucoin](https://github.com/sammchardy/python-kucoin) or the [official SDK](https://github.com/Kucoin/kucoin-python-sdk)?
Both the official SDK and Samm Chardy's API implementation are stable, well-written packages with the majority of API endpoints included. Unfortunately, the SDK is fairly bare-bones without detailed error handling or out-of-the-box function features. Samm Chardy's distribution is an improvement upon the SDK, but with few frills and appears to not be maintained any longer (or at least not be maintained often). 

By contrast, this package is written specifically with efficient data acquisition in mind. Key API endpoints, such as the OHLC(V) point, are quite feature-rich and data science friendly with stable error handling implemention. This package was developed for my personal use in obtaining, analyzing, and implementing a series of ML/RL oriented arbitrage and HFT strategies. Almost all functions output nicely wrapped pandas dataframes, a fully-built data pipeline function is included for piping OHLC(V) data right into a SQL database with no-to-minimal setup, and a websocket manager is included in the dist. 

I am personally using or have used this package to:
- Automate the generation of a PSQL database with 400M+ rows of OHLC(V) data
- Implement a fully automated statistical arbitrage trading algorithm via websockets
- Feed and train ML/RL algorithms for future deployment into live trading sessions

_**Disclaimer: This is an unofficial implementation of the [KuCoin Rest and Websocket API v2](https://docs.kucoin.com/#general). Use this package at your own risk.**_

#### Roadmap
- Clean-up websocket implemention + Make client-building more out of the box
- Improvement logging across the package
- Write better docstrings and update features for lesser used functions
- Add stop-loss order capabilities
- Add schema configuration functionality to data pipeline
- Add futures API access

#### Features
- One-line database pipeline. Open a high stability pipe from kucoin's kline API endpoint to a database of your creation
  - Automatically creates database or adds to pre-existing db
  - Can handle multi-day data acqusitions sessions through dynamic timeout mechanism
- Feature rich OHLC(V) acquisition. Able to query multiple currencies simultaneously as well as obtain paganated data. 
  Outputs are wrapped into a well formatted pandas dataframe
- Access to 99%+ of REST and Websocket endpoints
- 


#### Why [KuCoin](https://www.kucoin.com/)? 
- Extremely low transactions fees (0.10% at its highest level fee schedule)
- High liquidity across coins and a wide offering shitcoins for speculation
- Frequent additions of highly speculative coins earlier than other exchanges
- Among the least regulated exchanges available
- For U.S. based customers this is one of the last remaining non-KYC truly chaotic exchanges




##### Distributions & Info:
- [Kucoin-Cli on PyPI](https://pypi.org/project/kucoin-cli/)
- [Kucoin-Cli on Github](https://github.com/jaythequant/kucoin-cli)
- [Kucoin API Documenation](https://docs.kucoin.com/#general)

##### About Me






