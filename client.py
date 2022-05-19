import time
import requests
import base64, hashlib, hmac
import pandas as pd
import json
import calendar
from datetime import datetime
import warnings
import logging
import sys

from kucoincli.utils._helpers import _parse_date
from kucoincli.utils._helpers import _parse_interval


class Client(object):

    """
    KuCoin REST API wrapper -> https://docs.kucoin.com/#general

    :param api_key: str (Optional) API key generated upon creation of API endpoint on
        kucoin.com. If no API key is given, the user cannot access functions requiring
        account level authorization, but can access endpoints that require general auth
        such as kline historic data.
    :param api_secret: str (Optional) Secret API sequence generated upon create of API
        endpoint on kucoin.com. See api_key param docs for info on optionality of 
        variable
    :param api_passphrase: str (Optional) User created API passphrase. Passphrase is 
        created by the user during API setup on kucoin.com. See api_key param docs for 
        info on optionality of variable
    :param sandbox: bool If sandbox = True, access a special papertrading API version
        available for testing trading. For more details visit: https://sandbox.kucoin.com/
        Be aware that (1) sandbox API key, secret, and passphrase are NOT the same as
        regular kucoin API and may only be obtained from the sandbox website and (2)
        that sandbox markets are completely seperate than kucoin's regular sites. It is
        recommended that you not use sandbox as the data is highly corrupted.
    """

    REST_API_URL = "https://api.kucoin.com"
    SAND_BOX_URL = "https://openapi-sandbox.kucoin.com"
    API_VERSION = "v1"
    API_VERSION2 = "v2"
    API_VERSION3 = "v3"

    ACCOUNT_MAIN = "main"
    ACCOUNT_TRADE = "trade"
    ACCOUNT_MARGIN = "margin"

    SIDE_BUY = "buy"
    SIDE_SELL = "sell"

    ORDER_LIMIT = "limit"
    ORDER_MARKET = "market"
    ORDER_LIMIT_STOP = "limit_stop"
    ORDER_MARKET_STOP = "market_stop"

    def __init__(self, api_key="", api_secret="", api_passphrase="", sandbox=False, requests_params=None):

        self.logger = logging.getLogger(__name__)

        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.API_PASSPHRASE = api_passphrase

        if sandbox:
            self.API_URL = self.SAND_BOX_URL
        else:
            self.API_URL = self.REST_API_URL

        # Logging setup
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(funcName)s [%(levelname)s] %(message)s",
            handlers=[
                # logging.FileHandler("log.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _compact_json_dict(self, data):
        """convert dict to compact json
        :return: str
        """
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    def _create_path(self, path, api_version=None):
        api_version = api_version or self.API_VERSION
        return f"/api/{api_version}/{path}"

    def _create_uri(self, path):
        return f"{self.API_URL}{path}"

    def _request(self, method, path, signed=False, api_version=None, data=None):

        full_path = self._create_path(path, api_version)
        uri = self._create_uri(full_path)

        if signed:
            headers = self._generate_signature(method, full_path, data)
            return uri, headers

        return uri

    def _get_params_for_sig(data):
        return "&".join([f"{key}={data[key]}" for key in data])

    def _generate_signature(self, method, url, data):

        now = int(time.time() * 1000)

        data_json = ""
        endpoint = url

        if method == "get":
            if data:
                query_string = self._get_params_for_sig(data)
                endpoint = f"{url}?{query_string}"
        elif data:
            data_json = self._compact_json_dict(data)
        str_to_sign = str(now) + method.upper() + endpoint + data_json
        signature = base64.b64encode(
            hmac.new(
                self.API_SECRET.encode("utf-8"),
                str_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        passphrase = base64.b64encode(
            hmac.new(
                self.API_SECRET.encode("utf-8"),
                self.API_PASSPHRASE.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        headers = {
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": str(now),
            "KC-API-KEY": self.API_KEY,
            "KC-API-PASSPHRASE": passphrase,
            "Content-Type": "application/json",
            "KC-API-KEY-VERSION": "2",
        }
        return headers

    def list_subusers(self):
        path = "sub/user"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        df = pd.DataFrame(response.json()["data"])
        if df.empty:
            return print("No sub-users available")
        return df

    def get_accounts(self, type=None, currency=None, balance=None):
        """
        Query Kucoin API accounts endpoint returning dataframe of 
            open accounts. Requires trade level API authentication.

        :param type: Specify accounts type to filter returned data to
            only accounts of that type. Defaults all account types.
            types: main, margin, trade
        :param currency: Specify currency account to return (e.g. BTC)
            Defaults to None which returns all currencies
        :param balance: Filter response by balance amount

        :return df: Returns pandas dataframe of accounts 
        """
        path = "accounts"
        url, headers = self._request("get", path, signed=True)
        resp = requests.request("get", url, headers=headers)
        if resp.status_code == 401:
            raise Exception(f"[{resp.status_code}] Invalid API credentials")
        df = pd.DataFrame(resp.json()["data"])
        if type: 
            df = df[df["type"] == type]
        if currency:
            df = df[df["currency"] == currency]
        if balance:
            df = df[df["balance"].astype(float) >= balance]
        if df.empty:
           raise Exception("No accounts found / no data returned.")
        return df.set_index("id")

    def get_account(self, account_id: str) -> dict:
        path = f"accounts/{account_id}"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        return response.json()["data"]

    def create_account(self, type, currency):
        """
        ## Does not work ##
        :param type: Account types are main, trade, margin
        """
        data = {type: type, currency: currency}
        path = "accounts"
        url, headers = self._request("post", path, signed=True, data=data)
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def get_total_balance(self):
        path = f"sub-accounts"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        print(response.json())
        return response.json()["data"]

    def recent_orders(self):
        path = "limit/orders"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        df = pd.DataFrame(response.json()["data"])
        if df.empty:
            print("No recent accounts open.")
            return None
        return df.set_index("id")

    def transfer_funds(self, currency, source, destination, amount, client_oid=None):
        path = "accounts/inner-transfer"
        data = {
            "currency": currency,
            "from": source,
            "to": destination,
            "amount": amount,
        }
        if client_oid:
            data["clientOid"] = client_oid
        else:
            data["clientOid"] = str(int(time.time() * 10000))
        url, headers = self._request(
            "post", path, signed=True, api_version=self.API_VERSION2, data=data
        )
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def repay_all(self, currency, priority="highest", size=None) -> dict:
        """
        API endpoint for repayment outstanding margin debt
        :param priority: str Sequence in which to repay margin debt
            Highest (default) indicates to repay highest interest rate 
            loans first, while soonest repays loans with nearest 
            maturity time.
        :param size: float Repayment size 
        :return resp: JSON dictionary response with repayment detail
        """
        ## Needs some work
        path = "margin/repay/all"
        data = {
            "currency": currency,
        }
        if priority == "highest":
            data["sequence"] = "HIGHEST_RATE_FIRST"
        if priority == "soonest":
            data["sequence"] = "RECENTLY_EXPIRE_FIRST"
        if size: 
            data["size"] = size
        url, headers = self._request(
            "post", path, signed=True, data=data
        )
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def margin_balance(self, currency=None):
        """
        Query outstanding margin balances (does not support query
            by currency yet)
        """
        path = "margin/borrow/outstanding"
        url, headers = self._request("get", path, signed=True)
        resp = requests.request("get", url, headers=headers)
        return resp.json()["data"]

    def get_kline_history(
        self, tickers, begin, end=None, interval:str="1day", msg:bool=False,
        warning:bool=True,
    ):
        """
        Query historic OHLCV data for a ticker or list of tickers from Kucoin historic 
            database. 
        
        :param tickers: str pr list Currency pair or list of pairs. Pair names must be
            formatted in upper case (e.g. ETH-BTC)
        :param begin: Can be string or datetime object. Note that server time is UTC
            String format may include hours/minutes/seconds or may not
            Examples: "YYYY-MM-DD" or "YYYY-MM-DD"
        :param end: (Optional) Can be string or datetime object with the same
            formatting rules as the begin parameter. If unspecified end will 
            default to UTC time now
        :param interval: Interval at which to return OHLCV data. Default = 1day
            Intervals: 1min, 3min, 5min, 15min, 30min, 1hour, 2hour, 4hour, 6hour, 
                8hour, 12hour, 1day, 1week
        :param progress_bar: bool Flag to enable progress bar. Does not work in 
            Jupyter notebooks yet
        :param msg: bool Flag to turn on helper messages

        :return df: Returns dataframe with datetime index
        """
        if isinstance(begin, str):
            begin = _parse_date(begin)

        if end:
            if isinstance(end, str):
                end = _parse_date(end)
        else:
            end = datetime.utcnow()

        if isinstance(tickers, str):    
            tickers = [tickers]    

        paganated_ranges = _parse_interval(begin, end, interval)
        unix_ranges = []    # This list will hold paganated unix epochs

        # Convert paganated datetime ranges to unix epochs
        for b, e in paganated_ranges:
            b = int(calendar.timegm(b.timetuple()))
            e = int(calendar.timegm(e.timetuple()))
            unix_ranges.append((b, e))

        dfs = []

        if warning:
            num_calls = len(unix_ranges) * len(tickers)
            if num_calls > 20:
                warnings.warn(f"""
                Endpoint will be queried {num_calls} times.
                    Server may require one or multiple timeouts. Set msg to true for timeout notices
                """)

        for ticker in tickers:
            paths = []
            for begin, end in unix_ranges:
                path = f"market/candles?type={interval}&symbol={ticker}&startAt={begin}&endAt={end}"
                paths.append(path)

            df_pages = []   # List for individual df returns from paganated values

            for path in paths:
                url = self._request("get", path)
                resp = requests.request("get", url)

                # Handle timeout response by sleeping function
                if resp.status_code == 200:
                    pass
                elif resp.status_code == 429:
                    if msg:
                        print("\nRate limit trigger")
                    time.sleep(11)
                    if msg:
                        print("Re-establishing stream . . . ")
                    resp = requests.request("get", url)
                    if resp.status_code == 429:
                        if msg:
                            print("\nHard reset initiated.")
                        time.sleep(180)
                        resp = requests.request("get", url)
                        if resp.status_code == 429:
                            time.sleep(300)
                            resp = requests.request("get", url)
                        else:
                            pass
                else:
                    print(f"Failed reponse. Returned code: {resp.status_code}")
                
                resp = resp.json()
                try:
                    df = pd.DataFrame(resp["data"])
                    df[0] = pd.to_datetime(df[0], unit="s", origin="unix")
                    df = df.rename(
                        columns={
                            0: "time",
                            1: "open",
                            2: "close",
                            3: "high",
                            4: "low",
                            5: "volume",
                            6: "turnover",
                        }
                    ).set_index("time")
                except KeyError:
                    # This keyerror occurs when GET request returns no data
                    df = pd.DataFrame()
                df_pages.append(df.astype(float))
            if len(df_pages) > 1:
                dfs.append(pd.concat(df_pages, axis=0))
            else:
                dfs.append(df_pages[0])
        if len(dfs) > 1:
            return pd.concat(dfs, axis=1, keys=tickers)
        else:
            return dfs[0]

    def get_order_histories(self, symbol):
        path = f"market/histories?symbol={symbol.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.json())
        resp = resp.json()
        try:
            df = pd.DataFrame(resp["data"])
        except KeyError:
            return print("No message data received.")
        df["time"] = pd.to_datetime(df["time"], origin="unix")
        df.set_index("time", inplace=True)
        return df

    def get_all_pairs(self):
        """
        Requests kucoin API for list of all symbols
        Returns dataframe with all symbol info
        """
        path = "symbols"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.status_code)
        resp = resp.json()
        df = pd.DataFrame(resp["data"])
        return df

    def get_margin_data(self, currency):
        path = f"margin/trade/last?currency={currency.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.status_code)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
        if df.empty:
            print("No data returned.")
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"], origin="unix")
        df.set_index("timestamp", inplace=True)
        return df

    def lending_rate(self, currency, term):
        path = f"margin/market?currency={currency.upper()}&term={term}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.status_code)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
        return df

    def get_marginable(self):
        path = "symbols"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.status_code)
        resp = resp.json()
        df = pd.DataFrame(resp["data"])
        marginTrue = df["isMarginEnabled"] == True
        tradingEnabled = df["enableTrading"] == True
        df = df[marginTrue & tradingEnabled]
        return df

    def get_trade_history(self, symbol):
        path = f"market/histories?symbol={symbol.upper()}"
        url = self._request("get", url)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.status_code)
        resp = resp.json()
        df = pd.DataFrame(resp["data"])
        df["time"] = pd.to_datetime(df["time"], origin="unix")
        df.set_index("time", inplace=True)
        return df

    def get_markets(self):
        path = "markets"
        url = self._request("get", path)
        resp = requests.request("get", url)
        return resp.json()["data"]

    def get_stats(self, currency):
        path = f"market/stats?symbol={currency.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        return resp

    def get_ticker(self, currency):
        path = f"market/orderbook/level1?symbol={currency.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        return resp

    def get_market_info(self):
        path = "market/allTickers"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp["tickers"])
        df["time"] = pd.to_datetime(resp["time"], unit="ms", origin="unix")
        # df.set_index("time", inplace=True)
        return df

    def get_currency_list(self):
        path = "currencies"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
        df.set_index("currency", inplace=True)
        return df

    def get_currency_detail(self, currency):
        path = f"currencies/{currency.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        return resp

    def get_full_detail(self, currency):
        ### Needs further improvement from display standpoint.
        # Chains column return is a dictionary which is not good.
        path = f"currencies/{currency.upper()}"
        url = self._request("get", path, api_version=self.API_VERSION2)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
        return df

    def get_fiat_prices(self, fiat="USD"):
        path = "prices"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame.from_dict(resp, orient="index", columns=[fiat])
        return df

    def check_marginable_currencies(self):
        df = self.get_currency_list()
        try:
            df = df[df["isMarginEnabled"] == True]
        except KeyError:
            return print("No message data received.")
        return df

    def margin_config(self):
        path = "margin/config"
        url = self._request("get", path)
        resp = requests.request("get", url)
        return resp.json()["data"]

    def get_socket_detail(self, private=False):
        if not private:
            path = "bullet-public"
            is_signed = False
            url = self._request("post", path, signed=is_signed)
            resp = requests.request("post", url)
        if private:
            path = "bullet-private"
            is_signed = True
            url, headers = self._request("post", path, signed=is_signed)
            resp = requests.request("post", url, headers=headers)
        if resp.status_code != 200:
            print(resp.status_code)
        return resp.json()["data"]

    def get_server_time(self):
        """
        Return server time (UTC) as unix timestamp
        """
        path = "timestamp"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return print(resp.status_code)
        resp = resp.json()["data"]
        return resp

    def limit_order(
        self, symbol:str, side:str, price:float, size:float=None, 
        funds:float=None, client_oid:str=None, remark:str=None, 
        tif:str="GTC", stp:str=None, cancel_after:int=None, 
        postonly:bool=False, hidden:bool=False, iceberg:bool=None, 
        visible_size:float=None,
    ):
        """"
        API command for placing limit trades in the trade account (non-margin). 

        :param symbol: Pair on which to execute trade (e.g., BTC-USDT)
        :param side: Side to execute trade on 
            Options: buy or sell
        :param price: float Trades must be executed at this price or better
        :param size: (Optional) User is required to either specify size or funds.
            Size indicates the amount of base currency to buy or sell
            Size must be above baseMinSize and below baseMaxSize
            Size must be specified in baseIncrement symbol units
            Size must be a positive float value
        :param funds: (Optional) User is required to either specify size or funds.
            Funds indicates the amount of price [quote] currency to buy or sell.
            Funds must be above quoteMinSize and below quoteMaxSize
            Size of funds must be specified in quoteIncrement symbol units
            Funds must be a positive float value
        :param client_oid: (Optional) Unique order ID for identification of orders. 
            Defaults to integer nonce based on unix epoch
        :param remark: (Optional) Add a remark to the order execution
            Remarks may not exceed 100 utf8 characters
        :param stp: (Optional) Self-trade prevention. Primarily used by market makers
            Options: CN, CO, CB, or DC 
        :param tif: Dictate time in force order types. 
            Order types: GTC [default], GTT, IOC, or FOK
        :param cancel_after: Cancel after n seconds. Requires that tif be GTT
        :param postonly: bool If postonly is true, orders may only be executed 
            at the maker fee. Orders that would receive taker will be rejected.
        :param hidden: bool Orders will appear in orderbook
        
        :return order: JSON dict with order execution details
        """
        data = {
            "symbol": symbol,
            "side": side,
            "type": self.ORDER_LIMIT,
            "price": price,
        }
        if size:
            data["size"] = size
        if funds:
            data["funds"] = funds
        if client_oid:
            data["clientOid"] = client_oid
        else:
            data["clientOid"] = str(int(time.time() * 10000))
        if remark:
            data["remark"] = remark
        if stp:
            data["stp"] = stp
        if tif:
            data["timeInForce"] = tif
        if cancel_after:
            data["cancelAfter"] = cancel_after
        if postonly:
            data["postOnly"] = postonly
        if hidden:
            data["hidden"] = hidden
        if iceberg:
            data["iceberg"] = iceberg
            data["visible_size"] = visible_size
        path = "orders"
        url, headers = self._request("post", path, signed=True, data=data)
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def market_order(
        self, symbol:str, side:str, size:float=None, funds:float=None, 
        client_oid=None, remark=None, stp=None,
    ):
        """
        API command for executing market orders in the trade account (non-margin)
        
        :param symbol: Pair on which to execute trade (e.g., BTC-USDT)
        :param side: Side to execute trade on 
            Options: buy or sell
        :param size: (Optional) User is required to either specify size or funds.
            Size indicates the amount of base currency to buy or sell
            Size must be above baseMinSize and below baseMaxSize
            Size must be specified in baseIncrement symbol units
            Size must be a positive float value
        :param funds: (Optional) User is required to either specify size or funds.
            Funds indicates the amount of price [quote] currency to buy or sell.
            Funds must be above quoteMinSize and below quoteMaxSize
            Size of funds must be specified in quoteIncrement symbol units
            Funds must be a positive float value
        :param client_oid: Unique order ID for identification of orders. Defaults to
            integer nonce based on unix epoch
        :param remark: (Optional) Add a remark to the order execution
            Remarks may not exceed 100 utf8 characters
        :param stp: (Optional) Self-trade prevention. Primarily used by market makers
            Options: CN, CO, CB, or DC 

        :return order: JSON dict with order execution details
        """

        data = {"side": side, "symbol": symbol, "type": self.ORDER_MARKET}
        if size:
            data["size"] = size
        if funds:
            data["funds"] = funds
        if client_oid:
            data["clientOid"] = client_oid
        else:
            data["clientOid"] = int(time.time() * 10000)
        if remark:
            data["remark"] = remark
        if stp:
            data["stp"] = stp
        path = "orders"
        url, headers = self._request("post", path, signed=True, data=data)
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def margin_market_order(
        self, symbol:str, side:str, size:float=None, funds:float=None, 
        client_oid:str=None, remark:str=None, stp:str=None, mode:str="cross", 
        autoborrow:bool=True,
    ):
        """
        API command for placing market trades on margin. 

        :param symbol: Pair on which to execute trade (e.g., BTC-USDT)
        :param side: Side to execute trade on 
            Options: buy or sell
        :param size: (Optional) User is required to either specify size or funds.
            Size indicates the amount of base currency to buy or sell
            Size must be above baseMinSize and below baseMaxSize
            Size must be specified in baseIncrement symbol units
            Size must be a positive float value
        :param funds: (Optional) User is required to either specify size or funds.
            Funds indicates the amount of price [quote] currency to buy or sell.
            Funds must be above quoteMinSize and below quoteMaxSize
            Size of funds must be specified in quoteIncrement symbol units
            Funds must be a positive float value
        :param client_oid: Unique order ID for identification of orders. Defaults to
            integer nonce based on unix epoch
        :param remark: (Optional) Add a remark to the order execution
            Remarks may not exceed 100 utf8 characters
        :param stp: (Optional) Self-trade prevention. Primarily used by market makers
            Options: CN, CO, CB, or DC 
        :param mode: User may trade on cross margin or isolated margin. Default = cross 
        :param autoborrow: bool If true, system will automatically borrw at the
            optimal interest rate prior to placing the requested order. 

        :return order: JSON dict with order execution details
        """

        data = {
            "side": side,
            "symbol": symbol,
            "type": self.ORDER_MARKET,
            "marginMode": mode,
            "autoBorrow": autoborrow,
        }
        if size:
            data["size"] = size
        if funds:
            data["funds"] = funds
        if client_oid:
            data["clientOid"] = client_oid
        else:
            data["clientOid"] = int(time.time() * 10000)
        if remark:
            data["remark"] = remark
        if stp:
            data["stp"] = stp
        if mode != "cross":
            data["marginMode"] = mode
        path = "margin/order"
        url, headers = self._request("post", path, signed=True, data=data)
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()


    def margin_limit_order(
        self, symbol:str, side:str, price:float, size:float=None, 
        funds:float=None, client_oid:str=None, remark:str=None, 
        stp:str=None, mode:str="cross", autoborrow:bool=True, 
        tif:str="GTC", cancel_after:int=None, postonly:bool=False, 
        hidden:bool=False, iceberg:bool=None, visible_size:float=None,
    ) -> dict: 
        """"
        API command for placing margin limit trades. 

        :param symbol: Pair on which to execute trade (e.g., BTC-USDT)
        :param side: Side to execute trade on 
            Options: buy or sell
        :param price: float Trades must be executed at this price or better
        :param size: (Optional) User is required to either specify size or funds.
            Size indicates the amount of base currency to buy or sell
            Size must be above baseMinSize and below baseMaxSize
            Size must be specified in baseIncrement symbol units
            Size must be a positive float value
        :param funds: (Optional) User is required to either specify size or funds.
            Funds indicates the amount of price [quote] currency to buy or sell.
            Funds must be above quoteMinSize and below quoteMaxSize
            Size of funds must be specified in quoteIncrement symbol units
            Funds must be a positive float value
        :param client_oid: (Optional) Unique order ID for identification of orders. 
            Defaults to integer nonce based on unix epoch
        :param remark: (Optional) Add a remark to the order execution
            Remarks may not exceed 100 utf8 characters
        :param stp: (Optional) Self-trade prevention. Primarily used by market makers
            Options: CN, CO, CB, or DC 
        :param mode: User may trade on cross margin or isolated margin. Default = cross 
        :param autoborrow: bool If true, system will automatically borrw at the
            optimal interest rate prior to placing the requested order. 
        :param tif: Dictate time in force order types. 
            Order types: GTC [default], GTT, IOC, or FOK
        :param cancel_after: Cancel after n seconds. Requires that tif be GTT
        :param postonly: bool If postonly is true, orders may only be executed 
            at the maker fee. Orders that would receive taker will be rejected.
        :param hidden: bool Orders will appear in orderbook
        
        :return order: JSON dict with order execution details
        """
        if not size and not funds:
            raise ValueError("Must specify either size or funds parameter.")
        if size and funds:
            raise ValueError("May not specify both size and funds.")

        data = {
            "side": side,
            "symbol": symbol,
            "price": price,
            "type": self.ORDER_LIMIT,
            "marginMode": mode,
            "autoBorrow": autoborrow,
        }
        if size:
            data["size"] = size
        if funds:
            data["funds"] = funds
        if client_oid:
            data["clientOid"] = client_oid
        else:
            data["clientOid"] = int(time.time() * 10_000)
        if remark:
            data["remark"] = remark
        if stp:
            data["stp"] = stp
        if mode != "cross":
            data["marginMode"] = mode
        if cancel_after and tif == "GTT":
            data["cancelAfter"] = cancel_after
        if hidden:
            data["hidden"] = hidden
        if postonly:
            data["postOnly"] = postonly
        if iceberg:
            data["iceberg"] = iceberg
            data["visible_size"] = visible_size
        path = "margin/order"
        url, headers = self._request("post", path, signed=True, data=data)
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()
