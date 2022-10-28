import time
import requests
import base64, hashlib, hmac
import json
import math
import calendar
import warnings
import logging
import functools
import numpy as np
import pandas as pd
import datetime as dt
import timedelta as td
from collections import namedtuple
from kucoincli.utils._utils import _parse_date
from kucoincli.utils._utils import _parse_interval
from kucoincli.utils._kucoinexceptions import KucoinResponseError
from kucoincli.sockets import Socket


class BaseClient(Socket):

    REST_API_URL = "https://api.kucoin.com"
    SAND_BOX_URL = "https://openapi-sandbox.kucoin.com"
    API_VERSION = "v1"
    API_VERSION2 = "v2"
    API_VERSION3 = "v3"
    BACKOFF = 3
    RETRIES = 1
    MAX_RECURSION = 7

    def __init__(self, api_key=None, api_secret=None, api_passphrase=None, sandbox=False):

        Socket.__init__(self)

        self.logger = logging.getLogger(__name__)

        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.API_PASSPHRASE = api_passphrase

        if sandbox:
            self.API_URL = self.SAND_BOX_URL
        else:
            self.API_URL = self.REST_API_URL

        self.session = self._session()

    def _session(self):
        pass

    def _compact_json_dict(self, data:dict):
        """Convert dict to compact json"""
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    def _create_path(self, path, api_version=None):
        """Create path with endpoint and api version"""
        api_version = api_version or self.API_VERSION
        return f"/api/{api_version}/{path}"

    def _create_uri(self, path):
        """Convert path to URI via API URL and full path"""
        return f"{self.API_URL}{path}"

    def _request(self, method, path, signed=False, api_version=None, data=None):
        """Construct final get/post request"""
        full_path = self._create_path(path, api_version)
        uri = self._create_uri(full_path)

        if signed:
            headers = self._generate_signature(method, full_path, data)
            self.session.headers.update(headers)

        if signed and method != "get" and data:
            payload = self._compact_json_dict(data)
        else:
            payload = None

        try:
            response = self.session.request(method, uri, data=payload)
        except requests.exceptions.ConnectionError:
            # Error is raised when session idles for to long (typically only on macOS)
            response = self.session.request(method, uri, data=payload)
        except requests.exceptions.ReadTimeout:
            # Error is raised during extended scraping sessions (requires long time out)
            time.time(600)
            response = self.session.request(method, uri, data=payload)

        if response.status_code == 200:
            pass
        elif response.status_code == 429:
            # Exponential backoff to handle server timeouts
            while self.RETRIES < self.MAX_RECURSION:
                logging.debug(f"Server timeout hit. Timeout for {self.BACKOFF ** self.RETRIES} seconds.")
                response = self.session.request(method, uri, data=payload)
                if response.status_code == 200:
                    break
                else:
                    self.RETRIES += 1
                    time.sleep(self.BACKOFF ** self.RETRIES)
            if self.RETRIES == self.MAX_RECURSION:
                    self.RETRIES = 1
                    raise KucoinResponseError("Max recursion depth exceeded. Server response not received")
        elif response.status_code == 401:
            logging.info(response.json())
            raise KucoinResponseError("Invalid API Credentials")
        else:
            logging.info(response.json())
            raise KucoinResponseError(f"Response Error Code: <{response.status_code}>")

        self.RETRIES = 1
        return response.json()


    def _get_params_for_sig(data):
        """Construct params for trade authentication signature"""
        return "&".join([f"{key}={data[key]}" for key in data])

    def _generate_signature(self, method, url, data):
        """Generate unique signature for trade authorization"""
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


class Client(BaseClient):

    """KuCoin REST API wrapper -> https://docs.kucoin.com/#general

    Parameters
    ----------
    api_key : str, optional
        API key generated upon creation of API endpoint on kucoin.com. If no API key is given,
        the user cannot access functions requiring account level authorization, but can access
        endpoints that require general auth such as general market data.
    api_secret : str, optional
        Secret API sequence generated upon create of API endpoint on kucoin.com. 
        See api_key docs for info on optionality of 
        variable
    api_passphrase : str, optional
        User created API passphrase. Passphrase is created by the user during API setup on 
        kucoin.com. See api_key docs for info on optionality of variable
    sandbox : bool 
        If `sandbox=True`, access a special papertrading API version available for testing
        trading. For more details visit: https://sandbox.kucoin.com/.
    """

    REST_API_URL = "https://api.kucoin.com"
    SAND_BOX_URL = "https://openapi-sandbox.kucoin.com"
    API_VERSION = "v1"
    API_VERSION2 = "v2"
    API_VERSION3 = "v3"

    def __init__(self, api_key=None, api_secret=None, api_passphrase=None, sandbox=False, requests_params=None):

        BaseClient.__init__(self, api_key, api_secret, api_passphrase)

        self.logger = logging.getLogger(__name__)

        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.API_PASSPHRASE = api_passphrase

        if sandbox:
            self.API_URL = self.SAND_BOX_URL
        else:
            self.API_URL = self.REST_API_URL

        self.session = self._session()

    def _session(self) -> requests.sessions.Session:
        session = requests.Session()
        headers = {
            "Accept": "application/json",
            "User-Agent": "kucoin-cli",
            "Content-Type": "application/json",
        }
        session.headers.update(headers)
        # Shim to add default timeout value to get/post requests
        session.request = functools.partial(session.request, timeout=10)
        return session

    def subusers(self) -> pd.DataFrame:
        """Obtain a list of sub-users"""
        # Is this redundant to get_sub_accounts?
        path = "sub/user"
        resp = self._request("get", path, signed=True)
        df = pd.DataFrame(resp["data"])
        if df.empty:
            raise KucoinResponseError("No sub-users found")
        return df

    def accounts(
        self, currency:str or list=None, type:str or list=None, balance:float=None, id:str=None,
    ) -> pd.DataFrame or pd.Series:
        """Query API for open accounts filterd by type, currency or balance.

        Parameters
        ----------        
        type : str
            Specify account type to restrict returned accounts to only that type
            Defaults all account types. Options include: main, margin, trade.
        currency : str
            Specify currency (e.g. BTC) to restrict returned accounts to only that currency 
            Defaults to None which returns all currencies.
        balance : float 
            Specify float value to restrict returns to only accounts with => values.
        id : str
            Specify ID# to query an explicit accounts.

        Returns
        -------
        DataFrame
            Returns pandas dataframe with account details.
        """
        path = "accounts"
        if id:
            path = path + f"/{id}"
        resp = self._request("get", path, signed=True)
        # resp = self.session.request("get", url)
        try:
            if id:
                df = pd.Series(resp["data"])
            else:
                df = pd.DataFrame(resp["data"])
        except:
            raise Exception(resp) # Handle no data keyerror
        df[["balance", "available", "holds"]] = df[["balance", "available", "holds"]].astype(float)
        if type:
            type = [type] if isinstance(type, str) else type
            df = df[df["type"].isin(type)]
        if currency:
            currency = [currency] if isinstance(currency, str) else type
            currency = [curr.upper() for curr in currency]
            df = df[df["currency"].isin(currency)]
        if balance:
            df = df[df["balance"] >= balance]
        if df.empty:
           raise KucoinResponseError("No accounts found / no data returned.")
        if not id:
            df.set_index("id")
        return df

    def create_account(self, currency:str, type:str) -> dict:
        """Create a new account of type `type` for currency `currency`.

        Parameters
        ----------
        currency : str 
            Currency account type to create (e.g., BTC).
        type: str 
            Type of account to create. Available account types: `['main', 'trade', 'margin']`

        Returns
        -------
        dict
            JSON dictionary with confirmation message and new account ID.
        """
        data = {"type": type, "currency": currency}
        path = "accounts"
        resp = self._request("post", path, signed=True, data=data)
        return resp

    def get_sub_accounts(self, id:str=None) -> dict:
        """Returns account details for all sub-accounts. Requires Trade authorization"""
        path = f"sub-accounts" if not id else f"path/{id}"
        resp = self._request("get", path, signed=True)
        if not resp['data']:
            raise KucoinResponseError("No sub-accounts found")
        return resp

    def account_ledgers(self):
        """Obtain deposit and withdrawal history for all accounts"""
        pass

    def user_info(self) -> dict:
        """Obtain user info including number of subaccounts and trading level"""
        path = "user-info"
        resp = self._request("get", path, signed=True)
        return resp

    def recent_orders(self, id:str=None, unix:bool=False, page:int=1, pagesize:int=500) -> pd.DataFrame:
        """Returns DataFrame with details of all trades placed in last 24 hours.

        Notes
        -----
        - Max trades per page is 500; Min trades per page is 10
        - Max number of trades returned (across all pages) is 1000
        - Data is paganated into n pages displaying `pagesize` number of trades

        Parameters
        ----------
        id : str, optional
            Specify an explicit order ID to return values for only that order
        unix : bool, optional
            If `unix=False` [default], return datetime values as datetime objects.
            If `unix=True`, return datetime as unix epochs at millisecond precision.
        page : int 
            (Optional) JSON response is paganated. Use this variable
            to control the page number viewed. Default value returns first 
            page of paganated data.
        pagesize : int 
            (Optional) Max number of trades to display per response
            Default `pagesize` is 500.
        
        Returns
        -------
        DataFrame or Series
            Returns pandas DataFrame with complete list of trade details or if a single
            order ID was specified return a pandas Series with only that trade's details

        See Also
        --------
        `order_history`: Obtain comprehensive list of past orders
        `pull_by_cid`: Pull single trade by KuCoin-generated tradeId.
        `pull_by_oid`: Pull single trade by user-generated orderId.
        """
        path = f"limit/orders?currentPage={page}&pageSize={pagesize}"
        if id:
            path = f"orders/{id}"
        resp = self._request("get", path, signed=True)
        resp = resp["data"]
        if not resp:
            raise KucoinResponseError("No orders in the last 24 hours or order ID not found.")
        if not id:
            df = pd.DataFrame(resp).squeeze()
            if not unix:
                df["createdAt"] = pd.to_datetime(df["createdAt"], unit="ms")
                df = df.set_index("createdAt")
        else:
            df = pd.Series(resp)
            if not unix:
                df.createdAt = pd.to_datetime(df.createdAt, unit="ms")
        return df

    def transfer(
        self, currency:str, source_acc:str, dest_acc:str, amount:float, oid:str=None,
        from_pair:str=None, to_pair:str=None,
    ) -> dict:
        """Function for transferring funds between cross, isolated, trade, and main accounts.

        Parameters
        ----------
        currency : str
            Currency to transfer between accounts (e.g., BTC).
        source_acc : str
            Source account type. Current options: `['main', 'spot', 'cross', 'isolated']`.
            'trade' is synonymous with 'spot'. 'margin' is synonymous with 'cross'.
        dest_acc : str 
            Destination account type. Options are: `['main', 'spot', 'cross', 'isolated']`.
            'trade' is synonymous with 'spot'. 'margin' is synonymous with 'cross'.
        amount : float
            Currency amount to transfer. Must be of the transfer currency precision.
        oid : str, optional
            Unique order ID for identification of transfer. OID will autogenerate
            if not provided.
        from_pair : str, optional
            Specify trading pair (e.g., BTC-USDT) to transfer assets from. Only required 
            when `source_acc='isolated'`.
        to_pair : str, optional
            Specify trading pair (e.g., BTC-USDT) to transfer assets to. Only required
            when `dest_acc='isolated'`.
        
        Returns
        -------
        dict
            JSON dictionary with transfer confirmtion and details.
        """
        path = "accounts/inner-transfer"
        if source_acc == 'spot': 
            source_acc = 'trade'
        if dest_acc == 'spot': 
            dest_acc = 'trade'
        if source_acc == 'cross':
            source_acc = 'margin'
        if dest_acc == 'cross':
            dest_acc == 'margin'
        data = {
            "currency": currency,
            "from": source_acc,
            "to": dest_acc,
            "amount": amount,
        }
        if oid:
            data["clientOid"] = oid
        else:
            data["clientOid"] = str(int(time.time() * 10000))
        if source_acc == 'isolated':
            if not from_pair:
                raise ValueError('Must specify `from_pair` when transfering from isolated')
            data['fromTag'] = from_pair.upper()
        if dest_acc == 'isolated':
            if not to_pair:
                raise ValueError('Must specify `to_pair` when transfering to isolated')
            data['toTag'] = to_pair.upper()
        resp = self._request(
            "post", path, signed=True, api_version=self.API_VERSION2, data=data
        )
        return resp

    def ohlcv(
        self, tickers:str or list, start:dt.datetime or str, end:dt.datetime or str=None, 
        interval:str="1day", ascending:bool=True, warning:bool=True,
    ) -> pd.DataFrame:
        """Query historic OHLC(V) data for a ticker or list of tickers 

        Parameters
        ----------
        tickers : str or list
            Currency pair or list of pairs. Pair names must be formatted in upper 
            case (e.g. ETH-BTC)
        start : str or datetime.datetime
            Earliest time for queried date range. May be given either as a datetime object
            or string. String format may include hours/minutes/seconds or may not
            String format examples: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
        end : None or str or datetime.datetime, optional
            (Optional) Ending date for queried date range. This parameter has the same
            formatting rules and flexibility of param `begin`. If left unspecified, end 
            will default to the current UTC date and time stamp.
        interval : str, optional
            Interval at which to return OHLCV data. Intervals: `["1min", "3min", "5min",
            "15min", "30min", "1hour", "2hour", "4hour", "6hour", "8hour", "12hour", "1day",
            "1week"]`. Default=1day
        ascending : bool, optional
            If `ascending=True`, dataframe will be returned in standard order. If `False`,
            return data in reverse chronological.
        warning : bool, optiona
            Toggle whether function warns user about excessive API calls

        Returns
        -------
        DataFrame
            Returns pandas Dataframe indexed to datetime

        Notes
        -----
            Server time reported in UTC
        """
        if isinstance(start, str):
            start = _parse_date(start)

        if end:
            if isinstance(end, str):
                end = _parse_date(end)
        else:
            end = dt.datetime.utcnow()

        if isinstance(tickers, str):    
            tickers = [tickers]
        tickers = [ticker.upper() for ticker in tickers]

        paganated_ranges = _parse_interval(start, end, interval)
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
                    Server may require one or multiple timeouts
                """)

        for ticker in tickers:
            paths = []
            for start, end in unix_ranges:
                path = f"market/candles?type={interval}&symbol={ticker}&startAt={start}&endAt={end}"
                paths.append(path)

            df_pages = []   # List for individual df returns from paganated values
            for path in paths:
                resp = self._request("get", path)
                if resp["code"] == '400100': # Handle invalid trading pair response
                    raise KucoinResponseError(f"Pair not recognized. Is {ticker} a valid trading pair?")
                # If we receive a valid response code, but no data, then we have reached the end of the timeseries
                if resp["code"] == '200000' and not resp["data"]:
                    break
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
                df_pages.append(df.astype(float))
            if len(df_pages) > 1:
                dfs.append(pd.concat(df_pages, axis=0))
            else:
                try:
                    dfs.append(df_pages[0])
                except IndexError:
                    logging.debug("Valid ticker, but no price data available for this period.")
                    dfs.append(pd.DataFrame())
        if len(dfs) > 1:
            return pd.concat(dfs, axis=1, keys=tickers).sort_index(ascending=ascending)
        else:
            return dfs[0].sort_index(ascending=ascending)

    def symbols(
        self, pair:str or list or None=None, market:str or list or None=None, 
        marginable:bool=None, quote:str or list or None=None,
        base:str or list or None=None, tradable:bool=None,
    ) -> pd.DataFrame or pd.Series:
        """Highly configurable query for detailed list of currency pairs

        Primary trading pair detail endpoint for users. This function will return an outline of 
        trading details for all pairs on the KuCoin platform. This function is highly configurable
        accepting several filtering arguments to return a more focused look at the market.
        
        Parameters
        ----------
        currency : str or list, optional
            Specify a single pair or list of pairs to query. If `currency=None`, return 
            all trading pairs
        market : str or list, optional
            Filter response by trading market. If `market=None` return all markets. Markets:
            `['ALTS', 'BTC', 'DeFi', 'NFT', 'USDS', 'KCS', 'Polkadot', 'ETF', 'FIAT']`
        base : str or list, optional
            Specify explicit base currency or list of currencies. If `base_curr=None` 
            [DEFAULT], all base currencies will be returned.
        quote : str or list, optional
            Specify explicit quote currency or list of quote currencies. If `quote_curr=None` 
            [DEFAULT], all quote currencies will be returned.
        marginable : bool, optional
            If `marginable=True`, return only marginable securities. If `marginable=False` return only
            securities which cannot be traded on margin. If `marginable=None` [DEFAULT] return all
            trading pairs regardless of marginability.
        tradable : bool, optional
            If `tradable=True`, return trading-enabled securities. If `trading=False` return untradable
            listed pairs. If `tradable=None` [DEFAULT], return all securites regardless of tradability.

        Returns
        -------
        DataFrame or Series
            Returns pandas DataFrame with with detailed list of all traded pairs. 
            If a list of pairs is provided in the `currency` parameter, return a
            DataFrame containing only the specified pairs. If a single pair is 
            provided, return a pandas Series with the pair trade details.

        
        See Also
        -----
        There are several other currency detail endpoints: 
        * `.get_currency_detail`
        * `.all_tickers`
        * `.get_marginable_details`
        """
        path = "symbols"
        resp = self._request("get", path)
        df = pd.DataFrame(resp["data"]).set_index("symbol")
        if pair:
            try:
                pair = [pair] if isinstance(pair, str) else pair
                pair = [symbol.upper() for symbol in pair]
                df = df.loc[pair, :]            
            except KeyError as e:
                raise KeyError("Keys not found in response data", e)
        if marginable is not None:
            df = df[df["isMarginEnabled"] == marginable]
        if market is not None:
            market = [market] if isinstance(market, str) else market
            df = df[df["market"].isin(market)]
        if base is not None:
            base = [base] if isinstance(base, str) else base
            df = df[df["baseCurrency"].isin(base)]
        if quote is not None:
            quote = [quote] if isinstance(quote, str) else quote
            df = df[df["quoteCurrency"].isin(quote)]
        if tradable is not None:
            df[df["enableTrading"] == tradable]
        return df.squeeze()

    def get_margin_data(self, currency:str) -> pd.DataFrame:
        """Query API for the last 300 fills in the lending and borrowing market 
        
        Notes
        -----
            Response sorted descending on execution time
        
        Parameters
        ----------
        currency : str 
            Target currency to pull lending/borrowing data (e.g., BTC)

        Returns
        -------
        DataFrame
            pandas DataFrame containing most recent 300 lending/borrowing rate details
        """
        path = f"margin/trade/last?currency={currency.upper()}"
        resp = self._request("get", path)
        df = pd.DataFrame(resp["data"])
        if df.empty:
            raise KucoinResponseError("No data returned.")
        df["timestamp"] = pd.to_datetime(df["timestamp"], origin="unix")
        df.set_index("timestamp", inplace=True)
        return df

    def lending_rate(self, currency:str, term:int=None, maxrate:float=None) -> pd.DataFrame:
        """Query API to obtain current a list of available margin terms

        Parameters
        ----------
        currency : str
            Target currency to pull lending rates on (e.g., BTC)
        term : int, optional
            Specify term details 
        
        Returns
        -------
        DataFrame
            Returns pandas DataFrame containing margin rate details.
        """
        path = f"margin/market?currency={currency.upper()}"
        if term:
            path = path + f"&term={term}"
        resp = self._request("get", path)
        df = pd.DataFrame(resp["data"])
        if df.empty:
            err_msg = f"No results for {currency} returned"
            if term:
                err_msg += f" @ {term} day term"
            raise KucoinResponseError(err_msg)
        return df.astype(float)

    def get_trade_history(self, pair:str, ascending:bool=False) -> pd.DataFrame:
        """Query API for most recent 100 filled trades for target pair

        Parameters
        ----------
        pair : str 
            Target currency pair to query (e.g., BTC-USDT)
        ascending : bool, optional
            Control sort order of returned DataFrame (default order Newest -> Oldest)
        
        Returns
        -------
        DataFrame
            Returns pandas Dataframe with filled trade details keyed to timestamp
        """
        path = f"market/histories?symbol={pair.upper()}"
        resp = self._request("get", path)
        try:
            df = pd.DataFrame(resp["data"])
        except KeyError:
            return KucoinResponseError(f"No trade history received. Is {pair} a valid trading pair?")
        df["time"] = pd.to_datetime(df["time"], origin="unix")
        df.set_index("time", inplace=True)
        return df.sort_index(ascending=ascending)

    def get_markets(self) -> list:
        """Returns list of markets on KuCoin
        
        Returns
        -------
        list
            Returns list of all KuCoin markets (i.e., NFT)
        """
        path = "markets"
        resp = self._request("get", path)
        return resp["data"]

    def margin_account(
        self, asset:str or list=None, balance:float=None, mode:str="cross",
    ) -> pd.DataFrame or pd.Series:
        """Return cross margin account details

        Parameters
        ----------
        asset : None or str or list, optional
            Specify a currency or list of currencies and return only margin account
            balance information for those assets. Note that cross margin and isolated 
            margin require different assets specifications. Cross margin use currency
            (e.g. BTC) while for isolated margin use trading pair (e.g. BTC-USDT)
        balance : None or float, optional
            Control minimum balance required to include asset in return
            values. Cannot be used with isolated margin as of yet.
        mode : str, optional
            Toggle between isolated and cross margin mode by setting `mode="cross"` 
            [DEFAULT] or `mode="isolated"`
        
        Returns
        -------
        DataFrame or Series
            Returns a DataFrame or Series containing margin account balance
            details for all available marginable assets in the user's cross or
            isolated margin accounts.
        """
        if mode == "cross":
            path = "margin/account"
            resp = self._request("get", path, signed=True)
            df = pd.DataFrame(resp["data"]["accounts"]).set_index("currency")
            df = df.astype(float)
            df = df.sort_values("totalBalance", ascending=False)
        if mode == "isolated":
            path = "isolated/accounts"
            resp = self._request("get", path, signed=True)
            df = pd.DataFrame(resp["data"]["assets"]).set_index("symbol")
            base = pd.DataFrame(df["baseAsset"].to_dict()).T
            quote = pd.DataFrame(df["quoteAsset"].to_dict()).T
            df = pd.concat(
                [df.iloc[:, 0:2], base, quote], axis=1, keys=["Pair", "Base", "Quote"]
            )
            df.sort_values(by=[("Pair", "debtRatio")], ascending=False)
        if asset:
            if isinstance(asset, str):
                asset = [asset]
            asset = [a.upper() for a in asset]
            try:
                df = df.loc[asset]
            except KeyError:
                raise KeyError("Asset not found in marginable index")
        if balance is not None:
            if mode == "cross":
                df = df[df["totalBalance"] > balance]
                if df.empty:
                    raise KeyError(
                    f"No accounts with balance greater than {balance}"
                )
            else:
                warnings.warn("Isolated margin cannot be filtered by `balance` yet.")
        return df.squeeze()

    def get_stats(self, pair:str) -> pd.Series:
        """Query API for OHLC(V) figures and assorted statistics on specified pair

        Parameters
        ----------
        pair : str 
            Pair to obtain details for (e.g., BTC-USDT)
        
        Returns
        -------
        pd.Series
            Returns pandas Series containing details for target currency
        """
        path = f"market/stats?symbol={pair.upper()}"
        resp = self._request("get", path)
        ser =  pd.Series(resp["data"])
        ser.iloc[2:] = ser.iloc[2:].astype(float)
        return ser

    def get_fee_rate(self, currency:str or list or None=None, type:str="crypto") -> dict:
        """Get the base fee for users in either crypto or fiat terms"""
        if not currency:
            if type == "crypto":
                path = "base-fee?currencyType=0"
            if type == "fiat":
                path = "base-fee?currencyType=1"
        if currency:
            if isinstance(currency, str):
                currency = [currency]
            if len(currency) > 10:
                raise ValueError("This endpoint is limited to 10 currencies per call.")
            curr_str = ",".join(currency)
            path = f"trade-fees?symbols={curr_str}"
        resp = self._request("get", path, signed=True)
        if not currency:
            return {f"{type.title()} Base Rate": resp}
        return resp["data"]

    def get_level1_orderbook(self, pair:str, unix=True) -> pd.Series or pd.DataFrame:
        """Obtain best bid-ask spread details for a specified pair"""
        path = f"market/orderbook/level1?symbol={pair.upper()}"
        resp = self._request("get", path)
        resp = resp["data"]
        if resp is None:
            raise KucoinResponseError("No data returned for pair.")
        ser = pd.Series(resp, name=pair).astype(float)
        if not unix:
            ser.loc["time"] = pd.to_datetime(
                dt.datetime.utcfromtimestamp(
                    ser.loc["time"] / 1000
                ).strftime('%Y-%m-%d %H:%M:%S')
            )
        return ser

    def orderbook(
        self, pair:str, depth:int or str or None=100, format="df"
    ) -> dict or pd.DataFrame or namedtuple:
        """Query full or partial orderbook for target pair

        Query KuCoin's orderbook for a specific currency with a variety of 
        depth and format parameters. Note that orderbook historic information 
        cannot be queried. 

        Parameters
        ----------
        pair : str
            Target currency whose orderbook will be obtained (e.g., "BTC-USDT")
        depth : int or str or None, optional
            Specify orderbook depth as integer or as `None` or `full`. Be aware 
            that orderbook depths above 100 will require API keys with general 
            privelege or greater. Default = 100.
        format : str, optional
            Dictate data structure output. `format` options include
            * `df` and `dataframe`: Return a formatted dataframe.
            * `raw`: Return unaltered dictionary containing full JSON response. Note 
              that `raw` only returns exactly the best 100 bid-asks spreads or 
              the entire orderbook. If `depth <= 100`, `format=raw` will return the 
              100 best spreads. If `depth > 100` or `depth=None or full`, the entire
              orderbook will be returned.
            * `np` and `numpy`: Return a `namedtuple` with NumPy datastructures. See 
              ``Returns`` sections for explanation of namedtuple data struct.

        Returns
        -------
        dict or DataFrame or namedtuple
            * `format=raw`: Return a json dictionary containing either the 100 best
              bid-ask spreads or the full orderbook. If depth < 100, return the 100 best
              else return the full orderbook.
            * `format=df or dataframe`: Return a pandas DataFrame with multiIndex on
              rows and columns. Column multiIndex shows Bid and Ask at level 0 and 
              `price` corresponding to bid-ask price, `offer` corresponding to total
              price currency the given price, and `value` corresponding to total base 
              currency availabe at the given price and offer levels (value= price * offer).
            * `format=np or numpy`: Return a namedtuple containing the following price data:
                * `namedtuple.asset`: String value of asset to which the orderbook belongs
                * `namedtuple.time`: Unix-epoch time value (at microsecond level)
                * `namedtuple.bids`: [N x 2] NumPy array with bid prices in column 0, offer
                  amounts in column 1, and sequence in column 2.
                * `numedtuple.asks`: [N x 3] NumPy array with ask prices in column 0, offer
                  amounts in column 1, and sequence in column 2.
        
        Notes
        -----
        Obtaining depth size greater than 100 or the full orderbook requires API keys with 
        at least general access.

        Full orderbook bid-ask depth will almost never be equivalent. This creates NaN
        values in dataframe returns when `format=df or dataframe` and `depth=None or "full"`.

        Strict controls are placed on full orderbook API queries and timeouts will be 
        enforced if queried more than 30 times/3s. For a guide on maintaining live
        orderbooks, see https://docs.kucoin.com/#level-2-market-data.

        Raises
        ------
        KucoinResponseError
            If HTTP response does not equal 200 or the reponse equals 200, but no data is
            returned in the JSON object. Common cause of 400 response is invalid API 
            credentials
        """
        if isinstance(depth, str) or not depth:
            path = f"market/orderbook/level2?symbol={pair.upper()}"
            resp = self._request(
                "get", path, api_version=self.API_VERSION3, signed=True
            )
        if isinstance(depth, int):
            if depth <= 100:
                path = f"market/orderbook/level2_100?symbol={pair.upper()}"
                resp = self._request("get", path)
            else:
                path = f"market/orderbook/level2?symbol={pair.upper()}"
                resp = self._request(
                    "get", path, api_version=self.API_VERSION3, signed=True
                )
        # Sometimes the request is valid, but no data is returned. If this is the case then
        # `time` will be 0.
        if resp["data"]["time"] == 0:
            raise KucoinResponseError(f"Empty data returned. Is {pair} a valid trading pair?")
        if format == "raw":
            return resp
        if format == "df" or format == "dataframe":
            fmt = "%Y-%m-%d %H:%M:%S"
            t = resp["data"]["time"]
            t = pd.to_datetime(dt.datetime.utcfromtimestamp(t / 1000).strftime(fmt))
            bids = np.array(resp["data"]["bids"], dtype=float)
            asks = np.array(resp["data"]["asks"], dtype=float)
            if isinstance(depth, int):
                bids = pd.DataFrame(bids[:depth, :], columns=["price", "offer"])
                asks = pd.DataFrame(asks[:depth, :], columns=["price", "offer"])
            if isinstance(depth, str) or not depth:
                bids = pd.DataFrame(bids, columns=["price", "offer"])
                asks = pd.DataFrame(asks, columns=["price", "offer"])
            bids["value"] = bids["price"].astype(float) * bids["offer"].astype(float)
            asks["value"] = asks["price"].astype(float) * asks["offer"].astype(float)
            df = pd.concat([bids, asks], keys=["Bids", "Asks"], axis=1)
            df.index = df.index + 1
            df = pd.concat({t: df}, names=["time", "depth"]).astype(float)
            return df
        if format == "numpy" or format == "np":
            orderbook = namedtuple("orderbook",("asset", "time", "bids", "asks"))
            sequence = float(resp["data"]["sequence"])
            orderbook.bids = np.array(resp["data"]["bids"], dtype=float)
            orderbook.asks = np.array(resp["data"]["asks"], dtype=float)
            bidseq = np.full((orderbook.bids.shape[0],1), sequence, dtype=float)
            askseq = np.full((orderbook.asks.shape[0],1), sequence, dtype=float)
            orderbook.bids = np.hstack((orderbook.bids, bidseq))
            orderbook.asks = np.hstack((orderbook.asks, askseq))
            orderbook.time = float(resp["data"]["time"])
            orderbook.asset = pair
            if isinstance(depth, int):
                orderbook.bids = orderbook.bids[:depth, :]
                orderbook.asks = orderbook.asks[:depth, :]
            return orderbook

    def all_tickers(self, pair:str or list or None=None, quote:str or list or None=None) -> pd.DataFrame:
        """Query entire market for 24h trading statistics

        Parameters
        ----------
        pair : str or list or None, optional
            Filter trading pairs by specific currency or list or currencies
        quote : str or list or None, optional
            Filter trading currencies by quote currency (right side of trading pair)

        Returns
        -------
        DataFrame or Series
            Returns pandas DataFrame or Series containing recent trade data for entire market or
            if `pair` or `quote` is specified, a subset of the market.
        """
        path = "market/allTickers"
        resp = self._request("get", path)
        df = pd.DataFrame(resp["data"]["ticker"]).drop("symbolName", axis=1)
        df.set_index("symbol", inplace=True)
        if pair:
            pair = [pair] if isinstance(pair, str) else pair
            df = df[df.index.isin(pair)]
        if quote is not None:
            quote = [quote] if isinstance(quote, str) else quote
            quote_currs = df.index.str.split("-", expand=True).get_level_values(level=1)
            mask = quote_currs.isin(quote)
            df = df[mask]
        return df.squeeze()

    def get_currency_detail(self, currency:str or None=None) -> pd.Series or pd.DataFrame:
        """Query API for currency or list of currencies including precision and marginability
        
        Parameters
        ----------
        currency : str or None, optional
            Target currency to obtain details (e.g. BTC)

        Returns
        -------
        pd.Series or DataFrame
            Return pandas Series or DataFrame with currency detail

        See Also
        --------
        `.symbols`
        `.all_tickers`
        """
        if not currency:
            path = "currencies"
        else:
            path = f"currencies/{currency.upper()}"
        resp = self._request("get", path)
        try:
            resp = resp["data"]
        except KeyError:
            raise KucoinResponseError("No data returned. Is `currency` valid?")
        if isinstance(currency, str):
            return pd.Series(resp)
        else:
            return pd.DataFrame(resp).set_index("currency")


    def get_currency_chains(self, currency):
        """Query specific currency for withdrawal information per chain

        Parameters
        ----------
        currency : str
            Target currency to obtain details (e.g., BTC)
        
        Returns
        -------
        DataFrame
            Returns pandas DataFrame with full details for target currency
        """
        ### Needs further improvement from display standpoint.
        # Chains column return is a dictionary which is not good.
        path = f"currencies/{currency.upper()}"
        resp = self._request("get", path, api_version=self.API_VERSION2)
        df = pd.DataFrame(resp["data"])
        return df

    def get_fiat_prices(self, fiat:str="USD", currency=None) -> pd.Series:
        """Obtain list of all traded currencies denominated in specified fiat
        
        Useful for comparing prices across pairs with different quote currencies
        
        Parameters
        ----------
        fiat : str
            (Optional) Base currency for normalized conversion. Default = USD
            Options: USD [default], EUR, 
        currency : str or list
            (Optional) str or list Specific currency or list of currencies to query. 
            If no currency is specified the function will return all traded currencies.

        Returns
        -------
        pd.Series
            Returns pandas Series containing all currencies or specified list of 
            currencies normalized to the fiat price.
        """
        if isinstance(currency, list):
            currency = ",".join(currency)
        if currency:
            path = f"prices?base={fiat}&currencies={currency}"
        else: 
            path = f"prices?base={fiat}"
        resp = self._request("get", path)
        return pd.Series(resp["data"], name=f"{fiat} Denominated")

    def margin_config(self) -> dict:
        """Pull margin configuration as JSON dictionary"""
        path = "margin/config"
        resp = self._request("get", path)
        return resp["data"]

    def get_socket_detail(self, private:bool=False) -> dict:
        """Get socket details for private or public endpoints"""
        if not private:
            path = "bullet-public"
            is_signed = False
            url = self._request("post", path, signed=is_signed)
            resp = self.session.request("post", url)
        if private:
            path = "bullet-private"
            is_signed = True
            resp = self._request("post", path, signed=is_signed)
        return resp["data"]

    def get_server_time(self, format:str=None, unix=True) -> int:
        """Return server time in UTC time to millisecond granularity

        Notes
        -----
        This function will return the KuCoin official server time in UTC as unix epoch.
        Returned time is an integer value representing time to millisecond precision. 
        This function should be used to sync client and server time as orders submitted 
        with a timestamp over 5 seconds old will be rejected by the server. In some cases,
        client time can lag server time resulting in the server rejected commands as stale.
        
        Parameters
        ----------
        format : str, optional
            If `format='unix'`, return the time as UTC Unix-epoch with millisecond accuracy. If
            `format='datetime'` [default] return a datetime object in UTC time.
        unix : bool, optional
            If `unix=True`, return server time as Unix epoch with millisecond accuracy. Else,
            return datetime object.
        
        Returns
        -------
        int or datetime.datetime
            Returns time to the millisecond either as a UNIX epoch or datetime object
        """
        if format:
            warnings.warn('`format` argument will be deprecated in a future release. Please use `unix` argument')
        path = "timestamp"
        resp = self._request("get", path)
        resp = resp["data"]
        if format == "datetime" or not unix:
            resp = dt.datetime.utcfromtimestamp(
                int(resp) / 1000
            )
        return resp

    def construct_socket_path(self, private=False):
        """Construct socketpath from socket detail HTTP request"""
        socket_detail = self.get_socket_detail(private=private)
        token = socket_detail["token"]
        endpoint = socket_detail["instanceServers"][0]["endpoint"]
        nonce = int(round(time.time(), 3) * 10_000)
        socket_path = endpoint + f"?token={token}" + f"&[connectId={nonce}]"
        return socket_path

    def order(
        self, symbol:str, side:str, size:float=None, funds:float=None, type:str="market", 
        price:float=None, stp:str=None, oid:str=None, remark:str=None, margin:bool=False, 
        mode:str="cross", autoborrow:bool=True, tif:str="GTC", hidden:bool=False, 
        iceberg:bool=False, visible_size:float=None, timeout:int=None, postonly:bool=False,
    ) -> dict:
        """Place limit and market orders using spot trade, cross margin, and isolated margin 

        Parameters
        ----------
        symbol : str
            Specify trading pair for execution (e.g., BTC-USDT)
        side : str
            Specify which side of the trade to execute on (i.e., `buy` or `sell`)
        size : float, optional
            Size in base currency (i.e. the numerator) Quick notes on `size`:
            * Size indicates the amount of base currency to buy or sell
            * Size must be above `baseMinSize` and below `baseMaxSize`
            * Size must be specified in `baseIncrement` symbol units
            * Size must be a positive float value
            
            Note: User is required to either specify size or funds. 
        funds : float, optional
            Amount of funds in quote currency (denominator) to buy or sell. `funds` 
            is not a valid argument for limit orders. Quick notes on `funds` parameter:
            * Funds indicates the amount of price [quote] currency to buy or sell.
            * Funds must be above `quoteMinSize` and below `quoteMaxSize`
            * Size must be specified in `quoteIncrement` symbol units
            * Size must be positive float value

            Note: User is required to either specify size or funds.
        price : float, optional
            Set specific price at which to buy (sell) the trading pair. Price is
            only available to limit orders. If `price` while `type=market`, the
            order will be submitted as a limit order.
        mode : str, optional
            KuCoin supports both `cross` [DEFAULT] and `isolated` margin modes. Please 
            review KuCoin's account type information for more information.
        autoborrow : bool, optional
            Control whether or not the system will automatically borrow funds when
            executing a margin trade with insufficient real balance. If 
            `autoborrow=True` [DEFAULT], the exchange will automatically borrow 
            funds at the best interest rate available. If `false`, users must
            submit manual borrow orders.
        oid : int, optional
            Unique order ID for identification of orders. OID can be set via this 
            argument. If no OID specified, a Unix-time based nonce will be generated
            and attached to the order. 
        remark : str, optional
            Add a maximum 100 character UTF-8 remark to the order execution.
        stp : str, optional
            [LIMIT ONLY] TP or Self-Trade Prevention parameters. Primarily used by 
            market makers or users who have many multidirectional orders that could 
            trade against each other. STP is not enabled by default. Options for STP:
            * `CN`: Cancel newest. If `tif=FOK`, `stp` will be forced to `CN`.
            * `CO`: Cancel oldest
            * `CB`: Cancel both
            * `DC`: Decrease and cancel. Currently not supported for market orders.

        tif : str, optional
            [LIMIT ONLY] Add a Time-in-Force policy to the trade execution. If `tif` 
            unspecified, the default policy is good-to-cancelled. All `tif` options:
            * `GTC`: Good-to-Cancelled. Order will remain on the books till filled or 
            cancelled
            * `GTT`: Good-to-Time. Order will remain on books till filled or till 
              n seconds have passed as specified by `timeout` argument.
            * `IOC`: Immediate or Cancel. IOC orders are filled immediately and not
              added to the book. Any partial amount that cannot be immediately filled
              is cancelled.
            * `FOK`: Fill or Kill. If entire order cannot be filled at `price`, the
              entire order will be rejected.

        timeout : int, optional
            Cancel after n seconds. `timeout` requires Good-to-Time (`tif=GTT`)
            policy. If `timeout`, then `tif` will be forced to GTT.
        postonly : bool, optional
            If postonly is true, orders may only be executed at the maker fee. 
            Orders that would receive taker will be rejected. Postonly is invalid
            when `tif=FOK or IOC`.
        hidden : bool, optional
            [LIMIT ONLY] Orders will not be visible in the orderbook.
        iceberg : bool, optional
            Only a portion of the order will be visible in the orderbook. Use
            `visible_size` to control percentage of order size visible.
        visible_size : float, optional
            Control % of order visible in orderbook. Note that more than 1/20th of 
            the order must be visible or the order will be rejected. To hide the 
            full order use `hidden`.

        Returns
        -------
        dict
            JSON dict with order execution details. See example below:

            {
                code: '200000',
                data: {
                    'side': 'buy',
                    'symbol': 'ETH-USDT',
                    'type': 'limit',
                    'clientOid': 16667957483412,
                    'size': 0.0005,
                    'price': 900,
                    'hidden': False,
                    'postOnly': False,
                    'iceberg': False,
                    'timeInForce': 'IOC',
                    'cancelAfter': None,
                    'remark': None,
                    'stp': None,
                    'orderId': '635948e592d8ed0001929223'
                }
             
            {
        """
        # Add stop-loss feature to function
        type = 'limit' if price else type
        iceberg = True if visible_size else iceberg
        if not size and not funds:
            raise ValueError("Must specify either `size` or `funds`")
        if size and funds:
            raise ValueError("May not specify both `size` and `funds`")
        if type == "limit" and funds: 
            raise ValueError("Limit orders must use `size` argument")
        path = "orders"
        data = {"side": side, "symbol": symbol.upper(), "type": type}
        order_details = data # This initialization is just to put side/symbol/type at top
        order_details['margin'] = margin
        data["clientOid"] = oid if oid else int(time.time() * 10000)
        if size:
            data["size"] = size
        if funds and type == "market":
            data["funds"] = funds
        if margin:
            path = "margin/order" # Update to margin path
            data["marginModel"] = mode
            data["autoBorrow"] = autoborrow
        if type == "limit":
            data["price"] = price
            data["hidden"] = hidden
            data["postOnly"] = postonly
            data["iceberg"] = iceberg
            data["timeInForce"] = tif.upper()
            if timeout:
                data["timeInForce"] = "GTT"
                data["cancelAfter"] = timeout
            else:
                data['cancelAfter'] = None
            if iceberg:
                data["visibleSize"] = visible_size
        data["remark"] = remark
        data['stp'] = stp
        resp = self._request("post", path, signed=True, data=data)
        order_details.update(data)
        if resp['code'] == '200000':
            resp['data'].update(order_details)
        else:
            resp['data'] = order_details
            resp['data'].update({'orderId': None})
        return resp

    def debtratio(self) -> float:
        """Pull current cross margin debt ratio as float value"""
        path = "margin/account"
        resp = self._request("get", path, signed=True)
        return float(resp["data"]["debtRatio"])

    def repay(
        self, currency:str, size:float=None, id=None, symbol:str=None, 
        priority:str="highest", mode="cross",
    ) -> dict:
        """Repay outstanding margin debt against specified currency. 

        Parameters
        ----------
        currency : str
            Specific currency to repay liabilities against (e.g., BTC).
        size : float, optional
            Total sum to repay (in currency terms). Must be a multiple of currency max
            precision. If `size=None` [default], repayment size is max of total margin
            debt or total available balance.
        id : str or None, optional
            Repay by specific order ID. If `id=None` [default], repayment will occur
            across all borrowings for `currency` in `priority` order.
        priority : str, optional
            Specify how to prioritize debt repayment.
            - `highest`: [default] Repay highest interest rate loans first
            - `soonest`: Repay loans with shortest remaining term first 

        Returns
        -------
        dict
            Returns JSON dictionary with repayment confirmation and details.
        """
        if mode == "cross":
            margin_mode = "margin"
            data = {
                "currency": currency.upper(),
                "size": size if size else self.margin_account(currency).availableBalance,
            }
        if mode =="isolated":
            if not size:
                df = self.margin_account(mode="isolated").loc[symbol]
                if currency == df[("Quote", "currency")]:
                    size = df[("Quote", "totalBalance")]
                else:
                    size == df[("Base", "totalBalance")]
            if not symbol:
                raise ValueError("Isolated margin requires both `currency` and `symbol`")
            margin_mode = mode
            data = {
                "symbol": symbol.upper(),
                "currency": currency.upper(),
                "size": float(size),
            }
        if id:
            path = f"{margin_mode}/repay/single"
            if mode == "cross":
                data["tradeId"] = str(id)
            if mode == "isolated":
                data["loanId"] = str(id)
        if not id:
            path = f"{margin_mode}/repay/all"
            if priority == "highest":
                if mode == "cross":
                    data["sequence"] = "HIGHEST_RATE_FIRST"
                else:
                    data["seqStrategy"] = "HIGHEST_RATE_FIRST"
            if priority == "soonest":
                if mode == "cross":
                    data["sequence"] = "RECENTLY_EXPIRE_FIRST"
                else:
                    data["seqStrategy"] = "RECENTLY_EXPIRE_FIRST"
        resp = self._request("post", path, signed=True, data=data)
        return resp

    def get_margin_history(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Obtain record and detail of repaid margin debts"""
        if pagesize > 50:
            raise ValueError("Maximum `pagesize` is 50")
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
            pagesize = 50
        path = f"margin/borrow/repaid?currentPage={page}&pageSize={pagesize}"
        resp = self._request("get", path, signed=True)
        dfs = []
        df = pd.DataFrame(resp["data"]["items"])
        dfs.append(df)
        if concat_paginated == True:
            diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
            for page in range(2, diff+2):
                path = f"margin/borrow/repaid?currentPage={page}&pageSize=50"
                resp = self._request("get", path, signed=True)
                dfs.append(pd.DataFrame(resp["data"]["items"]))
        res = pd.concat(dfs)
        if not res.empty:
            if currency:
                currency = [currency] if isinstance(currency, str) else currency
                res = res[res["currency"].isin(currency)]
            fmt = "%Y-%m-%d %H:%M:%S"
            res.index = pd.to_datetime(res["repayTime"], unit="ms")
            res.index = pd.to_datetime(res.index.strftime(fmt))
            del res["repayTime"]
        return res.squeeze()

    def margin_balance(
        self, id:str or list=None, currency:str or list=None, unix:bool=False, page:int=None
    ) -> pd.DataFrame:
        """Query detailed information regarding current margin balances against the user's account.
        
        Parameters
        ----------
        currency : str or list, optional
            Query specific currency (e.g., BTC) or list of currencies.
        unix : bool, optional
            If `unix=False`, return datetime objects for maturity and created at fields.
            If `unix=True` return unix epoch as integer to millisecond precision.
        page : int, optional
            Response data is paganated. Use `page` to retrieve a single page.
            If `page=None` [default] then all pages will be retrieved and combined into a 
            single response.
        
        Returns
        -------
        DataFrame
            Return pandas DataFrame with list outstanding margin debts. If no debts are 
            outstanding, returns an empty dataframe.
        """
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
        path = f"margin/borrow/outstanding?currentPage={page}&pageSize=50"
        resp = self._request("get", path, signed=True)
        dfs = []
        df = pd.DataFrame(resp["data"]["items"])
        dfs.append(df)
        if concat_paginated == True:
            diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
            for page in range(2, diff+2):
                path = f"margin/borrow/outstanding?currentPage={page}&pageSize=50"
                resp = self._request("get", path, signed=True)
                dfs.append(pd.DataFrame(resp["data"]["items"]))
        res = pd.concat(dfs)
        if res.empty:
            return res
        if currency:
            currency = [currency] if isinstance(currency, str) else currency
            res = res[res['currency'].isin(currency)]
        if not unix:
            res['createdAt'] = pd.to_datetime(res['createdAt'], unit='ms')
            res['maturityTime'] = pd.to_datetime(res['maturityTime'], unit='ms')
        if id:
            id = [id] if isinstance(id, str) else id
            res = res[res['tradeId'].isin(id)]
        res.iloc[:,2:8] = res.iloc[:, 2:8].astype(float)
        return res.set_index('tradeId')
    
    def get_outstanding_loans(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Obtain record of all oustanding loans including those unfilled, partially filled and uncanceled
        
        See Also
        --------
        * `lend`: Place a new lending offer on the market.
        * `lending_rates`: Check outstanding loan offer rates and terms for specified currency.
        * `set_auto_lend`: Toggle auto-lending features for specified currency
        * `get_outstanding_loans`: Return DataFrame with details of all loans filled, unfilled
          and uncancelled.
        * `get_active_loans`: Return DataFrame with details on active, outstanding loans.
        * `get_settled_loans`: Return DataFrame with details on unsettled (inactive) loans.
        """
        if pagesize > 50:
            raise ValueError("Maximum `pagesize` is 50")
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
            pagesize = 50
        path = f"margin/lend/active?currentPage={page}&pageSize={pagesize}"
        resp = self._request("get", path, signed=True)
        dfs = []
        df = pd.DataFrame(resp["data"]["items"])
        dfs.append(df)
        if concat_paginated == True:
            diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
            for page in range(2, diff+2):
                path = f"margin/lend/active?currentPage={page}&pageSize=50"
                resp = self._request("get", path, signed=True)
                dfs.append(pd.DataFrame(resp["data"]["items"]))
        res = pd.concat(dfs).squeeze()
        if not res.empty:
            if currency:
                currency = [currency] if isinstance(currency, str) else currency
                res = res[res["currency"].isin(currency)]
            fmt = "%Y-%m-%d %H:%M:%S"
            res.index = pd.to_datetime(res["createdAt"], unit="ms")
            res.index = pd.to_datetime(res.index.strftime(fmt))
            del res["createdAt"]
        return res

    def get_lending_history(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Get historic details for cancelled or fully filled lend orders
        
        See Also
        --------
        * `lend`: Place a new lending offer on the market.
        * `lending_rates`: Check outstanding loan offer rates and terms for specified currency.
        * `set_auto_lend`: Toggle auto-lending features for specified currency
        * `get_outstanding_loans`: Return DataFrame with details of all loans filled, unfilled
          and uncancelled.
        * `get_active_loans`: Return DataFrame with details on active, outstanding loans.
        * `get_settled_loans`: Return DataFrame with details on unsettled (inactive) loans.
        """
        if pagesize > 50:
            raise ValueError("Maximum `pagesize` is 50")
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
            pagesize = 50   
        path = f"margin/lend/done?currentPage={page}&pageSize={pagesize}"
        resp = self._request("get", path, signed=True)
        dfs = []
        df = pd.DataFrame(resp["data"]["items"])
        dfs.append(df)
        if concat_paginated == True:
            diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
            for page in range(2, diff+2):
                path = f"margin/lend/done?currentPage={page}&pageSize=50"
                resp = self._request("get", path, signed=True)
                dfs.append(pd.DataFrame(resp["data"]["items"]))
        res = pd.concat(dfs).squeeze()
        if not res.empty:
            if currency:
                currency = [currency] if isinstance(currency, str) else currency
                res = res[res["currency"].isin(currency)]
            fmt = "%Y-%m-%d %H:%M:%S"
            res.index = pd.to_datetime(res["createdAt"], unit="ms")
            res.index = pd.to_datetime(res.index.strftime(fmt))
            del res["createdAt"]
        return res

    def get_active_loans(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Access order which are fully filled and oustanding
        
        See Also
        --------
        * `lend`: Place a new lending offer on the market.
        * `lending_rates`: Check outstanding loan offer rates and terms for specified currency.
        * `set_auto_lend`: Toggle auto-lending features for specified currency
        * `get_outstanding_loans`: Return DataFrame with details of all loans filled, unfilled
          and uncancelled.
        * `get_active_loans`: Return DataFrame with details on active, outstanding loans.
        * `get_settled_loans`: Return DataFrame with details on unsettled (inactive) loans.
        """
        if pagesize > 50:
            raise ValueError("Maximum `pagesize` is 50")
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
            pagesize = 50  
        path = f"margin/lend/trade/unsettled?currentPage={page}&pageSize={pagesize}"
        resp = self._request("get", path, signed=True)
        dfs = []
        df = pd.DataFrame(resp["data"]["items"])
        dfs.append(df)
        if concat_paginated == True:
            diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
            for page in range(2, diff+2):
                path = f"margin/lend/trade/unsettled?currentPage={page}&pageSize=50"
                resp = self._request("get", path, signed=True)
                dfs.append(pd.DataFrame(resp["data"]["items"]))
        res = pd.concat(dfs).squeeze()
        if not res.empty:
            if currency:
                currency = [currency] if isinstance(currency, str) else currency
                res = res[res["currency"].isin(currency)]
            fmt = "%Y-%m-%d %H:%M:%S"
            res.index = pd.to_datetime(res["maturityTime"], unit="ms")
            res.index = pd.to_datetime(res.index.strftime(fmt))
            del res["maturityTime"]
        return res

    def get_settled_loans(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Access order which are fully filled and oustanding

        See Also
        --------
        * `lend`: Place a new lending offer on the market.
        * `lending_rates`: Check outstanding loan offer rates and terms for specified currency.
        * `set_auto_lend`: Toggle auto-lending features for specified currency
        * `get_outstanding_loans`: Return DataFrame with details of all loans filled, unfilled
          and uncancelled.
        * `get_active_loans`: Return DataFrame with details on active, outstanding loans.
        * `get_settled_loans`: Return DataFrame with details on unsettled (inactive) loans.
        """
        if pagesize > 50:
            raise ValueError("Maximum `pagesize` is 50")
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
            pagesize = 50  
        path = f"margin/lend/trade/settled?currentPage={page}&pageSize={pagesize}"
        resp = self._request("get", path, signed=True)
        dfs = []
        df = pd.DataFrame(resp["data"]["items"])
        dfs.append(df)
        if concat_paginated == True:
            diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
            for page in range(2, diff+2):
                path = f"margin/lend/trade/settled?currentPage={page}&pageSize=50"
                resp = self._request("get", path, signed=True)
                dfs.append(pd.DataFrame(resp["data"]["items"]))
        res = pd.concat(dfs).squeeze()
        if not res.empty:
            if currency:
                currency = [currency] if isinstance(currency, str) else currency
                res = res[res["currency"].isin(currency)]
            fmt = "%Y-%m-%d %H:%M:%S"
            res.index = pd.to_datetime(res["settledAt"], unit="ms")
            res.index = pd.to_datetime(res.index.strftime(fmt))
            del res["settledAt"]
        return res
    
    def server_status(self) -> dict:
        """Get KuCoin service stats (open, closed, cancelonly)"""
        path = "status"
        resp = self._request("get", path)
        return resp["data"]

    def lend(self, currency:str, size:float, interest:float, term:int):
        """Post lend order to KuCoin lending markets
        
        Parameters
        ----------
        currency : str
            Specify currency to borrow
        size : float
            Total lend size
        interest : float
            Specify daily interest rate as decimal value (i.e., 0.02% should be specified as 0.0002)
        term : int
            Number of days to lock in lending terms. Units in days.

        Returns
        -------
        dict
            Returns dictionary with lend order details.

            {
                'code': '200000',
                'data': {
                    'currency': 'ETH',
                    'size': 1,
                    'dailyIntRate': 0.0002,
                    'term': 7
                }
            }
        """
        data = {"currency": currency.upper(), "size": size, "dailyIntRate": interest, "term": term}
        path = "margin/lend"
        resp = self._request("post", path, data=data, signed=True)
        if resp['code'] == '200000':
            resp['data'].update(data)
        else:
            resp['data'] = data
        return resp

    def cancel_lend_order(self, ids:str or list=None) -> dict:
        """Cancel all or specific active lend orders via currency target or ID
        
        Parameters
        ----------
        ids : str or list, optional
            Specify a single ID or list of IDs to be cancelled. IDs can be obtained via
            `get_oustanding_loans`. If no IDs are specified [default], then ALL unfilled,
            active loands will be cancelled.

        Returns
        -------
        dict
            Return a dictionary of successfully cancelled loans and loan IDs that raised 
            errors.

            {
                '200000': 
                [
                    '635948e592d8ed0001929223',
                    '5da59f5ef943c033b2b643e4,
                ],
                'errors': []
            }

        See Also
        --------
        * `lend`: Place a new lending offer on the market.
        * `lending_rates`: Check outstanding loan offer rates and terms for specified currency.
        * `set_auto_lend`: Toggle auto-lending features for specified currency
        * `get_outstanding_loans`: Return DataFrame with details of all loans filled, unfilled
          and uncancelled.
        * `get_active_loans`: Return DataFrame with details on active, outstanding loans.
        * `get_settled_loans`: Return DataFrame with details on unsettled (inactive) loans.
        """
        path = 'margin/lend/'

        if ids:
            ids = [ids] if not isinstance(ids, (tuple, list)) else ids
        else:
            loans = self.get_outstanding_loans()
            # Filter to onyl unfilled loans
            try:
                ids = loans[loans['filledSize'].astype(float) == 0].index
            except KeyError:
                ids = []
        
        response = {'200000': [], 'error': []}

        for id in ids:
            p = path + id
            resp = self._request('delete', p, signed=True)
            if resp['code'] == '200000':
                response['200000'].append(id)
            else:
                response['error'].append(resp)
        
        return response

    def set_auto_lend(
        self, currency:str, enable:bool, reserve_size:float=0, min_int:float=None,
        term:int=7,
    ) -> dict: 
        """Set specified currency to autolend or disable existing autolend feature

        Before leveraging the autolend features check out the documentation here:
        https://docs.kucoin.com/#set-auto-lend
        
        Parameters
        ----------
        currency : str
            Specify currency on which to set autolend features (e.g., BTC)
        enable : bool
            Toggle autolend feature on or off (e.g. `enable=True`, sets autolend to on)
        reserve_size : float, optional
            Add a reserve size which will not be lent out automatically. E.g., if you have
            a reserve size set to 0.1 which 1.0 BTC in your account, only 0.9 will be
            lent automatically.
        daily_int : float, optional
            Set a minimum daily interest rate that you are willing to lend at. Note that
            this argument will default to the minimum current market rate (as obtainable
            through `lending_rate` function) if not specified. It is highly recommended
            that user's specify their own target rate.
        term : int, optional
            Lending term in days that assets will be offered. Note that user's may receive
            assets back in their account earlier than the term if the borrower repays their
            debt early. Term must be one of `[7, 14, 28]`.

        Returns
        -------
        dict
            Return dictionary with confirmation code and data related to autolend terms:

            {
                'code': '200000',
                'data':
                {
                    'currency': 'BTC',
                    'isEnable': False,
                    'retainSize': 0,
                    'dailyIntRate': None,
                    'term': 7
                }
            }

        See Also
        --------
        * `lend`: Place a new lending offer on the market.
        * `lending_rates`: Check outstanding loan offer rates and terms for specified currency.
        * `set_auto_lend`: Toggle auto-lending features for specified currency
        * `get_outstanding_loans`: Return DataFrame with details of all loans filled, unfilled
          and uncancelled.
        * `get_active_loans`: Return DataFrame with details on active, outstanding loans.
        * `get_settled_loans`: Return DataFrame with details on unsettled (inactive) loans.
        """
        currency = currency.upper()
        if enable and not min_int:
            # Check current minimum rate that others are lending currently. Assume this 
            # approximates a "market" rate.
            min_int = self.lending_rate(currency).dailyIntRate.min()
        if term not in [7, 14, 28]:
            raise ValueError(f'Term length must be 7, 14, or 28 days. Your input: {term}')
        path = 'margin/toggle-auto-lend'
        data = {
            'currency': currency,
            'isEnable': enable,
            'retainSize': reserve_size,
            'dailyIntRate': min_int,
            'term': term,
        }
        resp = self._request('post', path, signed=True, data=data)
        resp['data'] = data
        return resp

    def borrow(
        self, currency:str, size:float, maxrate:float=None, 
        type:str="IOC", term:int or list=None,
    ) -> dict:
        """Post borrow request to KuCoin lending markets
        
        Parameters
        ----------
        currency : str
            Specify currency to borrow
        size : float
            Total borrow size
        maxrate : float, optional
            Maximum acceptable daily interest rate. If not specified, all rates will
            be accepted.
        term : int or list, optional
            Specify acceptable term length or list of term lengths. If not specified,
            all term lengths will be accepted. Currently supportered term lengths:
            `[7, 14, 28]`. Term lengths are measured in days
        type : str, optional
            Execution type. Borrow orders supports `FOK` or `IOC` orders.
            * `IOC`: Immediate or Cancel. This is the detault order submission. 
              Maximum portion of borrow order that is immediately fillable will 
              be executed with the remaining portion immediately cancelled.
            * `FOK`: Fill or Kill. FOK orders will either be filled in their
              entirety or immediately cancelled. No partial fulfillment is
              allowed.

        Returns
        -------
        dict
            Returns dictionary with order details. Use orderId with 
            `.get_borrow_order` to obtain order details.

            {
                'code': '103000',
                'msg': 'Exceed the borrowing limit, the remaining borrowable amount is: 0.19ETH',
                'data': {
                    'currency': 'ETH',
                    'type': 'IOC',
                    'size': 1,
                    'maxRate': None,
                    'term': None
                }
            }
        """
        data = {"currency": currency.upper(), "type": type.upper(), "size": size, "maxRate": maxrate}
        if term:
            term = [term] if isinstance(term, int) else term
            term = [str(period) for period in term]
            data["term"] = ",".join(term)
        else:
            data["term"] = None
        path = "margin/borrow"
        resp = self._request("post", path, data=data, signed=True)
        if resp['code'] == '200000':
            resp['data'].update(data)
        else:
            resp['data'] = data
        return resp

    def cancel_order(
        self, symbols:str or list=None, type:str='trade', oid:str or list=None, 
        cid:str or list=None,
    ) -> list:
        """Cancel orders by ID or cancel all orders related to a specific currency pair

        Use this endpoint to cancel single orders or to submit batches of cancellations.
        You are able to submit blended batches with some CID/OID lists alongside lists of 
        symbols (although all orders must be in the same account type). It is highly recommended
        that you avoid overlap in your cancellation batches. For example, users should avoid 
        submitting an order ID corresponding to an ETH-USDT order while also submitting the 
        cancellation of all ETH-USDT orders. Be aware that each ID and symbol pair added for
        cancellation requires additional API calls on the backend. For best performance, 
        work to consolidate the number of total requests when submitting cancellations.
        
        Parameters
        ----------
        symbols : str or list, optional
            Specify a currency pair or list of currency pairs (e.g. 'ETH-USDT') for which to 
            cancel ALL outstanding orders. Users must specify one or more of `symbols`, `id`,
            or `oid` arguments.
        type : str, optional
            Specify market in which to submit cancellations. Current markets are 
            `['trade', 'cross', 'isolated']`. Default is the trade (spot) market.
        oid : str or list, optional
            Specify one or more orders by OID. OID are assigned by KuCoin upon order
            submission. Users must specify one or more of `symbols`, `id`,
            or `oid` arguments.
        cid : str or list, optional
            Specify one or more orders by unique client-assigned ID. Client IDs are attached
            to orders by the client upon order submission. Users must specify one or more 
            of `symbols`, `id`, or `oid` arguments.

        Response
        --------
        dict
            Return dictionary with list of successfully cancelled order IDs and error responses

            {
                '200000': 
                [
                    '635948e592d8ed0001929223',
                    '5da59f5ef943c033b2b643e4,
                ],
                'errors': []
            }
        """
        if not symbols and not cid and not oid:
            raise ValueError("Must specify one of `symbols`, `id`, or `oid`")

        if type == 'cross' or type == 'margin':
            type = 'MARGIN_TRADE'
        elif type == 'isolated':
            type = 'MARGIN_ISOLATED_TRADE'
        else:
            type = 'TRADE'

        cancellations = []

        if cid:
            cids = [cid] if isinstance(cid, str) else cid
            for cid in cids:
                path = f"order/client-order/{cid}"
                cancellations.append(path)
        if oid:
            oids = [oid] if isinstance(oid, str) else oid
            for oid in oids:
                path = f"orders/{oid}"
                cancellations.append(path)
        if symbols:
            symbols = [symbols] if isinstance(symbols, str) else symbols
            for symbol in symbols:
                path = f"orders?symbol={symbol}&tradeType={type}"
                cancellations.append(path)

        responses = {'200000': [], 'error': []}
        for path in cancellations:
            resp = self._request("delete", path, signed=True)
            if resp["code"] == '200000':
                r = resp["data"].get("cancelledOrderIds")
                if not r:
                    r = resp['data'].get("cencelledOrderId")
                r = [r] if isinstance(r, str) else r
                if r:
                    responses['200000'] += r
            else:
                logging.error(
                    "Order cancellation failure: " +
                    resp["msg"]
                )
                responses['error'].append(resp)

        return responses

    def order_history(
        self, symbols:str or list=None, start:str=None, end:str=None, acc_type:str="trade",
        side:str=None, status:str="done", order_type:str or list=None, consolidated:bool=True,
        page:int=None, id:str or list=None, oid:str or list=None, channel:str or list=None,
    ) -> pd.DataFrame:
        """Detailed cross account information on both active and completed orders

        This function returns order details in two flavors: Consolidated and unconsolidated. 
        The consolidated response contains only order price, order size, value of the filled
        portion, amount of order size that was filled, fees paid, and relevant asset details
        Unconsolidated responses contain an additional 20+ detail columns that will, for most 
        users, not be useful. Use the `consolidated` argument to toggle between these responses.
        Be aware that this endpoint is both slow to run and slow to update. As such, it is not
        intended for use in performance-oriented algorithms. For significantly faster performance
        time, use `.pull_by_oid` or `.pull_by_cid` functions.

        Parameters
        ----------
        acc_type : str, optional
            Specify which account type to return active/completed trades from. Valid account 
            types are `['trade', 'cross', 'isolated']`. Default account type is trade.
        symbols : str or list, optional
            Return only specified symbol or list of symbols (e.g., `['BTC-USDT', 'ETH-USDT']`)
        start : dt.datetime or str, optional
            Specify earliest date to obtain trade history from. String dates should be in 
            YYYY-MM-DD format with HH:MM:SS additioionally accepted (e.g., '2022-01-01 00:00:00').
            If `start` is not specified, default behavior will be to return last 7 days of order
            history.
        end : dt.datetime or str, optional
            Specify latest date to obtain trade history from. String formatting requirements are
            identical to `start`. If `end` is specified, but not `start`, a ValueError will be
            raised.
        side : str, optional
            Return only `'buy'` or `'sell'` orders. By default both buy and sell with be returned.
        status : str, optional
            Return only active or only completed orders. For completed orders use `status='done'` 
            [default]. For active use, `status='active'`.
        order_type : str or list, optional
            Filter by order type(s). All order types are returned by default. Valid order types: 
            `['limit', 'market', 'limit_stop', 'market_stop']`.
        consolidated : bool, optional
            If `False` [default], return all columns in full response. Set to `True`, for focused
            response data.
        page : int, optional
            For better execution performance, specify a target page. If `page=None` [default],
            all pages will be concatenated into one response. This process does require multiple
            API calls assuming there is more than one page of responses and as such preformance will
            be reduced.
        id : str or list, optional
            Filter response by ID or list of IDs.
        oid : str or list, optional
            Filter response by client OID (client OID are user assigned IDs attached to the order at
            time of submission).
        channel : str, optional
            Filter by order entry channel. Valid channels include `['API', 'ANDROID', 'IOS', 'WEB']`

        Returns
        -------
        DataFrame
            Returns pandas DataFrame with historic order details. If no orders data is 
            found, an empty dataframe will be returned.

        See Also
        --------
        * `.recent_orders`: Light-weight function for obtaining orders placed in the last 24-hours
        * `.pull_by_cid`: Pull a single order execution detail by user-generated OID. High performance function.
        * `.pull_by_oid`: Pull a single order execution detail by KuCoin-generated OID. High performance function.
        
        Notes
        -----
        * Be aware that extended date ranges and large trade counts within a date ranges will
        significantly impact function execution time. For quicker execution time, limit date ranges
        as possible.
        * Per 7 day interval, KuCoin will only return a maximum of 50,000 trades. If you are
        executing / canceling more than 50,000 trades per 7 day period, this is not an appropriate
        endpoint.
        * Record of cancelled trades will only be maintained for 30 days by KuCoin's servers.
        """
        if end and not start:
            raise ValueError('Connect specify `end` without also specifying `start`')
        if acc_type == 'cross' or acc_type == 'margin':
            acc_type = 'MARGIN_TRADE'
        elif acc_type == 'isolated':
            acc_type = 'MARGIN_ISOLATED_TRADE'
        else:
            acc_type = 'TRADE'

        if start:
            if isinstance(start, str):
                start = _parse_date(start, as_unix=False)
        if end:
            if isinstance(end, str):
                end = _parse_date(end, as_unix=False)
        else:
            end = dt.datetime.now()

        if start:
            intervals = math.ceil(td.Timedelta(end - start).days/7)
        else:
            intervals = 1
        responses = [] # Container for dataframe responses over multiple intervals

        for _ in range(intervals):
            concat_paginated = False
            if not page:
                concat_paginated = True
                page = 1
            path = f"orders?status={status}&tradeType={acc_type}&currentPage={page}&pageSize=500"
            if start:
                unix_start = int(time.mktime(start.timetuple()))
                path += f"&startAt={unix_start*1000}"
            resp = self._request("get", path, signed=True)

            dfs = []
            df = pd.DataFrame(resp["data"]["items"])
            dfs.append(df)
            if concat_paginated == True:
                diff = resp["data"]["totalPage"] - resp["data"]["currentPage"]
                # Rotate through additional results pages when neccesary
                for page in range(2, diff+2):
                    path = f"orders?status={status}&tradeType={acc_type}&currentPage={page}&pageSize=500"
                    if start:
                        path += f"&startAt={unix_start*1000}"
                    resp = self._request("get", path, signed=True)
                    temp_df = pd.DataFrame(resp["data"]["items"])
                    dfs.append(temp_df)
            res = pd.concat(dfs)
            responses.append(res)
            page = None # Reset page to none, this will force repeat page iteration
            if start:
                start += dt.timedelta(days=7)
        
        res = pd.concat(responses, axis=0)
        if res.empty:
            return res
        # Add a unix bool flag here
        res['createdAt'] = pd.to_datetime(res['createdAt'], unit='ms')
        if isinstance(res, pd.DataFrame):
            res.set_index('createdAt', inplace=True)
            res.sort_values('createdAt', inplace=True)
            end += dt.timedelta(days=1)
            res = res.loc[:end]

        if id:
            id = [id] if isinstance(id, str) else id
            res = res[res['id'].isin(id)]
        if oid:
            oid = [oid] if isinstance(oid, str) else oid
            res = res[res['clientOid'].isin(oid)]
        if channel:
            res = res[res['channel'] == channel]
        if order_type:
            order_type = [order_type] if isinstance(order_type, str) else order_type
            res = res[res['type'].isin(order_type)]
        if symbols:
            symbols = [symbols] if isinstance(symbols, str) else symbols
            symbols = [symbol.upper() for symbol in symbols]
            res = res[res['symbol'].isin(symbols)]
        if side:
            res = res[res['side'] == side]
        if consolidated:
            consol_columns = [
                'symbol', 'type', 'side', 'price', 'size', 
                'dealFunds', 'dealSize', 'fee'
            ]
            res = res[consol_columns]
        float_cols = ['price', 'size', 'dealFunds', 'dealSize','fee']
        res[float_cols] = res[float_cols].astype(float)
        # somehow duplicates are getting into the response...
        return res.drop_duplicates().sort_index(ascending=False)

    def get_borrow_order(self, id):
        """Use orderId from `.borrow` to obtain loan details"""
        path = f"margin/borrow?orderId={id}"
        resp = self._request("get", path, signed=True)
        return resp

    def pull_by_cid(self, cid:str, unix:bool=True) -> pd.Series:
        """Pull single order by KuCoin generated OID
        
        Parameters
        ----------
        cid : str
            Specify tradeId for target order. tradeId's are autogenerated
            IDs attached to trades by KuCoin's order matching system.
        unix : bool, optional
            Leverage `unix` arguments to specify how to return trade timestamps.
            If `unix=True` [default] times are returned as UTC unix epoch, else
            datetimes will be converted to UTC datetime object.

        Returns
        -------
        Series
            Returns pandas Series with trade details

        See Also
        --------
        `pull_by_oid`: Pull single trade by user-generated orderId.
        `order_history`: Obtain comprehensive list of past orders
        `recent_orders`: Obtain list of order placed in last 24 hours
        """
        path = f"order/client-order/{cid}"
        resp = self._request("get", path, signed=True)
        try:
            ser = pd.Series(resp['data'])
        except KeyError:
            raise KucoinResponseError(f'No response returned for {cid}')
        ser.iloc[5:11] = ser.iloc[5:11].astype(float)
        if not unix:
            ser.createdAt = pd.to_datetime(ser.createdAt, unit='ms')
        return ser

    def pull_by_oid(self, oid:str, unix:bool=True) -> pd.Series:
        """Pull single order by user-generated client OID

        Parameters
        ----------
        oid : str
            Specify tradeId for target order. orderId's are user generated IDs
            attached to trades via the `oid` argument or `order` when placing an
            order.
        unix : bool, optional
            Leverage `unix` arguments to specify how to return trade timestamps.
            If `unix=True` [default] times are returned as UTC unix epoch, else
            datetimes will be converted to UTC datetime object.

        Returns
        -------
        Series
            Returns pandas Series with trade details

        See Also
        --------
        `pull_by_cid`: Pull single trade by user-generated orderId.
        `order_history`: Obtain comprehensive list of past orders
        `recent_orders`: Obtain list of order placed in last 24 hours
        """
        path = f"orders/{oid}"
        resp = self._request("get", path, signed=True)
        try:
            ser = pd.Series(resp['data'])
        except KeyError:
            raise KucoinResponseError(f'No response returned for {oid}')
        ser.iloc[5:11] = ser.iloc[5:11].astype(float)
        if not unix:
            ser.createdAt = pd.to_datetime(ser.createdAt, unit='ms')
        return ser

    def mark_price(self, symbol:str) -> pd.Series:
        """Get mark price data for a specified symbol"""
        path = f"mark-price/{symbol.upper()}/current"
        resp = self._request("get", path)
        if resp['code'] != '200000':
            raise KucoinResponseError(resp["msg"])
        return pd.Series(resp['data'])
