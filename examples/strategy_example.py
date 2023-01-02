"""

#### A quick look at setting up a naive SMA cross strategy. 
# 
# This is one the most popular example strategi
# While this strategy won't work in the real world (at least we have no reason to believe
# it will). The code should give you the blueprints of how to bring your own strategy
# to life.

# To learn more about SMA cross strategies review the following resources:
# * https://www.cmcmarkets.com/en/trading-guides/trade-on-simple-moving-average#:~:text=SMA%20crossover,above%20its%20long%2Dterm%20SMA.
# * https://en.wikipedia.org/wiki/Moving_average_crossover

"""

# First step as always: import some libraries
from kucoincli.client import Client
from pprint import pformat
import datetime as dt
import pandas as pd
import logging
import re
import math
import time

# Before we get started let's setup a custom error class. We'll raise this exception whenever
# data is invalidated throughout our strategy execution process.
class DataError(Exception):
    """Raise this error when data has been found to be invalid"""
    pass

# Typically, you will want to create a strategy class and inherit the KCI Client
# Think of this process as extended the base functionality than Kucoin-Cli provides
class SMACross(Client):
    """Basic SMA cross strategy execution class"""

    def __init__(
        self, asset, api_key, api_secret, api_passphrase, fast_sma=50, slow_sma=200, 
        interval='1hour', order_size=10,
    ):
        """Input an asset and trade authorized API parameters to initialize the object"""
        # Initialize our client. This will give us full access to KCI functions for execution
        Client.__init__(api_key, api_secret, api_passphrase)

        # Lets add some order management variables
        self.asset = asset.upper()
        self.fast = fast_sma
        self.slow = slow_sma
        self.interval = interval
        self.pdtime = self.__interval_to_T(interval)
        self.position = None
        self.size = order_size
        self.increment = self.symbols(asset).baseIncrement

    # This is just a helper function that will take e.g., '1hour' and convert it into '60T'
    # Formating time values as `minutes`T is how pandas likes to work with time increments,
    # so this step is going to be useful as we want to do things like reindex a dataframe.
    @staticmethod
    def __interval_to_T(interval):
        """Convert a string of interval text to minutes with "T" time that pandas can use"""
        n = int(re.findall(r'\d+', interval)[0])
        val = re.sub(r"\d+", "", interval)
        granularities = {
            'minute': 1,
            'hour': 60,
            'day': 1440,
            'week': 10_080,
        }
        m = granularities.get(val)
        T = f'{n*m}T'
        return T

    # This helper function will round our asset sale increment to the right size
    @staticmethod
    def __round_decimal_down(number, decimals):
        """Returns a value rounded down to a specific number of decimal places."""
        if decimals == 0:
            return math.ceil(number)
        factor = 10 ** decimals
        return math.floor(number * factor) / factor

    # I like to add a wrapper function on top of the basic order functionality.
    # Essentially, this just let's us tweak order default parameters without
    # having to type it in every time.
    def _create_market_order(self, side, size):
        """Thin-wrapper around Kucoin-Cli `order` function"""
        oid = self._generate_oid() # Generate an OID to tag the order
        if side == 'buy':
            return self.order(
                symbol=self.asset,
                side=side,
                funds=size,
                type='market',
                oid=oid,
            )
        if side == 'sell':
            return self.order(
                symbol=self.asset,
                side=side,
                size=size,
                type='market',
                oid=oid,
            )

    # Lets add a way to "watermark" orders placed via this strategy. When we go back to
    # review execution, we can filter OID by either the asset name or the 'SMACROSS' string.
    def _generate_oid(self):
        """Make a unique OID that way we can review our order history logs later"""
        return f'{self.asset.replace("-", "")}SMACROSS{time.time()}'

    def _acquire_data(self):
        """Acquire historic OHLCV data"""
        # Pick-up the current UTC datetime and calulate our time offset for historic data acquisition.
        # For example purposes, we will calculate our fast and slow SMA based on a 200-day and 50-day 
        # lookbacks. Obviously we could use any arbitrary number and we'd probably want to come into 
        # the strategy with some level of prior hyperparameter tuning.
        ts = dt.datetime.utcnow()
        offset_1 = ts - dt.timedelta(days=self.slow)
        df = self.ohlcv(
            self.asset, 
            start=offset_1,
            interval=self.interval
        )
        # Lets just do a wee bit of data validation and processing
        if df.shape[0] != 4800:
            # If data is missing indices, we will go ahead and reindex our dataframe 
            # filling missing rows with NaN values. As long as those NaN rows are limited
            # to a single isolated missing value, interpolated the information.
            idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq=self.pdtime)
            df = df.reindex(idx)
            df = df.interpolate(limit=1)
        # We really only care about validity in the close data as that's what we will be performing
        # analysis on. As such, let's make sure we don't have any pesky missing values.
        if df.close.isna().any():
            # If we do have missing values, raise a DataError to hault execution!
            raise DataError(
                'To many NaN values present in data. Data returned is not sound for analysis'
            )
        return df # If all goes well, return our historic data

    # Now that we have the data, we need to process the data into something that we can trade on.
    # The basics of the SMA cross, as explained in more detail above, require a "fast" simple moving
    # average and a "slow" simple moving average. This function will calculate both
    def _process_data(self, df):
        """Process OHLCV data and extract statistics/trade signals"""
        # The fast offset is calculated as `self.fast` days prior to the maximum value in the pandas
        # DataFrame datetime index.
        # Note that we don't calculate a slow offet. This is because the DataFrame we queried was already
        # the "slow" SMA length (i.e., 200-days). With this in mind, our slow SMA is just the mean close price
        # of the entire dataframe.
        fast_offset = df.index.max() - dt.timedelta(days=self.fast)
        slow_sma = df.close.mean() # Get our slow SMA
        fast_sma = df.loc[fast_offset:].close.mean() # Slice dataframe and calculate the fast SMA
        return slow_sma, fast_sma

    # Now that we've calculated our updated fast and slow SMA, let's run them through
    # this signal processing function and determine whether a signal has been generated.
    def _issue_signal(self, fast_sma, slow_sma):
        """Return a boolean value indicated where to execute a trade or not"""
        if not self.position and fast_sma > slow_sma:
            # If the fast moving average (in this example, the 50-day simple moving average)
            # exceeds the slow moving average (here that that is the 200-day simple moving average)
            # and we are not already in the position, we will return an positive execute signal.
            execute_trade = True
        elif self.position and fast_sma < slow_sma:
            # If we are in a position, we are going to look for an opportunity to close. In this case,
            # we will close the trade when the 50-day SMA cross back below the 200-day SMA. In this
            # event, return a execution signal.
            execute_trade = True
        else:
            # If neither our open or closing signal conditions are met... No execution signal is returned.
            execute_trade = False
        return execute_trade

    def execute(self):
        """Execute the strategy. Execute will run forever."""
        # We should have every piece we need to run the strategy! Let's go ahead and put it all together in a
        # single execution function.
        while True:
            # First step: Get the data, process the data, issue the trade signal
            df = self._acquire_data()
            slow_sma, fast_sma = self._process_data(df)
            execution_signal = self._issue_signal(fast_sma, slow_sma)
            # If we have a trade signal we need to either open or close a trade
            if execution_signal:

                # Not in a position yet? Let's get one open!
                if not self.position:
                    # Step 1 to opening a trade: Check your account balance
                    quote_bal = float(self.accounts(
                        currency=self.asset.split('-')[1],
                        type='trade'
                    ).available)
                    # Step 2: Is the account balance supportive of our order execution size?
                    if quote_bal < self.size:
                        # If not raise an error
                        logging.error(
                            f'Not enough avaible funds in the account to execute {self.size} order'
                        )
                    # Step 3: Put a buy order on the market
                    order_resp = self._create_market_order(
                        side='buy', 
                        size=self.size
                    )
                    # Step 4: Lets just log some info and validate the order was successful
                    logging.info(pformat(order_resp))
                    if order_resp['code'] != '200000':
                        raise DataError('Order failed. Killing trade process')
                    else:
                        logging.info('Order executed successfully!')
                    # Step 5: We're in a position .... Now we wait.

                # Already in a position? Close it down.
                elif self.position:
                    # Step 1: Check how much of the asset we hold. In this simple strategy, we
                    # want assume that no other trading algorithms will mess with our balances
                    # from open to close of the trade. We will assume that we always want to
                    # fully flatten our position in the asset when a signal is raised.
                    asset_bal = float(self.accounts(
                        currency=self.asset.split('-')[0],
                        type='trade'
                    ).available)
                    # Note that there is no validation of size step here. That's because we are always
                    # just selling the available balance. We know the balance is valid as we just 
                    # queried it.
                    # Step 2: Place an order flatten the entire available balance in the asset after
                    # rounding our balance to the nearest valid order size increment
                    order_size = self.__round_decimal_down(asset_bal, self.increment)
                    order_resp = self._create_market_order(
                        side='sell',
                        size=order_size,
                    )
                    # Step 3: As before we want to log and validate the order
                    logging.info(pformat(order_resp))
                    if order_resp['code'] != '200000':
                        raise DataError('Order failed. Killing trade process')
                    else:
                        logging.info('Order executed successfully!')
                    # Step 4: We unwound our position. Time to wait for the next signal!
            # No execution signal? No actions needed this hour
            else:
                pass
            # Now we want to sleep the execution for 1 hour.
            time.sleep(60*60) 


def main():
    """Run SMA Cross strategy"""
    # Your own credentials here 
    # Don't do this in real code. Use python-dotenv or add the variable to PATH
    API_KEY = 'api_key' 
    API_SECRET = 'api_secret' 
    API_PASSPHRASE = 'api_passphrase' 

    # Let's establish our strategy constants
    ASSET = 'BTC-USDT'      # The strategy will run against Bitcoin quoted in Tether
    FAST_SMA = 50           # Calculate our "fast" simple moving average based on 50 days of data
    SLOW_SMA = 200          # Calculate our "slow" simple moving average based on 200 days of data
    GRANULARITY = '1hour'   # Moving averages will calculate using 1 hour granularity data
    ORDER_SIZE = 10         # Open new orders with a fixed 10 USDT size

    # Now we initialize our order class by loading it with our trade params and API info.
    strategy = SMACross(
        asset=ASSET,
        fast_sma=FAST_SMA,
        slow_sma=SLOW_SMA,
        interval=GRANULARITY,
        order_size=ORDER_SIZE,
        api_key=API_KEY,
        api_secret=API_SECRET,
        api_passphrase=API_PASSPHRASE,
    )

    # Finally, we will call the execute function and let the strategy go about its business
    strategy.execute()


if __name__ == '__main__':
    main()
