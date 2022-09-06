import time
import requests
import base64, hashlib, hmac
import json
import calendar
import warnings
import logging
import functools
import numpy as np
import pandas as pd
import datetime as dt
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
        except ConnectionError: # macOS sometimes throws this error if session has idled
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
    api_key : str 
        (Optional) API key generated upon creation of API endpoint on
        kucoin.com. If no API key is given, the user cannot access functions requiring
        account level authorization, but can access endpoints that require general auth
        such as kline historic data.
    api_secret : str 
        (Optional) Secret API sequence generated upon create of API
        endpoint on kucoin.com. See api_keydocs for info on optionality of 
        variable
    api_passphrase : str 
        (Optional) User created API passphrase. Passphrase is 
        created by the user during API setup on kucoin.com. See api_keydocs for 
        info on optionality of variable
    sandbox : bool 
        If sandbox = True, access a special papertrading API version
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
        path = "sub/user"
        resp = self._request("get", path, signed=True)
        df = pd.DataFrame(resp["data"])
        if df.empty:
            raise KucoinResponseError("No sub-users found")
        return df

    def accounts(
        self, type:str=None, currency:str=None, balance:float=None, id:str=None,
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
            df = df[df["type"] == type]
        if currency:
            df = df[df["currency"] == currency]
        if balance:
            df = df[df["balance"] >= balance]
        if df.empty:
           raise KucoinResponseError("No accounts found / no data returned.")
        if not id:
            df.set_index("id")
        return df

    def create_account(self, currency:str, type:str) -> dict:
        """Create a new sub-account of account type `type` for currency `currency`.

        Parameters
        ----------
        currency : str 
            Currency account type to create (e.g., BTC).
        type: str 
            Type of account to create. Options: main, trade, margin.

        Returns
        -------
        dict
            JSON dictionary with confirmation message and new account ID.
        """
        data = {"type": type, "currency": currency}
        path = "accounts"
        resp = self._request("post", path, signed=True, data=data)
        return resp.json()

    def get_subaccounts(self, id:str or None=None) -> dict:
        """Returns account details for all sub-accounts. Requires Trade authorization"""
        path = f"sub-accounts"
        if id:
            path = f"path/{id}"
        url = self._request("get", path, signed=True)
        response = self.session.request("get", url)
        resp = response.json()["data"]
        if not resp:
            raise KucoinResponseError("No sub-accounts found")
        return resp

    def recent_orders(self, page:int=1, pagesize:int=50, id:str=None) -> pd.DataFrame:
        """Returns DataFrame with details of all trades placed in last 24 hours.

        Notes
        -----
            - Max trades per page is 500; Min trades per page is 10
            - Max number of trades returned (across all pages) is 1000
            - Data is paganated into n pages displaying `pagesize` number of trades

        Parameters
        ----------
        page : int 
            (Optional) JSON response is paganated. Use this variable
            to control the page number viewed. Default value returns first 
            page of paganated data.
        pagesize : int 
            (Optional) Max number of trades to display per response
            Default `pagesize` is 50.
        id : str, optional
            Specify an explicit order ID to return values for only that order
        
        Returns
        -------
        DataFrame or Series
            Returns pandas DataFrame with complete list of trade details or if a single
            order ID was specified return a pandas Series with only that trade's details
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
            df["createdAt"] = pd.to_datetime(df["createdAt"], unit="ms")
            df = df.set_index("createdAt")
        else:
            df = pd.Series(resp)
            df.createdAt = pd.to_datetime(df.createdAt, unit="ms")
        return df

    def transfer(
        self, currency:str, source_acc:str, dest_acc:str, amount:float, oid:str=None
    ) -> dict:
        """Function for transferring funds between margin, trade and main accounts.

        Parameters
        ----------
        currency : str 
            Currency to transfer between accounts (e.g., BTC-USDT).
        source_acc : str 
            Source account type. Options are: Main, trade, and margin.
        dest_acc : str 
            Destination account type. Options are: Main, trade, and margin.
        amount : float 
            Positive float value. Must be of the transfer currency precision.
        oid : str
            (Optional) Unique order ID for identification of transfer. OID will 
            autogenerate an integer based on the UNIX epoch if not explicitly 
            given.
        
        Returns
        -------
        dict
            JSON dictionary with transfer confirmtion and details.
        """
        path = "accounts/inner-transfer"
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
        resp = self._request(
            "post", path, signed=True, api_version=self.API_VERSION2, data=data
        )
        return resp.json()

    def margin_balance(self, currency:str=None) -> dict:
        """Query all outstanding margin balances.
        
        Parameters
        ----------
        currency : str 
            (Optional) Query specific currency (e.g., BTC).
            If no currency is specified, query all currencies.
        
        Returns
        -------
        dict
            JSON dictionary with margin balance details.
        """
        path = "margin/borrow/outstanding"
        if currency:
            path = f"{path}?={currency}"
        resp = self._request("get", path, signed=True)
        return resp["data"]

    def ohlcv(
        self, tickers:str or list, begin:dt.datetime or str, 
        end:None or dt.datetime or str=None, interval:str="1day", 
        ascending:bool=True, warning:bool=True,
    ) -> pd.DataFrame:
        """Query historic OHLC(V) data for a ticker or list of tickers 

        Notes
        -----
            Server time reported in UTC

        Parameters
        ----------
        tickers : str or list
            Currency pair or list of pairs. Pair names must be formatted in upper 
            case (e.g. ETH-BTC)
        begin : str or datetime.datetime
            Earliest time for queried date range. May be given either as a datetime object
            or string. String format may include hours/minutes/seconds or may not
            String format examples: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
        end : None or str or datetime.datetime, optional
            (Optional) Ending date for queried date range. This parameter has the same
            formatting rules and flexibility of param `begin`. If left unspecified, end 
            will default to the current UTC date and time stamp.
        interval : str, optional
            Interval at which to return OHLCV data. Intervals: `["1min", 
            "3min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", "8hour", 
            "12hour", "1day", "1week"]`. Default=1day
        ascending : bool, optional
            If `ascending=True`, dataframe will be returned in standard order. If `False`,
            return data in reverse chronological.
        warning : bool, optiona
            Toggle whether function warns user about excessive API calls

        Returns
        -------
        DataFrame
            Returns pandas Dataframe indexed to datetime
        """
        if isinstance(begin, str):
            begin = _parse_date(begin)

        if end:
            if isinstance(end, str):
                end = _parse_date(end)
        else:
            end = dt.datetime.utcnow()

        if isinstance(tickers, str):    
            tickers = [tickers]
        tickers = [ticker.upper() for ticker in tickers]

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
                    Server may require one or multiple timeouts
                """)

        for ticker in tickers:
            paths = []
            for begin, end in unix_ranges:
                path = f"market/candles?type={interval}&symbol={ticker}&startAt={begin}&endAt={end}"
                paths.append(path)

            df_pages = []   # List for individual df returns from paganated values

            for path in paths:
                try:
                    resp = self._request("get", path)
                    if resp["code"] == '400100': # Handle invalid trading pair response
                        raise KucoinResponseError(f"Pair not recognized. Is {ticker} a valid trading pair?")
                    try:
                        r = resp["data"]
                    except KeyError:
                        print(resp)
                        logging.debug(f"No more data available for {ticker}")
                        break
                    df = pd.DataFrame(r)
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
                except KeyError as e:
                    logging.debug(f"End of timeseries reached for {ticker}")
                    break
                except requests.exceptions.ConnectionError as e:
                    logging.info("ConnectionError raised. 5 minute timeout.")
                    logging.debug(e, exc_info=True)
                    self.session.close()
                    time.sleep(300) # Ten minute time out
                    self.session = self._session()
                    resp = self.session._request("get", path)
                except requests.exceptions.ReadTimeout as e:
                    logging.info("Request.exceptions.ReadTimeout. 5 minute timeout")
                    logging.debug(e, exc_info=True)
                    self.session.close()
                    time.sleep(300) # Ten minute time out
                    self.session = self._session()
                    resp = self.session._request("get", path)
            if len(df_pages) > 1:
                dfs.append(pd.concat(df_pages, axis=0))
            else:
                dfs.append(df_pages[0])
        if len(dfs) > 1:
            return pd.concat(dfs, axis=1, keys=tickers).sort_index(ascending=ascending)
        else:
            return dfs[0].sort_index(ascending=ascending)

    def symbols(
        self, pair:str or list or None=None, market:str or list or None=None, 
        marginable:str or list or None=None, quote:str or list or None=None,
        base:str or list or None=None, tradable:str or list or None=None,
    ) -> pd.DataFrame or pd.Series:
        """Highly configurable query for detailed list of currency pairs

        Primary trading pair detail endpoint for users. This function will return an outline of 
        trading details for all pairs on the KuCoin platform. This function is highly configurable
        accepting several filtering arguments to return a more focused look at the market.
        
        Parameters
        ----------
        currency : str or list or None, optional
            Specify a single pair or list of pairs to query. If `currency=None`, return 
            all trading pairs
        market : str or list or None, optional
            Filter response by trading market. If `market=None` return all markets. Markets:
            `['ALTS', 'BTC', 'DeFi', 'NFT', 'USDS', 'KCS', 'Polkadot', 'ETF', 'FIAT']`
        base : str or list or None, optional
            Specify explicit base currency or list of currencies. If `base_curr=None` 
            [DEFAULT], all base currencies will be returned.
        quote : str or list or None, optional
            Specify explicit quote currency or list of currencies. If `base_curr=None` 
            [DEFAULT], all quote currencies will be returned.
        marginable : bool or None
            If `marginable=True`, return only marginable securities. If `marginable=False` return only
            securities which cannot be traded on margin. If `marginable=None` [DEFAULT] return all
            trading pairs regardless of marginability.
        tradable : bool or None
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

    def lending_rate(self, currency:str, term:int=None) -> pd.DataFrame:
        """Query API to obtain current a list of available margin terms

        Notes
        -----
            Sorted descending on sequence of daily interest rate and term

        Parameters
        ----------
        currency : str
            Target currency to pull lending rates on (e.g., BTC)
        
        Returns
        -------
        DataFrame
            Returns pandas DataFrame containing margin rate details
        """
        path = f"margin/market?currency={currency.upper()}"
        if term:
            path = path + f"&term={term}"
        resp = self._request("get", path)
        if df.empty:
            KucoinResponseError("No results for currency and term combination")
        df = pd.DataFrame(resp["data"])
        return df

    def get_marginable_pairs(self, base:None or str or list=None) -> pd.DataFrame:
        """Obtain all marginable securities with trade details

        Parameters
        ----------
        base : None or str or list, optional
            Filter results by base currency. Margin only supported currently 
            for `[BTC, ETH, USDT, USDC]`

        Returns
        -------
        pd.DataFrame
            Return DataFrame object with marginable trading pairs and
            relevant trade details for each pair.
        """
        warnings.warn("This endpoint will be deprecated in the near future. Please use `.symbols`")
        if base:
            if isinstance(base, str):
                base = [base]
            base = [ticker.upper() for ticker in base]
        path = "symbols"
        resp = self._request("get", path)
        df = pd.DataFrame(resp["data"])
        marginTrue = df["isMarginEnabled"] == True
        tradingEnabled = df["enableTrading"] == True
        df = df[marginTrue & tradingEnabled]
        if base:
            df = df[df["quoteCurrency"].isin(base)]
        return df

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
        self, asset:None or str or list=None, balance:None or float=None, 
        mode:str="cross",
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
            df.sort_values("totalBalance", inplace=True)
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
        return pd.Series(resp["data"])

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

    def get_level1_orderbook(self, pair:str, time="utc") -> pd.Series or pd.DataFrame:
        """Obtain best bid-ask spread details for a specified pair"""
        path = f"market/orderbook/level1?symbol={pair.upper()}"
        resp = self._request("get", path)
        resp = resp["data"]
        if resp is None:
            raise KucoinResponseError("No data returned for pair.")
        ser = pd.Series(resp, name=pair)
        if time == "utc":
            ser.loc["time"] = pd.to_datetime(
                dt.datetime.utcfromtimestamp(
                    ser.loc["time"] / 1000
                ).strftime('%Y-%m-%d %H:%M:%S')
            )
        if time == "unix" or not time:
            pass
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

    def get_server_time(self, format:str="unix") -> int:
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
            If `format=unix`, return the time as UTC Unix-epoch with millisecond accuracy. If
            `format=datetime` [default] return a datetime object in UTC time.
        
        Returns
        -------
        int or datetime.datetime
            Returns time to the millisecond either as a UNIX epoch or datetime object
        """
        path = "timestamp"
        resp = self._request("get", path)
        resp = resp["data"]
        if format == "datetime":
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
            JSON dict with order execution details
        """
        if price:
            type = "limit"
        if visible_size:
            iceberg = True
        if not size and not funds:
            raise ValueError("Must specify either `size` or `funds`")
        if size and funds:
            raise ValueError("May not specify both `size` and `funds`")
        if type == "limit" and funds: 
            raise ValueError("Limit orders must use `size` argument")
        path = "orders"
        data = {"side": side, "symbol": symbol, "type": type}
        data["clientOid"] = oid if oid else int(time.time() * 10000)

        if size:
            data["size"] = size
        if funds and type == "market":
            data["funds"] = funds
        if margin:
            path = "margin/order" # Update to margin path
            data["marginMode"] = mode
            data["autoBorrow"] = autoborrow
        if type == "limit":
            data["price"] = price
            data["hidden"] = hidden
            data["postOnly"] = postonly
            data["iceberg"] = iceberg
            data["timeInForce"] = tif
            if timeout:
                data["timeInForce"] = "GTT"
                data["cancelAfter"] = timeout
            if iceberg:
                data["visibleSize"] = visible_size
        if remark:
            data["remark"] = remark
        if stp:
            data["stp"] = stp
        resp = self._request("post", path, signed=True, data=data)
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
        """Function for repaying all outstanding margin debt against specified currency. 

        Parameters
        ----------
        currency : str 
            Specific currency to repay liabilities against (e.g., BTC).
        size : float, optional
            Total currency sum to repay. Must be a multiple of currency max
            precision.
        id : str or None, optional
            Repay by specific order ID. If no ID is provided, repayment will occur
            across all borrowings for that currency in `priority` order.
        priority : str, optional
            Specify how to prioritize debt repayment.
            - Highest: Repay highest interest rate loans first
            - Soonest: Repay nearest term loans first 

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

    def get_outstanding_margin(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Obtain record and detail of outstanding margin debts"""
        if pagesize > 50:
            raise ValueError("Maximum `pagesize` is 50")
        concat_paginated = False
        if not page:
            concat_paginated = True
            page = 1
            pagesize = 50
        path = f"margin/borrow/outstanding?currentPage={page}&pageSize={pagesize}"
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
    
    def get_outstanding_loans(
        self, currency:str or list=None, page:int=None, pagesize:int=50
    ) -> pd.DataFrame or pd.Series:
        """Obtain record of outstanding loans"""
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
        """Get historic details for cancelled or fully filled lend orders"""
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
        """Access order which are fully filled and oustanding"""
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
        """Access order which are fully filled and oustanding"""
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
        """Post lend order to KuCoin lending markets"""
        data = {"currency": currency, "size": size, "dailyIntRate": interest, "term": term}
        path = "margin/lend"
        resp = self._request("post", path, data=data, signed=True)
        return resp

    def get_borrow_order(self, id):
        """Get borrow order details for specific order ID"""
        path = f"margin/borrow?orderId={id}"
        resp = self._request("get", path, signed=True)
        return resp

    def borrow(
        self, currency:str, size:float, maxrate:float=None, 
        type:str="FOK", term:int or list or None=None,
    ) -> dict:
        """Post borrow request to KuCoin lending markets"""
        data = {"currency": currency, "type": type, "size": size}
        if maxrate:
            data["maxRate"] = maxrate
        if term:
            term = [term] if isinstance(term, int) else term
            term = [str(period) for period in term]
            data["term"] = ",".join(term)
        path = "margin/borrow"
        resp = self._request("post", path, data=data, signed=True)
        return resp
