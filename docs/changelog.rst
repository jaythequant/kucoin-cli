Changelog
=========

1.4.2
-----
Release Date:

In `ohlcv`, begin has been officially deprecated as an argument.

Quality of Life
^^^^^^^^^^^^^^^
* `get_server_time`: Added `unix` boolean argument and added deprecation warning for old `format` argument. In a later release, `format` will be deprecated in
  favor of the new argument.
* `order_history`: Added `unix` boolean argument. Set `unix=True` to return timestamps in unix epochs. Default behavior will still return timestamps in as
  datetime format. For *very* minor performance increases in live trading, set `unix=True` to avoid the call to `pd.to_datetime`.
* `transfer`: Added 'spot' and 'cross' as valid inputs for `source_acc` and `dest_acc` arguments. These inputs are more descriptive than the previous 'trade'
  and 'margin' terms. Note that 'trade' and 'margin' are still supported and are now synonymous with 'spot' and 'cross' respectively.
* `cancel_order`: Now supports 'spot' as an `acc_type` argument input. The prior 'trade' input is still supported and is synonymous with 'spot'.
* `margin_balance`: `tradeId` column is now automatically set as index. Previously, the returned dataframe had no set index.
* `symbols`: Reversed previous index column change from `name` to `symbol`. This change will ensure naming consitency between other functions such as OHLCV.
  New index column is `symbol`. Be aware that `name` is the trading pair name and may differ from `symbol`.

1.4.1
-----
Release Date: 2022-09-22

Bugs Fixes
^^^^^^^^^^
* `.cancel_order`: A few errors in parsing responses were discovered and fixed.

Quality of Life
^^^^^^^^^^^^^^^
* `get_level1_orderbook`: Not has `unix` argument, consistent with other functions (deprecated `time` argument). Output is now automatically cast to 
  float values (previously returned strings).
* `order_history`: Changed `consolidated` to default to `False` (previously defaulted to `True`). I expected that consolidated responses would be more
  useful, but found that in live execution, I was consistently setting it to `False`.

1.4.0 and 1.3.9
---------------
Release Date: 2022-09-21

Rolled changelog entry together as 1.39 was primarily bug-squashing.

New Features 
^^^^^^^^^^^^
* Added support for isolated margin in the `.transfer` function
  
  * Transferring into and out of isolated margin accounts requires an extra argument (`from_pair` or `to_pair`, respectively).
    Please review the docstrings or KuCoin API documentation for details.

* Completely overhauled the `.cancel_order` function. `.cancel_order` is now a one-stop shop for order cancellation. The function
  has a comprehensive docstring attached for user reference. Use this function to:

  * Cancel all orders associated with a trading pair or list of trading pairs.
  * Submit cancellations within all three major markets: spot, cross, and isolated.
  * Cancel orders targetted on client IDs or vanilla IDs.
  * Mix and match cancellation methods to submit large batch cancellations (i.e., cancel 100 order IDs at a time by passing a list to
    to `oid` or `cid` arguments or cancel all orders related to the BTC-USDT pair while simultaneously cancelling several
    order IDs associated with other trading pairs.

* Improved `lending_rate` endpoint. Also, this endpoint had an issue with error handling previous and this has been fixed.

Quality of Life
^^^^^^^^^^^^^^^
* Broadly improved docstrings across several functions.
* Several functions used to return either a DataFrame or (when possible) a pandas Series. I found that this behavior was disruptive
  in a few of my live-trading algorithms and as such it has been removed in some functions.
* Default order type in `borrow` changed from FOK to IOC. I have found IOC to be more broadly useful.

Bugs Fixes
^^^^^^^^^^
* `.orders`: Thanks to @lithium-bot on Github, an issue was corrected with isolated margin order submission.

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