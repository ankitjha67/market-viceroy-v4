# Known failure modes — sma_cross_10_30

## 1. High turnover in choppy markets

A 10/30 cross is short-term. Any multi-day oscillation around the
slow SMA flips the position, and transaction costs accumulate
quickly. BLL (1992) report the rule is profitable on the Dow only
**before** transaction costs — at round-trip costs above ~50 bps the
edge disappears.

## 2. Lag into new trends

SMA rules are late. The 10-day SMA needs 10 days of confirmation
before the cross happens, so the strategy misses the first ~5% of
most new trends. This is a fundamental property of moving averages
and cannot be mitigated without changing the signal definition.

## 3. Whipsaws at range boundaries

In a well-defined trading range the 10-day SMA crosses the 30-day
SMA repeatedly, producing several losing round-trips per month. The
2014–2015 period in crude oil is a textbook example.

## 4. Data-snooping bias

BLL's published Sharpe ratios should be read with Sullivan-Timmerman-
White (1999) in mind — the (10, 30) pair was picked after testing 26
rules, so the reported p-value is optimistic. Out-of-sample Sharpe
is typically 0.3–0.5, not the 0.6–0.9 BLL report.
