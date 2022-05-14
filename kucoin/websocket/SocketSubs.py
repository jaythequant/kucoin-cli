import time
import json

from ..kucoin import Client


class Subscriptions(Client):

    """Construct socket subscriptions for Kucoin websockets"""

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
