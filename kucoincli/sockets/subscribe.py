import time
import json
from pprint import pprint


class Subscriptions(object):
    """Manage channel subscriptions for KuCoin socket connection"""

    def __init__(self, api_key=None, api_secret=None, api_passphrase=None, socket=None):
        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.API_PASSPHRASE = api_passphrase

        self.socket = socket

        self.increments = [
            "1min", "3min", "15min", "30min", "1hour", "2hour", 
            "4hour", "6hour", "8hour", "12hour", "1day", "1week",
        ]

        self.public = {
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

        self.private = {
            "trades": "/spotMarket/tradeOrders",
            "balance": "/account/balance",
            "debt": "/margin/position",
            "loan": "/margin/loan:",
            "stoporder": "/spotMarket/advancedOrders",
        }

    def list_public_endpoints(self):
        """Print list of all public WebSocket enpoints"""
        pprint(self.public)
    
    def list_private_endpoints(self):
        """Print list of all private WebSocket endpoints"""
        pprint(self.private)

    def list_socket_endpoints(self):
        """Print list of all WebSocket endpoints"""
        endpoints = {**self.public, **self.private}
        pprint(endpoints)

    async def _submit_subscription(self, channel, private=False, ack=False):
        """Submit Kucoin websocket subscription request"""
        headers = {
            "id": int(time.time() * 10_000),
            "type": "subscribe",
            "topic": channel,
            "privateChannel": private,
            "response": ack,
        }
        await self.socket.send(json.dumps(headers))
        resp = await self.socket.recv()
        return resp

    async def subscribe(
        self, channels:str or list, tickers:None or str or list=None, 
        market:None or str or list=None, currency:None or str or list=None, 
        interval:None or str=None, ack=False,
    ) -> None:
        """Select set of endpoints and submit authenticated subscriptions
        
        Parameters
        ----------
        channels : str or list
            Channel or list of channels on which to subscribe. For a full
            list of endpoints use `.list_all_endpoints`.
        tickers : None or str or list, optional
            Many endpoints require the user to specify a ticker or list of
            tickers for subscription. If `tickers=None` and a channel
            does require a ticker, a `ValueError` will be raised. Note that 
            the `market` endpoint also allows for subscription to **all**
            tickers. Set `tickers="all"` or include "all" in list of tickers
            alongside a `market` channel subscription to access the all ticker
            subscription.
        market : None or str or list, optional
            The `snapshot` endpoint allows users to query whole markets rather
            than single tickers. Currently available markets are `[BTC, KCS, 
            ETH, ALT]`.
        currency : None or str or list, optional
            Some endpoints are queriable by currency rather than trading pair 
            (i.e. ticker). If a user attempts to subscribe to an endpoint that
            requires a currency specification while `currency=None`, a `ValueError`
            will be raised
        interval : None or str or list, optional
            `kline` endpoint subscriptions are denoted by interval. If 
            `channel="kline"`, interval must be specified or a `ValueError` will 
            be raised.
        ack : bool, optional
            If `ack=True`, the server will send an ack response confirming
            a successful subscription request.

        Returns
        -------
        None
        """
        if not self.socket:
            raise ValueError("Missing open socket connection")
        if isinstance(channels, str):
            channels = [channels]
        if isinstance(tickers, str):
            tickers = [tickers]
        if isinstance(currency, str):
            currency = [currency]
        if isinstance(market, str):
            market = [market]
        if ("loan" in channels or "funding" in channels) and not currency:
            raise ValueError("One or more channels require `currency` argument")
        if "kline" in channels and not interval: 
            raise ValueError("Use of the `kline` endpoint requires `interval` argument")
        endpoints = {**self.public, **self.private}
        channels = {key: endpoints[key] for key in channels}
        if "all" in tickers and "market" in channels:
            channels["market"] = self.public["market"] + "all"
        if "all" in tickers:
            tickers.remove("all")
        ticker_related = {}
        for key, value in channels.items():
            if value.endswith(":"):
                ticker_related[key] = value
        if ticker_related:
            ticker_str = ",".join(tickers).upper()
            for key, value in ticker_related.items():
                channels[key] = value + ticker_str
        if "snapshot" in channels and market: 
            for idx, mark in enumerate(market):
                channels[f"snapshot{idx}"] = self.public["snapshot"] + mark
            del channels["snapshot"]
        if "snapshot" in channels and not market:
            for idx, tick in enumerate(tickers):
                channels[f"snapshot{idx}"] = self.public["snapshot"] + tick
            del channels["snapshot"]
        if "loan" in channels:
            for idx, curr in enumerate(currency):
                channels[f"loan{idx}"] = self.private["loan"] + curr
            del channels["loan"]
        if "funding" in channels:
            curr_str = ",".join(currency)
            channels["funding"] = self.public["funding"] + curr_str
        if "kline" in channels:
            for idx, ticker in enumerate(tickers):
                channels[f"kline{idx}"] = f"{self.public['kline']}{ticker}_{interval}"
            del channels["kline"]
        private = {key: channels[key] for key in list(set(self.private).intersection(channels))}
        for key, value in channels.items():
            if "loan" in key:
                private[key] = value
        for k in private.keys():
            del channels[k]
        for channel in private.values():
            print(channel)
            await self._submit_subscription(channel, private=True, ack=ack)
        for channel in channels.values():
            print(channel)
            await self._submit_subscription(channel, private=False, ack=ack)
