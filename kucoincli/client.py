import time
import requests
import base64, hashlib, hmac
import pandas as pd
import json
import calendar
import datetime as dt
import warnings
import logging

from kucoincli.utils._helpers import _parse_date
from kucoincli.utils._helpers import _parse_interval
from kucoincli.utils._kucoinexceptions import ResponseError


class Client(object):

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
            return uri, headers

        return uri

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

    def subusers(self) -> pd.DataFrame:
        """Obtain a list of sub-users"""
        path = "sub/user"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        df = pd.DataFrame(response.json()["data"])
        if df.empty:
            raise ResponseError("No sub-users found")
        return df

    def get_accounts(
        self, type:str=None, currency:str=None, balance:float=None
    ) -> pd.DataFrame:
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

        Returns
        -------
        DataFrame
            Returns pandas dataframe with account details.
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

    def get_account(self, account_id:str) -> pd.Series:
        """Obtain account details for an account specified by ID number"""
        path = f"accounts/{account_id}"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        return pd.Series(response.json()["data"])

    def create_account(self, type:str, currency:str) -> dict:
        """Create a new sub-account of account type `type` for currency `currency`.

        Parameters
        ----------
        type: str 
            Type of account to create. Options: main, trade, margin.
        currency : str 
            Currency account type to create (e.g., BTC).

        Returns
        -------
        dict
            JSON dictionary with confirmation message and new account ID.
        """
        data = {"type": type, "currency": currency}
        path = "accounts"
        url, headers = self._request("post", path, signed=True, data=data)
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def get_subaccounts(self) -> dict:
        """Returns account details for all sub-accounts. Requires Trade authorization"""
        path = f"sub-accounts"
        url, headers = self._request("get", path, signed=True)
        response = requests.request("get", url, headers=headers)
        resp = response.json()["data"]
        if not resp:
            raise ResponseError("No sub-accounts found")
        return resp

    def recent_orders(self, page:int=1, pagesize:int=50) -> pd.DataFrame:
        """Returns pandas Series with last 24 hours of trades detailed.

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
        
        Returns
        -------
        DataFrame
            Returns pandas DataFrame with complete list of trade details.
        """
        path = f"limit/orders?currentPage={page}&pageSize={pagesize}"
        url, headers = self._request("get", path, signed=True)
        resp = requests.request("get", url, headers=headers)
        resp = resp.json()["data"]
        if not resp:
            raise ResponseError("No orders in the last 24 hours.")
        return pd.DataFrame(resp)

    def transfer_funds(
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
        url, headers = self._request(
            "post", path, signed=True, api_version=self.API_VERSION2, data=data
        )
        data_json = self._compact_json_dict(data)
        resp = requests.request("post", url, headers=headers, data=data_json)
        return resp.json()

    def repay_all(self, currency:str, size:float, priority:str="highest") -> dict:
        """Function for repaying all outstanding margin debt against specified currency. 

        Parameters
        ----------
        currency : str 
            Specific currency to repay liabilities against (e.g., BTC).
        size : float 
            Total currency sum to repay. Must be a multiple of currency max
            precision.
        priority : str 
            (Optional) Specify how to prioritize debt repayment.
            - Highest: Repay highest interest rate loans first
            - Soonest: Repay nearest term loans first 

        Returns
        -------
        dict
            Returns JSON dictionary with repayment confirmation and details.
        """
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
        url, headers = self._request("get", path, signed=True)
        resp = requests.request("get", url, headers=headers)
        return resp.json()["data"]

    def ohlcv(
        self, tickers:str or list, begin:dt.datetime or str, end:dt.datetime or str=None, 
        interval:str="1day", warning:bool=True,
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
            Start time for queried date range. May be given either as a datetime object
            or string. String format may include hours/minutes/seconds or may not
            String format examples: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
        end : str or datetime.datetime
            (Optional) Ending date for queried date range. This parameter has the same
            formatting rules and flexibility of param `begin`. If left unspecified, end 
            will default to the current UTC date and time stamp.
        interval : str
            Interval at which to return OHLCV data. Default: 1day
            Intervals: 1min, 3min, 5min, 15min, 30min, 1hour, 2hour, 4hour, 6hour, 
                8hour, 12hour, 1day, 1week
        progress_bar : bool 
            Flag to enable progress bar. Does not work in Jupyter notebooks yet
        msg : bool 
            Flag for turning on and off helper messages

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
                    logging.debug("Server requires 10 second timeout")
                    time.sleep(11)
                    logging.debug("Re-establishing stream . . . ")
                    resp = requests.request("get", url)
                    if resp.status_code == 429:
                        logging.debug("Server requires hard timeout: 3 minute delay.")
                        time.sleep(180)
                        logging.debug("Re-establishing stream . . . ")
                        resp = requests.request("get", url)
                        if resp.status_code == 429:
                            logging.debug("Server requires hard timeout: 5 minute delay.")
                            time.sleep(300)
                            logging.debug("Re-establishing stream . . . ")
                            resp = requests.request("get", url)
                        else:
                            pass
                else:
                    logging.error(f"Failed reponse. Returned code: {resp.status_code}")
                
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

    def get_order_history(self, symbol:str) -> pd.DataFrame:
        """Query API the 100 most recent filled trades for a specified symbol
        
        Parameters
        ----------
        symbol : str 
            Symbol to query order history for (e.g., BTC-USDT)

        Returns
        -------
        DataFrame
            Returns pandas DataFrame with order history details
        """
        path = f"market/histories?symbol={symbol.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp.json())
        resp = resp.json()
        try:
            df = pd.DataFrame(resp["data"])
        except KeyError:
            return logging.error("No message data received.")
        df["time"] = pd.to_datetime(df["time"], origin="unix")
        df.set_index("time", inplace=True)
        return df

    def symbols(self, pair:str or list=None) -> pd.DataFrame or pd.Series:
        """Query API for dataframe containing detailed list of trading pairs

        This is the primary trading pair detail endpoint for users. The returned values
        outline, in details, the trading parameters neccesary to successfully
        execute trades. Several other pair, currency, and market detail endpoints are available,
        but these endpoints primarily contain duplicate information to this detail or 
        offer information largely unrelated to trade execution.

        Notes
        -----
        There are several other currency detail endpoints: 
        * `.get_currencies()`
        * `.get_currency_detail()
        * `.all_tickers`
        * `.get_marginable_details()`
        
        Parameters
        ----------
        currency : str
            (Optional) Specify a single pair or list of pairs to query.
            If currency = None, return a dataframe of all trading pairs.

        Returns
        -------
        DataFrame or Series
            Returns pandas DataFrame with with detailed list of all traded pairs. 
            If a list of pairs is provided in the `currency` parameter, return a
            DataFrame containing only the specified pairs. If a single pair is 
            provided, return a pandas Series with the pair trade details.
        """
        path = "symbols"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp.status_code)
        resp = resp.json()
        df = pd.DataFrame(resp["data"]).set_index("symbol")
        if pair:
            try:
                df = df.loc[pair, :]
            except KeyError as e: 
                raise KeyError("Keys not found in list frame", e)
        return df

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
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
        if df.empty:
            raise ResponseError("No data returned.")
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
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp.status_code)
        resp = resp.json()["data"]
        if df.empty:
            ResponseError("No results for currency and term combination")
        df = pd.DataFrame(resp)
        return df

    def get_marginable_details(self) -> pd.DataFrame:
        """Obtain marginable securities with trade details"""
        path = "symbols"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp.status_code)
        resp = resp.json()
        df = pd.DataFrame(resp["data"])
        marginTrue = df["isMarginEnabled"] == True
        tradingEnabled = df["enableTrading"] == True
        df = df[marginTrue & tradingEnabled]
        return df

    def get_trade_history(self, pair:str) -> pd.DataFrame:
        """Query API for most recent 100 filled trades for target pair

        Parameters
        ----------
        pair : str 
            Target currency pair to query (e.g., BTC-USDT)
        
        Returns
        -------
        DataFrame
            Returns pandas Dataframe with filled trade details keyed to timestamp
        """
        path = f"market/histories?symbol={pair.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp.status_code)
        resp = resp.json()
        df = pd.DataFrame(resp["data"])
        df["time"] = pd.to_datetime(df["time"], origin="unix")
        df.set_index("time", inplace=True)
        return df

    def get_markets(self) -> list:
        """Returns list of markets on KuCoin
        
        Returns
        -------
        list
            Returns list of all KuCoin markets (i.e., NFT)
        """
        path = "markets"
        url = self._request("get", path)
        resp = requests.request("get", url)
        return resp.json()["data"]

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
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        return pd.Series(resp)

    def get_ticker_spreads(self, pair:str) -> pd.Series:
        """Obtain best bid-ask spread details for a specified pair"""
        path = f"market/orderbook/level1?symbol={pair.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        if resp is None:
            raise ResponseError("No data returned for pair.")
        return pd.Series(resp)

    def all_tickers(self, round:int=7) -> pd.DataFrame:
        """Query entire market for 24h trading statistics
        
        Parameters
        ----------
        round : int 
            Round price data to n decimal places. Used to supress 
            scientific notation on output. Set to None to disable

        Returns
        -------
        DataFrame
            Returns pandas DataFrame containing recent trade data for entire market
        """
        path = "market/allTickers"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp["ticker"]).drop("symbolName", axis=1)
        df.set_index("symbol", inplace=True)
        df = df.astype(float)
        if round:
            df = df.round(round)
        return df

    def get_currencies(self) -> pd.DataFrame:
        """Query API list of general currency info including precision and marginability"""
        path = "currencies"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
        df.set_index("currency", inplace=True)
        return df

    def get_currency_detail(self, currency:str) -> pd.Series:
        """Query API for target currency including precision and marginability
        
        Parameters
        ----------
        currency : str 
            Target currency to obtain details (e.g. BTC)

        Returns
        -------
        pd.Series
            Return pandas Series with target currency detail
        """
        path = f"currencies/{currency.upper()}"
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        return pd.Series(resp)

    def get_full_detail(self, currency):
        """Currently not fully implemented

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
        url = self._request("get", path, api_version=self.API_VERSION2)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        df = pd.DataFrame(resp)
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
        url = self._request("get", path)
        resp = requests.request("get", url)
        resp = resp.json()["data"]
        return pd.Series(resp, name=f"{fiat} Denominated")

    def marginable_currency_info(self) -> pd.DataFrame:
        """Get marginable currencies with general (non-trade) details
        
        Returns
        -------
        DataFrame
            Returns pandas DataFrame with non-trade related details for all
            marginable details.
        """
        df = self.get_currencies()
        try:
            df = df[df["isMarginEnabled"] == True]
        except KeyError:
            raise ResponseError("No message data received.")
        return df

    def margin_config(self) -> dict:
        """Pull margin configuration as JSON dictionary"""
        path = "margin/config"
        url = self._request("get", path)
        resp = requests.request("get", url)
        return resp.json()["data"]

    def get_socket_detail(self, private=False):
        """Get socket details for private or public endpoints"""
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
            logging.error(resp.status_code)
        return resp.json()["data"]

    def get_server_time(self, datetime_output:bool=False) -> int:
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
        datetime_output : bool 
            (Optional) If true, convert UNIX epoch integer to datetime object
        
        Returns
        -------
        int or datetime.datetime
            Returns time to the millisecond either as a UNIX epoch or datetime object
        """
        path = "timestamp"
        url = self._request("get", path)
        resp = requests.request("get", url)
        if resp.status_code != 200:
            return logging.error(resp.status_code)
        resp = resp.json()["data"]
        if datetime_output:
            resp = dt.datetime.utcfromtimestamp(
                int(resp) / 1000
            )
        return resp

    def limit_order(
        self, symbol:str, side:str, price:float, size:float=None, 
        funds:float=None, client_oid:int=None, remark:str=None, 
        tif:str="GTC", stp:str=None, cancel_after:int=None, 
        postonly:bool=False, hidden:bool=False, iceberg:bool=None, 
        visible_size:float=None,
    ):
        """"API command for placing limit trades in the trade account (non-margin). 

        Parameters
        ----------
        symbol : str
            Pair on which to execute trade (e.g., BTC-USDT)
        side : str
            Side on which to execute trade.
            Options: buy or sell
        price : float 
            Trades must be executed at this price or better
        size : float
            (Optional) Size in base currency to buy or sell.
            | Size indicates the amount of base currency to buy or sell
            | Size must be above baseMinSize and below baseMaxSize
            | Size must be specified in baseIncrement symbol units
            | Size must be a positive float value
            | Note: User is required to either specify size or funds. 
        funds : float
            (Optional) Amount of funds in quote currency to buy or sell.
            | Note: User is required to either specify size or funds.
            | Funds indicates the amount of price [quote] currency to buy or sell.
            | Funds must be above quoteMinSize and below quoteMaxSize
            | Size must be specified in quoteIncrement symbol units
        client_oid : int
            (Optional) Unique order ID for identification of orders. 
            Defaults to integer nonce based on unix epoch if unspecified.
        remark : str
            (Optional) Add a remark to the order execution. Remarks may not 
            exceed 100 utf-8 characters in length.
        stp : str
            (Optional) Self-trade prevention parameters. Primarily used by market makers.
            Options: CN, CO, CB, or DC. Defaults to None.
        tif : str
            Dictate time in force order types. If unspecified order will be good-till-cancel. 
            Order types: GTC [default], GTT, IOC, or FOK
        cancel_after : int
            Cancel after n seconds. `cancel_after` requires that `tif` = GTT.
        postonly : bool 
            If postonly is true, orders may only be executed at the maker fee. 
            Orders that would receive taker will be rejected.
        hidden : bool 
            If true, orders will not be publicly visible i.e. will not appear in orderbook.
        
        Returns
        -------
        dict
            JSON dict with order execution details
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
        """API command for executing market orders in the trade account (non-margin).
        
        Parameters
        ----------
        symbol : str
            Pair on which to execute trade (e.g., BTC-USDT)
        side : str
            Side on which to execute trade.
            Options: buy or sell
        size : float
            (Optional) Size in base currency to buy or sell.
            | Size indicates the amount of base currency to buy or sell
            | Size must be above baseMinSize and below baseMaxSize
            | Size must be specified in baseIncrement symbol units
            | Size must be a positive float value
            | Note: User is required to either specify size or funds. 
        funds : float
            (Optional) Amount of funds in quote currency to buy or sell.
            | Note: User is required to either specify size or funds.
            | Funds indicates the amount of price [quote] currency to buy or sell.
            | Funds must be above quoteMinSize and below quoteMaxSize
            | Size must be specified in quoteIncrement symbol units
        client_oid : int
            (Optional) Unique order ID for identification of orders. 
            Defaults to integer nonce based on unix epoch if unspecified.
        remark : str
            (Optional) Add a remark to the order execution. Remarks may not 
            exceed 100 utf-8 characters in length.
        stp : str
            (Optional) Self-trade prevention parameters. Primarily used by market makers.
            Options: CN, CO, CB, or DC. Defaults to None.

        Returns
        -------
        dict
            JSON dict with order execution details
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
        """API command for placing market trades on margin. 

        Notes
        -----
            Due to a glitch in KuCoin's API handling of autoborrowed funds, the server
            will sometimes return the following:
                `{'code': '300000', 'msg': 'Order funds invalid.'}`
            This issue arises with certain combinations of side, size/funds and only 
            while autoborrow is true. I am currently working on a way around this, but 
            as the glitch appears to be server side there may be no elegant solution.
            Users are recommended to either use the `margin_limit_order` function which works
            as intended or to manually borrow funds and set autoborrow to False.

        Parameters
        ----------
        symbol : str
            Pair on which to execute trade (e.g., BTC-USDT)
        side : str
            Side on which to execute trade.
            Options: buy or sell
        size : float
            (Optional) Size in base currency to buy or sell.
            | Size indicates the amount of base currency to buy or sell
            | Size must be above baseMinSize and below baseMaxSize
            | Size must be specified in baseIncrement symbol units
            | Size must be a positive float value
            | Note: User is required to either specify size or funds. 
        funds : float
            (Optional) Amount of funds in quote currency to buy or sell.
            | Note: User is required to either specify size or funds.
            | Funds indicates the amount of price [quote] currency to buy or sell.
            | Funds must be above quoteMinSize and below quoteMaxSize
            | Size must be specified in quoteIncrement symbol units
        client_oid : int
            (Optional) Unique order ID for identification of orders. 
            Defaults to integer nonce based on unix epoch if unspecified.
        remark : str
            (Optional) Add a remark to the order execution. Remarks may not 
            exceed 100 utf-8 characters in length.
        stp : str
            (Optional) Self-trade prevention parameters. Primarily used by market makers.
            Options: CN, CO, CB, or DC. Defaults to None.
        mode : str
            User may trade on cross margin or isolated margin. 
            Default mode = cross; Options: cross or isolated
        autoborrow : bool 
            If true, system will automatically borrow at the optimal interest rate prior 
            to placing the requested order. 

        Returns
        -------
        dict
            JSON dict with order execution details
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
        """API command for placing margin limit trades. 

        Parameters
        ----------
        symbol : str
            Pair on which to execute trade (e.g., BTC-USDT)
        side : str
            Side on which to execute trade.
            Options: buy or sell
        price : float 
            Trades must be executed at this price or better
        size : float
            (Optional) Size in base currency to buy or sell.
            | Size indicates the amount of base currency to buy or sell
            | Size must be above baseMinSize and below baseMaxSize
            | Size must be specified in baseIncrement symbol units
            | Size must be a positive float value
            | Note: User is required to either specify size or funds. 
        funds : float
            (Optional) Amount of funds in quote currency to buy or sell.
            | Note: User is required to either specify size or funds.
            | Funds indicates the amount of price [quote] currency to buy or sell.
            | Funds must be above quoteMinSize and below quoteMaxSize
            | Size must be specified in quoteIncrement symbol units
        client_oid : int
            (Optional) Unique order ID for identification of orders. 
            Defaults to integer nonce based on unix epoch if unspecified.
        remark : str
            (Optional) Add a remark to the order execution. Remarks may not 
            exceed 100 utf-8 characters in length.
        stp : str
            (Optional) Self-trade prevention parameters. Primarily used by market makers.
            Options: CN, CO, CB, or DC. Defaults to None.
        mode : str
            User may trade on cross margin or isolated margin. 
            Default mode = cross; Options: cross or isolated
        autoborrow : bool 
            If true, system will automatically borrow at the optimal interest rate prior 
            to placing the requested order. 
        tif : str
            Dictate time in force order types. If unspecified order will be good-till-cancel. 
            Order types: GTC [default], GTT, IOC, or FOK
        cancel_after : int
            Cancel after n seconds. `cancel_after` requires that `tif` = GTT.
        postonly : bool 
            If postonly is true, orders may only be executed at the maker fee. 
            Orders that would receive taker will be rejected.
        hidden : bool 
            If true, orders will not be publicly visible i.e. will not appear in orderbook.
        iceberg : bool
            If true, only a portion of the order will be visible in the orderbook. Use
            `visible_size` to control percentage of order size visible.
        visible_size : float
            If `iceberg` is true, use this to set % of order visible in orderbook. Note that
            more than 1/20th of order must be visible in the orderbook or the order will be 
            rejected. To hide the full order use `hidden` parameter.

        Returns
        -------
        dict
            JSON dict with order execution details
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
