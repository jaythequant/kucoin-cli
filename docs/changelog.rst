=========
Changelog
=========

-----
1.4.7
-----
Release Date: Unreleased

Core functionality of the API is complete. The dev branch contains the framework for the futures API which will eventually be merged into the main branch. As such, I will turning focus to
documentation with extended examples and detailed walkthroughs. Visit the Examples page on readthedocs to get some implementation tips on how to use this library, then check out the `example`
folder on Github to try the example scripts out for yourself.

Quality of Life
^^^^^^^^^^^^^^^
* `order_history`: Added a calculated column called `avgPrice`. `avgPrice` is the average executed price calculated as `dealSize` / `dealFunds`. If the order did not execute, `avgPrice=NaN`.
* `repay`: Much like `order` and `borrow`, `repay` now provides improved responses. Core return data for responses is still intacted (so no existing programs will break). See docstrings for
  further details and an example output.

Bug Fixes
^^^^^^^^^
* During super-extended webscraping sessions (those put on by the `pipe` module), an error could occur in which the program was intended to sleep for 10 minutes, but failed to do so. This
  has now been corrected.

-----
1.4.6
-----
Release Date: 2022-10-28

**POTENTIALLY BREAKING CHANGE**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* `cancel_order`: Previously `cancel_order` returned a list of order IDs that were cancelled and logged an error message when an order failed to cancel. This function will now return a dictionary
  with the following format:

  .. code-block:: python

    {
      '200000': 
      [
          '635948e592d8ed0001929223',
          '5da59f5ef943c033b2b643e4,
      ],
      'errors': []
    }

**If you have a system that performs validation on orders cancellations based on the `cancel_order` response it will break**.

Futures and Async classes were moved from main branch to dev branch. These features may be in development for some time and as such they have been removed.

New Features
^^^^^^^^^^^^
* `cancel_lend_order`: Cancel outstanding lending orders across your account. Alternatively, cancel a single order or list of orders by tradeId.
* `set_auto_lend`: Toggle autolend features on or off for specified currency. Check out `the auto lend documentation <https://docs.kucoin.com/#set-auto-lend>`_ **before** you use this feature.

Quality of Life
^^^^^^^^^^^^^^^
* `order`: Significant improvements were made to `order` responses. By default, KuCoin order confirmations contain only a status code and either a tradeId or
  message field (dependent on whether the trade was accepted or rejected). `order` will now return the same confirmation with additional information surrounding
  order parameters. This change will not break any legacy systems as the response will still come in the same format. Simply more information has been added. See 
  the docstring for an example of what new reponses look like.
* `borrow`: In the same vein as `order`, improved response's have been added to `borrow`. For an example, check the docstrings.
* `lend`: Lend has also received updated response features. See the docstring for an example.

Bug Fixes
^^^^^^^^^
* During multi-day REST API scraping sessions, KuCoin would eventually refuse to send a HTTP response. This error is now handled via a 10 minute timeout with a log messages
  printed at the debug logging level.

-----
1.4.5
-----
Release Date: 2022-10-23

Futures API support is currently in development. Current releases may be unstable or lack proper documentation. Explore features at your own risk.

New Features
^^^^^^^^^^^^
* `mark_price`: Use this function for obtaining KuCoin official mark prices.
* `consumer`: Added basic websocket consumer processing websocket message and handling keep alive pings

Quality of Life
^^^^^^^^^^^^^^^
* `pull_by_oid` and `pull_by_cid`: As appropriate, string values are recast to float automatically. `unix` boolean argument has been added to both functions. Finally, a 
  `KuCoinResponseError` is now raised if an invalid OID/CID is passed to the argument.
* `order_history`: With the addition of `pull_by_oid` and `pull_by_cid` as premier live trading endpoints, `order_history`'s primary purpose is for evaluation of trade results.
  As such, consolidated outputs are more often a better view. `consolidated` view will now be the default.
* `margin_balance`: Where appropriate, columns are now automatically recast from string to float.
* `get_stats`: Where appropriate, columns are now automatically recast from string to float.
* `order_history`: Symbols passed to `symbols` argument are no longer case sensitive

-----
1.4.4
-----
Release Date: 2022-10-01

Added two new functions:

* `pull_by_oid`: Pull an active or inactive order by its KuCoin autogenerated order ID. Order details are returned as a pandas Series. This is the lowest latency, most consistent way to 
  obtain order details.
* `pull_by_cid`: Very similar to `pull_by_oid` above, this function is a low latency, consistent function for pulling order details by specifying a user-generated order ID. User-generated
  order ID's can be attached to orders via the `oid` argument of the `orders` function.

With the addition of these functions, it is highly recommended that users remove `order_history` or `recent_orders` functions from their algorithms in favor of one of the new pull functions.
Both `order_history` and `recent_orders` suffer from slow execution time and significant lag in updating new orders to the response by KuCoin.

Bug Fixes
^^^^^^^^^
* `cancel_order`: Fixed error in appending cancelled order ID to list of order IDs when several CID/OID order existed, but one did not.

-----
1.4.3
-----
Release Date: 2022-09-27

Added exception handling for ConnectionError when submitting POST request. This issue was raised due to an idled request session and effected primarily macOS.

-----
1.4.2
-----
Release Date: 2022-09-25

In `ohlcv`, `begin` argument has officially been deprecated.

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
* `symbols`: Reversed previous index column change from `name` to `symbol`. This change will ensure naming consistency between other functions such as OHLCV.
  New index column is `symbol`. Be aware that `name` is the trading pair name and may differ from `symbol`.

-----
1.4.1
-----
Release Date: 2022-09-22

Bugs Fixes
^^^^^^^^^^
* `.cancel_order`: A few errors in parsing responses were discovered and fixed.

Quality of Life
^^^^^^^^^^^^^^^
* `get_level1_orderbook`: Now has `unix` argument, consistent with other functions (deprecated `time` argument). Output is now automatically cast to 
  float values (previously returned strings).
* `order_history`: Changed default for `consolidated` to `False` (previously defaulted to `True`). I expected that consolidated responses would be more
  useful, but found that in live execution, I was consistently setting the argument to `False`.

---------------
1.4.0 and 1.3.9
---------------
Release Date: 2022-09-21

Rolled changelog entries 1.4.0 and 1.3.9 together as 1.3.9 was primarily bug-squashing.

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
* `orders`: Thanks to @lithium-bot on Github, an issue was corrected with isolated margin order submission.

---------------
1.3.7 and 1.3.8
---------------
Release Date: 2022-09-19

Rolled changelog entries 1.3.7 and 1.3.8 together as 1.3.7 contained only minor changes

* `recent_orders`: Added `unix` boolean argument. If `unix=True`, datetimes will be returned in unix epochs at millisecond granularity 
* `order_history`: Added extremely detailed endpoint for obtaining order history infromation. See `.order_history` docstring for full details. 

-----
1.3.6
-----
Release Date: 2022-09-18

Significantly updated `.margin_balance` function. Use this endpoint detailed information surrounding margin debts
against the user's accounts.

Additional updates:

* Improved overal documentation
* Deprecated `.get_outstanding_balance` as it was extraneous once `.margin_balance` was overhauled.

-----
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

-----
1.1.0
-----
Release Date: 2022-06-08

* Completely reworked `kucoincli.pipe`
  
  * Made `schema` optional
  * Added functionality 