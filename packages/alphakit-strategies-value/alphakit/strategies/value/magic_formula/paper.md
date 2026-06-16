# Book — The Little Book That Beats the Market

> Greenblatt, J. (2006). *The Little Book That Beats the Market*.
> Wiley. ISBN 978-0-471-73306-5.

```bibtex
@book{greenblatt2006magic,
  title     = {The Little Book That Beats the Market},
  author    = {Greenblatt, Joel},
  publisher = {Wiley},
  year      = {2006},
  isbn      = {978-0-471-73306-5}
}
```

## Summary

The magic formula ranks stocks on two dimensions: earnings yield
(EBIT / enterprise value) and return on capital (EBIT / net fixed
assets + working capital). Stocks are ranked separately on each
measure, and the combined rank determines portfolio membership. The
strategy buys the highest-ranked stocks (cheap and high-quality) and
holds for one year before rebalancing.

Greenblatt demonstrated strong long-term performance on US equities
from 1988-2004, particularly among small- and mid-cap stocks.

## Phase 1 proxy

Without fundamental data, the magic formula is proxied as follows:

- **Value rank**: negative trailing 3-year (756-day) return (long-term
  reversal as cheapness proxy).
- **Quality rank**: volatility-adjusted trailing 1-year (252-day)
  return (risk-adjusted momentum as quality proxy).
- **Combined rank**: sum of value and quality ranks.

## Canonical parameters

| Parameter | Greenblatt | AlphaKit default |
|---|---|---|
| Value lookback | ~3 years of earnings | 756 days |
| Quality lookback | ~1 year of earnings | 252 days |
| Rebalance | Annual | Monthly |

## In-sample period

Greenblatt (2006): US equities 1988-2004.
