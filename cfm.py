#!/usr/bin/env python


# continuous fee minting simulation


import logging, argparse, time, random
from datetime import datetime, timedelta


def pretty_time(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def pretty_delta(seconds):
    s = timedelta(seconds=int(seconds))
    d = datetime(1,1,1) + s
    return '%02d:%02d:%02d:%02d' % (d.day-1, d.hour, d.minute, d.second)


def percentage(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError('percent value {} not in range [0.0, 1.0]'.format(x))
    return x


def positive_int(x):
    x = int(x)
    if x <= 0.0:
        raise argparse.ArgumentTypeError('invalid positive_int value: {}'.format(x))
    return x


logging.basicConfig(format='%(asctime)-15s %(levelname)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


# constants
fund_value = 4000000.00         # assume it stays constant during sim
init_shares = 1000.0            # initial shares subject to inflation due to fee minting
customer_shares = 25.0          # track the effect on an individual customer's holdings
sim_periods = 10                # how long sim will run as number of mgmt fee periods
xlm_price = 0.45
stroop_per_tx = 100
stroop_per_xlm = 0.0001


# sim params
default_mgmt_fee = 0.02            # percent [0.00, 1.00]
default_mgmt_fee_period = 365      # how often to capture mgmt fee
default_mint_period = 300          # how often to mint micro-fees in seconds
default_mint_period_noise = 240    # plus or minus some uniform random seconds
default_clock_drift = 0.001        # scalar for adding errors to the clock
default_fee_tolerance = 1.00      # max stellar fees to pay in USD/day


# user params
parser = argparse.ArgumentParser(description='continuous fee minting simulation')
parser.add_argument('-v', '--verbose', help='show verbose output', action='store_true', required=False)
parser.add_argument('-f', '--fee', help='mgmt fee 0.00-1.00, default {}'.format(default_mgmt_fee), type=percentage, default=default_mgmt_fee, required=False)
parser.add_argument('-p', '--period', help='mgmt fee period in days, default {:,.0f}'.format(default_mgmt_fee_period), type=positive_int, default=default_mgmt_fee_period, required=False)
parser.add_argument('-m', '--mint', help='fee minting period in seconds, default {}'.format(default_mint_period), type=positive_int, default=default_mint_period, required=False)
parser.add_argument('-n', '--noise', help='fee minting period randomness in seconds, default {}'.format(default_mint_period_noise), type=positive_int, default=default_mint_period_noise, required=False)
parser.add_argument('-d', '--drift', help='clock drift scalar, default {}'.format(default_clock_drift), type=float, default=default_clock_drift, required=False)
parser.add_argument('-t', '--tolerance', help='ledger tx fee tolerance in USD/day, default {:,.2f}'.format(default_fee_tolerance), type=float, default=default_fee_tolerance, required=False)
args = vars(parser.parse_args())

if args['verbose']:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

mgmt_fee = args['fee']
inflation_rate = (1.0 / (1.0 - mgmt_fee))
mgmt_fee_period = args['period'] * 60 * 60 * 24   # convert to days -> secs
mint_period = args['mint']
mint_period_noise = args['noise']
clock_drift = args['drift']
init_price = float(fund_value)/init_shares
fee_tolerance = args['tolerance']

if mint_period_noise > mint_period:
    raise argparse.ArgumentTypeError('mint period noise {:,.0f} must be less than the mint period {:,.0f}'.format(mint_period_noise, mint_period))

logger.debug('management fee, f = {}'.format(mgmt_fee))
logger.debug('management fee period, p = {:,.0f} secs ({} days)'.format(mgmt_fee_period, args['period']))
logger.debug('inflation rate: {}'.format(inflation_rate))
logger.debug('minting every: {:,.0f} +- {:,.0f} secs'.format(mint_period, mint_period_noise))
logger.debug('clock drift: {}'.format(clock_drift))
logger.debug('fund value: ${:,.2f}'.format(fund_value))
logger.debug('initial shares: {:,.0f}'.format(init_shares))
logger.debug('init price per share: ${:,.2f}'.format(init_price))
logger.debug('customer shares: {:,.0f}'.format(customer_shares))
logger.debug('customer value: {:,.2f}'.format(customer_shares * init_price))
logger.debug('sim periods: {:,.0f}'.format(sim_periods))
logger.debug('fee tolerance: ${:,.2f}'.format(fee_tolerance))
logger.debug('xlm price: ${:,.2f}'.format(xlm_price))
logger.debug('stroop per tx: {:,.0f}'.format(stroop_per_tx))


# sim loop
fund_shares = init_shares
init_customer_value = (float(fund_value) / fund_shares) * customer_shares
this_timestamp = 0.0
last_timestamp = 0.0
earnings = 0.0          # total fees taken in USD
tx_fees = 0.0           # fees paid to the Stellar network
num_mints = 0           # total mint events per period
num_skips = 0           # mints skipped per period due to fee throttle
mint = 0.0

while not this_timestamp > mgmt_fee_period * sim_periods:

    # random delay between fee mintings
    r = (random.random() * 2.0) - 1.0
    wait = float(mint_period) + (r * float(mint_period_noise))
    this_timestamp += wait

    # check for new mgmt fee period
    new_period = False
    this_period = int(this_timestamp / mgmt_fee_period)
    last_period = int(last_timestamp / mgmt_fee_period)
    if this_period > last_period:
        this_timestamp = (this_period * mgmt_fee_period) # force mint at end of period
        new_period = True

    # introduce clock sampling error
    time_delta = this_timestamp - last_timestamp
    time_delta *= (1.0 + clock_drift)

    skipped = False
    usd_per_day = 0.0
    if not last_timestamp:

        # sim starting, bootstrap t=0
        new_period = True
        display_time = last_timestamp

    else:

        # continuous fee minting formula
        period_slice = time_delta / mgmt_fee_period
        shares_scalar = pow(inflation_rate, period_slice)
        mint = fund_shares * (shares_scalar - 1.0)
        display_time = this_timestamp

        # minting throttle
        this_tx_fee = float(stroop_per_xlm * xlm_price * stroop_per_tx)
        sim_days = float(this_timestamp) / (60 * 60 * 24)
        usd_per_day = (tx_fees + this_tx_fee) / sim_days

        # skip this mint to reduce freq
        if usd_per_day > fee_tolerance:
            skipped = True
            num_skips += 1
            mint = 0.0

        # mint ok
        else:
            tx_fees += this_tx_fee
            num_mints += 1

    # customer share dilution
    fund_shares += mint
    fund_price = float(fund_value) / float(fund_shares)
    earnings += (mint * fund_price)
    customer_value = fund_price  * customer_shares

    # log minting details
    mint_disp = 'SKIPPED' if skipped else '{:,.010f}'.format(mint)
    msg  = 'Time {} Delta {} '.format(pretty_time(this_timestamp), pretty_delta(time_delta))
    msg += 'Mint {} TotShs {:,.010f} ShrPrice {:,.2f} '.format(mint_disp, fund_shares, fund_price)
    msg += 'CustVal {:,.2f} Fees {:,.2f} FeeRate {:,.2f}'.format(customer_value, tx_fees, usd_per_day)
    logger.debug(msg)

    # end of period summary
    if new_period:
        ideal = float(init_customer_value) * pow(1.0 - mgmt_fee, this_period)
        err = abs(customer_value - ideal)
        msg  = 'Time {} Mints {:,.0f} {}Skips {:,.0f} '.format(pretty_time(display_time), num_mints, '[START] ' if not num_mints else '', num_skips)
        msg += 'Shs {:,.012f} Price ${:,.2f} '.format(fund_shares, fund_price)
        msg += 'Cust1 ${:,.2f} Err ${:,.2f} Earn ${:,.2f} TxFees ${:,.2f}'.format(customer_value, err, earnings, tx_fees)
        num_mints = 0
        num_skips = 0
        print msg

    if not skipped or new_period:
        last_timestamp = this_timestamp

