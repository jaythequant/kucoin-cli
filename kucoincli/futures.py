import logging
import requests
import functools
import time
import warnings
import pandas as pd
import datetime as dt
from utils._utils import _parse_date, _parse_interval
from kucoincli.client import BaseClient
from kucoincli.utils._kucoinexceptions import KucoinResponseError


class FuturesClient(BaseClient):
    """KuCoin Futures REST API wrapper -> https://docs.kucoin.com/futures/#general

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
    """

    REST_API_URL = "https://api-futures.kucoin.com"
    API_VERSION = "v1"
    API_VERSION2 = "v2"
    API_VERSION3 = "v3"

    def __init__(self, api_key=None, api_secret=None, api_passphrase=None, requests_params=None):

        BaseClient.__init__(self, api_key, api_secret, api_passphrase)

        self.logger = logging.getLogger(__name__)

        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.API_PASSPHRASE = api_passphrase

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

    @staticmethod
    def __format_contract_list(contracts):
        """Clean up formatting for list of contracts"""
        contracts = [contracts] if not isinstance(contracts, (list, tuple)) else contracts
        contracts = [contract.upper() for contract in contracts]
        return contracts

    def account_overview(self, currency:str='XBT') -> pd.Series:
        """Pull general account overview for futures trading"""
        path = f'account-overview?currency={currency}'
        resp = self._request('get', path, signed=True)
        ser = pd.Series(resp['data'])
        ser.iloc[0:-1] = ser.iloc[0:-1].astype(float)
        return ser

    def all_contracts(self, contracts:str or list =None) -> pd.DataFrame:
        """Obtain list of active contracts with relevant trade details
        
        Parameters
        ----------
        contracts : str or list, optional
            Return only specified contract or contracts.

        Returns
        -------
        DataFrame or Series
            Return contract details for all active contracts as a pandas 
            DataFrame (for multiple contracts) or Series (for a single contract).
        """
        path = "contracts/active"
        resp = self._request('get', path)
        df = pd.DataFrame(resp['data'])
        df = df.set_index('symbol')
        if contracts:
            contracts = self.__format_contract_list(contracts)
            df = df[df.index.isin(contracts)]
        return df.squeeze()

    def get_stats(self, contract:str, unix:bool=True) -> pd.Series:
        """Query API for OHLC(V) figures and assorted statistics on specified pair

        Parameters
        ----------
        contract: str 
            contract to obtain details for (e.g., XBTUSDM)
        
        Returns
        -------
        Series
            Returns pandas Series containing details for target currency
        """
        path = f'ticker?symbol={contract.upper()}'
        resp = self._request('get', path)
        try:
            ser = pd.Series(resp['data'])
        except KeyError:
            raise KucoinResponseError(
                f'No data returned. Is {contract.upper()} a valid contract?'
            )
        if not unix:
            ser.ts = pd.to_datetime(ser.ts)
        ser = ser.rename(index={'ts': 'lastTrade'})
        return ser

    def current_funding_rate(self, symbol):
        """Obtain current funding rate details"""
        path = f'funding-rate/{symbol.upper()}/current'
        resp = self._request('get', path)
        if not resp['data']:
            raise KucoinResponseError(f'Not response returned. Is {symbol} a valid contract?')
        ser = pd.Series(resp['data'])
        ser.iloc[1:] = ser.iloc[1:].astype(float)
        return ser

    def get_server_time(self, unix=True) -> int:
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
        unix : bool, optional
            If `unix=True`, return server time as Unix epoch with millisecond accuracy. Else,
            return datetime object.
        
        Returns
        -------
        int or datetime.datetime
            Returns time to the millisecond either as a UNIX epoch or datetime object
        """
        path = "timestamp"
        resp = self._request("get", path)
        resp = resp["data"]
        if not unix:
            resp = dt.datetime.utcfromtimestamp(
                int(resp) / 1000
            )
        return resp

    def get_trade_history(self, contract:str, unix=False, ascending:bool=False) -> pd.DataFrame:
        """Query API for most recent 100 filled trades for target pair

        Parameters
        ----------
        contract : str 
            Target currency pair to query (e.g., XBTUSDM)
        unix : bool, optional
            If `unix=False` [default], DataFrame index will be returned as datetimes. Else,
            index will be returned as unix epochs with millisecond precision.
        ascending : bool, optional
            Reverse sorting order of returned dataframe (default sorts newest to oldest)
        
        Returns
        -------
        DataFrame
            Returns pandas Dataframe with filled trade details keyed to timestamp
        """
        path = f'trade/history?symbol={contract.upper()}'
        resp = self._request('get', path)
        if not resp['data']:
            raise KucoinResponseError(
                f'No data returned. Is {contract.upper()} a valid symbol?'
            )
        df = pd.DataFrame(resp['data']).set_index('ts')
        df[['size', 'price']] = df[['size', 'price']].astype(float)
        if not unix:
            df.index = pd.to_datetime(df.index)
        df.index = df.index.rename('time')
        return df.sort_index(ascending=ascending)

    def server_status(self) -> dict:
        """Get KuCoin service stats (open, closed, cancelonly)"""
        path = "status"
        resp = self._request("get", path)
        return resp["data"]

    def ohlcv(
        self, contracts:str, start:dt.datetime or str=None, end:dt.datetime or str=None, 
        interval:str="1day", ascending:bool=True, warn:bool=True,
    ) -> pd.DataFrame:
        """Obtain historic OHLCV price data for futures contract
        
        Parameters
        ----------
        contracts : str or list
            Futures contract or list of contracts (e.g., XBTUSDT)
        start : str or datetime.datetime, optional
            Earliest time for queried date range. May be given either as a datetime object
            or string. String format may include hours/minutes/seconds or may not
            String format examples: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS". If no `start` is
            specified, function will returned 200 bars at `interval` granularity prior to the
            `end` datetime.
        end : str or datetime.datetime, optional
            Latest (most recent) date for queried date range. This parameter has the same
            formatting rules and flexibility as `start`. If left unspecified, end will default
            to the current UTC datetime.
        interval : str, optional
            Provide interval granularity for returned data. Default granularity is 1 day. 
            All possible intervals: `["1min", "5min", "15min", "30min", "1hour", 
            "2hour", "4hour", "8hour", "12hour", "1day", "1week"]`
        ascending : bool, optional
            If `ascending=True` [default], returned DataFrame will be in standard order. If `False`,
            data is returned in reverse chronological order.
        warn : bool, optional
            If `warn=True`, a warning will be raised if number of API calls is greater than 20
        
        Returns
        -------
        DataFrame
            Return pandas DataFrame with datetime index in `ascending` order.
        """
        granularity = {
            "1min": 1, "5min": 5, "15min": 15, "30min": 30, "1hour": 60, "2hour": 120,
            "4hour": 240, "8hour": 480, "12hour": 720, "1day": 1440, "1week": 10080,
        }
        
        base_path = 'kline/query'
        interval_granularity = granularity[interval]

        if start:
            start = _parse_date(start) if isinstance(start, str) else start
        end = _parse_date(end) if isinstance(end, str) else dt.datetime.utcnow()

        unix_ranges = []
        if start:
            paganated_ranges = _parse_interval(start, end, interval, 200)
            for b, e in paganated_ranges:
                b = int(time.mktime(b.timetuple()))
                e = int(time.mktime(e.timetuple()))
                unix_ranges.append((b, e))
        else:
            unix_end_ts = int(time.mktime(end.timetuple()))
            unix_start_ts = int(time.mktime(start.timetuple())) if start else None
            unix_ranges = [(unix_start_ts, unix_end_ts)]

        contracts = self.__format_contract_list(contracts)

        responses = []

        if warn:
            num_calls = len(unix_ranges) * len(contracts)
            if num_calls > 20:
                warnings.warn(f"""
                Endpoint will be queried {num_calls} times.
                    Server may require one or multiple timeouts
                """)

        for symbol in contracts:
            paths = []
            for start, end in unix_ranges:
                path = (
                    base_path + 
                    f"?symbol={symbol}" + 
                    f"&granularity={interval_granularity}" +
                    f"&to={end*1000}"
                )
                if start:
                    path += f"&from={start*1000}"
                paths.append(path)
            df_pages = []
            for path in paths:
                resp = self._request('get', path)
                if resp["code"] == '400100': # Handle invalid trading contracts
                    raise KucoinResponseError(f"No data returned. Is {symbol} a valid contract?")
                # If we receive a valid response code, but no data, then we have reached the end of the timeseries
                if resp["code"] == '200000' and not resp["data"]:
                    break
                df = pd.DataFrame(resp['data'], columns=[
                    'time', 'open', 'high', 'low', 'close', 'volume',
                ]).set_index('time')
                df.index = pd.to_datetime(df.index, unit='ms')
                df_pages.append(df)
            if len(df_pages) > 1:
                res = pd.concat(df_pages, axis=0)
                responses.append(res[~res.index.duplicated()])
            else:
                try:
                    responses.append(df_pages[0])
                except IndexError:
                    logging.debug(
                        "Valid ticker, but no price data available for this period."
                    )
                    responses.append(pd.DataFrame())
        
        if len(responses) > 1:
            df = pd.concat(responses, axis=1, keys=contracts)
        else:
            df = responses[0]
        return df.sort_index(ascending=ascending)

    def get_funding_rate(self, contract:str, unix:bool=False) -> pd.Series:
        """Obtain current funding rate for specified futures contract"""
        contract = contract.upper()
        path = f'funding-rate/{contract}/current'
        resp = self._request('get', path)
        try:
            ser = pd.Series(resp['data'])
        except KeyError:
            raise KucoinResponseError(
                f'No data returned. Is {contract} a valid contract?'
            )
        if not unix:
            ser.timePoint = pd.to_datetime(ser.timePoint, unit='ms')
        ser = ser.rename(index={
            'timePoint': 'time',
            'value': 'funding_rate',
            'predictedValue': 'predicted_rate'
        })
        ser.name = contract
        return ser

    def premium_index(self, contract:str):
        """Obtain list of premium indices for target contract"""
        path = f'premium/query?symbol={contract}'
        resp = self._request('get', path)
        return resp

    def orderbook(self, contract, depth=None):
        pass

    def interest_rates(self, contract):

        df = []
        path = f'interest/query?symbol={contract}'
        resp = self._request('get', path)
        df.append(resp)
        if resp['data']['hasMore']:
            path = f'interest/query?symbol={contract}&forward=true'
            resp = self._request('get', path)
            df.append(resp)
        return df

    def indices(self):
        pass