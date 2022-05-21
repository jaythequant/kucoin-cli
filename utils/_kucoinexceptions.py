
# Custom defined KuCoin specific exceptions
class Error(Exception):
    """Base class for other exceptions"""
    pass

class ResponseError(Error):
    """Raise when kucoin API returns empty data field"""
    pass

class HTTPError(Error):
    """Raise when kucoin API returns HTTP response != 200"""
    pass
