import logging
import requests
import functools
import pandas as pd
import datetime as dt
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

    def account_overview(self, currency='XBT'):
        """Pull general account overview for futures trading"""
        path = f'account-overview?currency={currency}'
        resp = self._request('get', path, signed=True)
        ser = pd.Series(resp['data'])
        ser.iloc[0:-1] = ser.iloc[0:-1].astype(float)
        return ser

    def active_contracts(self, contracts=None):
        """Obtain list of active contracts"""
        path = "contracts/active"
        resp = self._request('get', path)
        df = pd.DataFrame(resp['data'])
        df = df.set_index('symbol')
        return df

    def current_funding_rate(self, symbol):
        """Obtain current funding rate details"""
        path = f'funding-rate/{symbol.upper()}/current'
        resp = self._request('get', path)
        if not resp['data']:
            raise KucoinResponseError(f'Not response returned. Is {symbol} a valid contract?')
        ser = pd.Series(resp['data'])
        ser.iloc[1:] = ser.iloc[1:].astype(float)
        return ser

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

    def server_status(self) -> dict:
        """Get KuCoin service stats (open, closed, cancelonly)"""
        path = "status"
        resp = self._request("get", path)
        return resp["data"]
