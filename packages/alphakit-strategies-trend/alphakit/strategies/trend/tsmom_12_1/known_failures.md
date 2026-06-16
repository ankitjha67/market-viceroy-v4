# Known failure modes — tsmom_12_1

> "Dies in 2022 rate shock" beats silence. Every AlphaKit strategy must
> document the regimes where it underperforms, so that users can size
> it intelligently and avoid surprise drawdowns.

Time-series momentum is a **profitable-over-the-long-run, painful-in-the-
short-run** strategy. It will lose money during any of the following
regimes. None of these are bugs — they are the cost of the risk premium.

## 1. Trendless, range-bound markets (2018)

During 2018 most major asset classes oscillated without establishing
durable trends. The strategy repeatedly entered long after a brief rally
only to be stopped out by a reversion, and the same for shorts. Most
CTAs posted negative years — AHL, Winton, Man AHL, Aspect Capital all
returned between **−5% and −12%** that year.

Expected behaviour for tsmom_12_1 in 2018:
* Sharpe around **0.0 to −0.5**
* Drawdown of 8–15% from peak
* High turnover (monthly flip-flops)

## 2. Sharp regime changes / rate shocks (2022)

The 2022 correlated sell-off in equities *and* bonds broke the classic
60/40 diversification assumption. Trend-following recovered later in
the year as short-bond and long-commodity positions paid off, but the
first half was a brutal whipsaw for strategies that were long bonds
going in.

Expected behaviour for tsmom_12_1 in H1 2022:
* 10–20% drawdown before the strategy flipped short bonds
* Late-year recovery as short-bond and long-energy positions caught the
  new regime

## 3. Short, sharp reversals in 2023

The March 2023 SVB banking panic caused a flash reversal in rates that
whipsawed trend-following portfolios short bonds at exactly the wrong
moment. The SG Trend Index returned **−4.2%** in 2023 — its worst year
since 1999.

Expected behaviour for tsmom_12_1 in 2023:
* Negative Sharpe (−0.3 to −0.8)
* Max drawdown in March
* Slow recovery as the new "higher-for-longer" rate regime established

## 4. Extended low-volatility regimes (2017, 2024 partial)

When realised vol collapses below the target (10% annualised), the
vol-scaling term `target_vol / realised_vol` pushes weights above 1
per asset. The per-asset leverage cap (`max_leverage_per_asset=3.0`)
prevents infinite weights, but leverage *does* accumulate, and any
small reversal gets amplified.

Mitigation: raise `max_leverage_per_asset` to 2.0 or less if you plan
to run the strategy through a volatility-dispersion regime.

## 5. Asset-specific blow-ups

Because each asset gets its own signal, the strategy will cheerfully
scale *into* an asset that is trending into a bubble (e.g. commodities
in H1 2008, crypto in 2021). The trend flip comes late — by design —
and the drawdown on the bursting bubble is proportional to how late
the flip is.

## 6. Data gaps and corporate actions

If the input price series has un-adjusted dividends, splits, or
survivorship bias, the 12-month lookback return will be wrong and the
signal will flip on noise. **Always feed the strategy adjusted close
prices** from a survivorship-unbiased source.

## Regime performance (reference, from benchmark_results.json)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Crisis (2008 GFC) | 2007-06 – 2009-06 | ~1.5 | −12% |
| Low vol / range (2018) | 2018-01 – 2018-12 | ~−0.3 | −11% |
| Rate shock (2022 H1) | 2022-01 – 2022-06 | ~0.0 | −14% |
| Trend recovery (2022 H2) | 2022-07 – 2022-12 | ~1.8 | −4% |
| Reversal (2023) | 2023-01 – 2023-12 | ~−0.5 | −9% |

(Values are *reference ranges* from published CTA indices, not specific
to this AlphaKit implementation. The in-repo benchmark is the
authoritative source — see [`benchmark_results.json`](benchmark_results.json).)
