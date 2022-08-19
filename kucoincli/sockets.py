import time
import json
from pprint import pprint
from kucoincli.utils._utils import _str_to_list


class Socket(object):
    """Manage channel subscriptions for KuCoin socket connection"""

    def __init__(self, api_key=None, api_secret=None, api_passphrase=None, socket=None):
     """Manage channel subscriptions for KuCoin socket connection"""
    public = {
        "orderbook": "/market/level2:",
        "market": "/market/ticker:",
        "snapshot": "/market/snapshot:",
        "5book": "/spotMarket/level2Depth5:",
        "50book": "/spotMarket/level2Depth50:",
        "kline": "/market/candles:",
        "match": "/market/match:",
        "indicator": "/indicator/index:",
        "mark": "/indicator/markPrice:",
        "funding": "/margin/fundingBook:",
    }
    private = {
        "trades": "/spotMarket/tradeOrders",
        "balance": "/account/balance",
        "debt": "/margin/position",
        "loan": "/margin/loan:",
        "stoporder": "/spotMarket/advancedOrders",
    }
    endpoints = {**public, **private}

    def __init__(self, socket=None):
        self.socket = socket

    async def _submit_subscription(self, channels, private=False, ack=False):
        """Submit Kucoin websocket subscription requests"""
        channels = [channels] if isinstance(channels, str) else channels
        for channel in channels:
            headers = {
                "id": int(time.time() * 10_000),
                "type": "subscribe",
                "topic": channel,
                "privateChannel": private,
                "response": ack,
            }
            await self.socket.send(json.dumps(headers))
            await self.socket.recv()

    async def subscribe(
        self, channels:str or list, ticker:None or str or list=None, 
        market:None or str or list=None, currency:None or str or list=None, 
        interval:None or str=None, ack=False,
    ) -> None:
        """Select set of endpoints and submit authenticated subscriptions
        
        Parameters
        ----------
        channels : str or list
            Channel or list of channels to submit subscriptions for. Channel endpoints
            can be accessed through `.endpoint` attribute. List of channels:
            * `orderbook`: Access Level 2 orderbook updates. This will only push 
              order book updates to the user and as such it is geared towards 
              live orderbook maintenance, not obtaining bid-ask spreads. Pushes
              updates in real time.
            * `5book`: Access top 5 best bid-ask spreads for a single trading
              pair. Pushes updates at 100ms frequency.
            * `50book`: Access top 50 best bid-ask spreads for a single 
              trading pair. Pushes at 100ms frequency.
            * `kline`: Access live updates to kline data for a single trading
              pair with candles keyed to specified interval (see `interval` 
              below for valid intervals). Messages pushed on an as needed basis.
            * `trades`: [PRIVATE] Receive status update messages related to trades
              the user has placed on orderbook. Pushes whenever trade event 
              occurs.
            * `balance`: [PRIVATE] Receive status update messages whenever any
              account balance changes across the users accounts. Pushes whenever
              balanace change event occurs.
            * `debt`: [PRIVATE] Receive pings with margin debt information including
              margin balances per asset and current debt ratios. Pushes periodically
              when a margin balance is present.
            * `snapshot`: 
            * `market`: Subscribe to this channel for summary statistical information
              related to a single currency, group of currencyies or, all currencies.
              Pushes new data per trading pair every 100ms or full market currency updates 
              every 2s. Leverages `tickers` argument to obtain list of currencies to
              subscribe to for information. 
            * `indicator`: 
            * `mark`: 
            * `funding`:
            * `loan`:
            * `stoporder`:

        ticker : None or str or list, optional
            Many endpoints require the user to specify a ticker or list of
            ticker for subscription. If `ticker=None` and a channel
            does require a ticker, a `ValueError` will be raised. Note that 
            the `market` endpoint also allows for subscription to **all**
            ticker. Set `ticker="all"` or include "all" in list of ticker
            alongside a `market` channel subscription to access the all ticker
            subscription.
        market : None or str or list, optional
            Market argument only used by `snapshot` endpoint. Allows users to query 
            whole snapshots by whole market rather individual ticker. Available
            markets are `[BTC, KCS, ETH, ALT]`. Subscribe to multiple markets by 
            passing a list.
        currency : None or str or list, optional
            Some endpoints are queriable by currency rather than trading pair 
            (e.g. BTC). If a user attempts to subscribe to an endpoint that
            requires a currency specification while `currency=None`, a `ValueError`
            will be raised
        interval : None or str, optional
            Interval argument only used for `kline` endpoint. Valid intervals are:
            `["1min", "3min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", 
            "8hour", "12hour", "1day", "1week"]`
        ack : bool, optional
            If `ack=True`, the server will send an ack response confirming
            a successful subscription request. `ack=False` by default.

        Raises
        ------
        """
        if not self.socket:
            raise ValueError("Missing open socket connection")
        channels, ticker, currency, market = _str_to_list([channels, ticker, currency, market])
        if ("loan" in channels or "funding" in channels) and not currency:
            raise ValueError("One or more channels require `currency` argument")
        if "kline" in channels and not interval: 
            raise ValueError("Use of the `kline` endpoint requires `interval` argument")
        channels = {key: self.endpoints[key] for key in channels} # Pull endpoints into channels
        if ticker:
            ticker_str = ",".join(ticker).upper()
            if "all" in ticker:
                if "market" in channels:
                    channels["market"] = self.public["market"] + "all"
                ticker.remove("all")
            for key, value in channels.items(): # Extract endpoints that need tickers appended
                if value.endswith(":"):
                    channels[key] = value + ticker_str
        if "snapshot" in channels:
            if market:
                self._generate_endpoints("snapshot", market, channels)
            else:
                self._generate_endpoints("snapshot", ticker, channels)
        if "loan" in channels:
                self._generate_endpoints("loan", currency, channels)
        if "kline" in channels:
            self._generate_endpoints("kline", ticker, channels, interval)
        if "funding" in channels:
            curr_str = ",".join(currency)
            channels["funding"] = self.public["funding"] + curr_str
        private = {key: channels[key] for key in list(set(self.private).intersection(channels))}
        for key, value in channels.items():
            if "loan" in key:
                private[key] = value
        for k in private.keys():
            del channels[k]
        await self._submit_subscription(list(private.values()), private=True, ack=ack)
        await self._submit_subscription(list(channels.values()), private=False, ack=ack)

    def _generate_endpoints(self, endpoint, vars, channels, interval=None):
        """Generate series of unique endpoints on iterable"""
        for idx, var in enumerate(vars):
            if endpoint == "kline":
                channels[f"{endpoint}{idx}"] = f"{self.endpoints[endpoint]}{var}_{interval}"
            else:  
                channels[f"{endpoint}{idx}"] = f"{self.endpoints[endpoint]}{var}"
        del channels[endpoint]
