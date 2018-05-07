# Continuous fee minting

Rick Seeger, Crypdex LLC, May 6, 2018

# Abstract

Investment funds may levy a management fee as a fixed percent of the fund value on a periodic basis (typically 2% annually). This method is inaccurate for customers that trade shares of a fund at a higher frequency than the management fee levy period, but can be partially assuaged through customer pro-rating, fund value averaging, and by putting restrictions on the frequency of customer trades (i.e. "lock-in" periods).

Alternatively, if the fund exists on a distributed ledger, such as the [Stellar Network](https://www.stellar.org/), management fees can be levied trivially with near perfect accuracy without imposing any restrictions on user trading and without the discontinuous fund devaluations corresponding to periodic levies. This is achieved by minting micro-fees at each ledger update, an effectively continuous process from the context of the ledger.

A throttle may be implemented to keep tranasaction fees below a specified daily rate and to protect against congestion-induced fee spikes by increasing the minting frequency as necessary.

# Refs

1 https://en.wikipedia.org/wiki/Management_fee
