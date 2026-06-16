# Known failure modes — sma_cross_50_200

## 1. Huge lag into new trends

The 50/200 cross is so slow that the signal can lag the market turn
by 3–6 months. The March 2009 golden cross happened in June 2009,
three months after the market bottomed, and missed the first 30% of
the recovery. Same story in 2020.

## 2. Whipsaws are rare but painful

The 50/200 cross does not whipsaw often (that's its whole point), but
when it does — typically in a choppy sideways market like 2011 or
2015 — each round-trip is a ~5% drawdown because the slow SMA
requires a long confirmation window before flipping back.

## 3. Data-snooping warning

See `sma_cross_10_30/known_failures.md` §4. The headline Sharpe
numbers from BLL (1992) are optimistic after correcting for the
search over 26 rules. Out-of-sample post-2000 Sharpe is typically
0.2–0.4 for the 50/200 cross on US equities, vs. the 0.6–0.8 BLL
report in-sample.

## 4. Long-only default assumes you have a cash alternative

The default `long_only=True` means "invest or sit in cash". It does
not earn the risk-free rate during flat periods — the AlphaKit bridge
simply marks cash at the initial balance. Users who want explicit
cash-earning behaviour should pipe the output into a portfolio
overlay that deploys idle cash into a short-rates proxy.
