import time
import json

from ..client import Client


class Subscriptions(Client):

    """
    Construct socket subscriptions for Kucoin websockets
    This class is temporary and will be refined in future builds of the 
    websocket functionaility. 
    """

    def __init__(self, api_key, api_secret, api_passphrase):

        super().__init__(api_key, api_secret, api_passphrase)


    def construct_socket_path(self, private=False):
        """Construct socketpath from socket detail HTTP request"""
        socket_detail = self.get_socket_detail(private=private)
        token = socket_detail["token"]
        endpoint = socket_detail["instanceServers"][0]["endpoint"]
        nonce = int(round(time.time(), 3) * 10_000)
        socket_path = endpoint + f"?token={token}" + f"&[connectId={nonce}]"
        return socket_path


    async def submit_subscription(self, socket, channel, private=False, ack=False):
        """Submit Kucoin websocket subscription request"""
        headers = {
            "id": int(time.time() * 10_000),
            "type": "subscribe",
            "topic": channel,
            "privateChannel": private,
            "response": ack,
        }
        await socket.send(json.dumps(headers))
        resp = await socket.recv()
        return resp


    def orderbook_sub(self, symbol, level=2, depth=5):
        """Build out orderbook subscriptions for various depths and book levels"""
        return f"/spotMarket/level{level}Depth{depth}:{symbol}"
    
    def margin_loan_sub(self, symbol):
        """Subscribe for currency margin updates"""
        return f"/margin/loan:{symbol}"

    def account_balance_sub(self):
        """Subscribe to account balance change updates"""
        return "/account/balance"

    def margin_position_sub(self):
        """Subscribe to receive margin balance updates"""
        return "/margin/position"

    def tradeorders_sub(self):
        """Subscribe to receive order updates"""
        return "/spotMarket/tradeOrders"

    def kline_sub(self, symbol, interval="1min"):
        """
        Subscribe for kline data
        :param symbol: Symbol formatted in uppercase (e.g., BTC-USDT)
        :param interval: Interval at which to recieve kline updates
            Options: 1min, 3min, 15min, 30min, 1hour, 2hour, 4hour, 
                6hour, 8hour, 12hour, 1day, 1week
        """
        return f"/market/candles:{symbol}_{interval}"
