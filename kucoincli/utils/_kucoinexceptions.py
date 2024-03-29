
# Custom defined KuCoin specific exceptions
class Error(Exception):
    """Base class for other exceptions"""
    pass

class KucoinResponseError(Error):
    """Raise when kucoin API returns empty data field"""
    pass

class HTTPError(Error):
    """Raise when kucoin API returns HTTP response != 200"""
    pass

class MissingDataError(Error):
    """Raise when data is missing or undelivered"""
    pass