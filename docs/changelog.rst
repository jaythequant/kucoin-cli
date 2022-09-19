Changelog
=========

1.3.7 and 1.3.8
---------------
Release Date: 2022-09-19

Rolled changelog entry together as 1.3.7 contained only minor changes

* Added `unix` argument to `.recent_orders`. If `unix=True`, datetimes will be returned in unix epochs at millisecond granularity 
* Added extremely detailed endpoint for obtaining order history infromation. See `.order_history` docstring for full details. 

1.3.6
-----
Release Date: 2022-09-18

Significantly updated `.margin_balance` function. Use this endpoint detailed information surrounding margin debts
against the user's accounts.

Additional updates:

* Improved documentation
* Deprecated `.get_outstanding_balance` as it was extraneous once `.margin_balance` was overhauled.

1.3.5
-----
Release Date: 2022-09-18

* OHLCV (and by extension the pipeline module) raised errors when querying a date range for a ticker that contained no values. In the event that no price 
  data is available for a ticker in the requested time interval, the function will now return an empty DataFrame. This will correct corner-case issues.
* Comprehensive support has been added for cancelling orders. See `cancel_order` function.
* Comprehensive support for listing currently activate orders was added. See `list_orders` function.
* In `symbols` function, the index columns was changed to 'name' from 'symbol'. Occasionally, ticker names change (symbol names never change). This can cause 
  confusion if the index is the old name (an example of this being BSV which used to be BCHSV). To access the immutable (potentially older names), 
  simply review the 'symbol' column.
* Several functions with filter arguments used to accept only strings, but now accept lists and strings. No functionality was changed, this is purely a QoL 
  improvement.
* OHLCV function now accepts `start` argument in addition to `begin`. The arguments provide identical functionality. `begin` is confusing to work with as 
  other popular data acquisition tools (e.g. yfinance) use `start` arguments. Please switch existing tools to `start` where applicable. The `begin` argument 
  will now raise a deprecation warning and will be removed from the kucoincli API at some point in the future.
* `get_marginable_pairs` was officially deprecated. Use `symbols` with `marginable=True` to replicate the deprecated function.

1.1.0
-----
Release Date: 2022-06-08
* Completely reworked `kucoincli.pipe`
    * Made `schema` optional
    * Added functionality 