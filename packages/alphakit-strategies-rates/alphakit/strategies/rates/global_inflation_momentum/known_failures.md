# Known failure modes — global_inflation_momentum

> Inflation-momentum bond tilts are most useful in regimes where
> inflation matters most — and most painful when the inflation
> regime changes faster than the 12-month signal can react.
> 2021–2022 is the canonical recent example.

Cross-country dollar-neutral bond tilt on inflation momentum.
Will lose money in the regimes below.

## 1. Inflation regime change at signal-window scale (2021–2022)

The 12-month inflation-momentum signal lags the inflation regime
by definition. When inflation regime shifts (post-pandemic supply
shocks, 2021 Q3 onwards), the signal continues to point at the
*previous* regime for a year. Specifically:

* Mid-2021 onwards: US inflation rises sharply (above 5% YoY by
  mid-2021)
* Strategy enters with US inflation momentum *low* (because the
  trailing 12-month change was small as of mid-2020)
* Strategy goes LONG US bonds (low inflation momentum → expect
  bond rally)
* US bonds CRASH 25%+ in H1 2022 as the Fed pivots
* Strategy doesn't re-rank to short US until early 2023

Drawdown of 12-20% during the lag window is expected. Mitigation:
shorten ``cpi_lookback_months`` to 6 for faster regime
recognition, accepting more signal noise.

## 2. Synchronised inflation surprises across countries

The strategy is *cross-sectional* dollar-neutral. If all countries
experience the same inflation shock simultaneously (2021–2022:
global commodity-driven inflation), the cross-section dispersion
narrows and the rank-based signal has little to trade on. The
strategy's expected return shrinks to zero in synchronised
regimes — but the *fixed costs* (transaction costs, slippage)
remain.

## 3. CPI release timing and look-ahead bias

The strategy uses month-end CPI levels, but real-world CPI
releases happen with a lag (US CPI: ~mid-month for prior month;
some countries: 2-3 weeks lag). The strategy implicitly assumes
the CPI level at month-end is *known* at month-end, which is
a form of look-ahead bias.

Mitigation: real-feed Session 2H benchmarks must lag the CPI
column by 1 month before computing the signal. Easy fix at
benchmark-runner level; documented here as a known limitation
of the synthetic-fixture benchmark.

## 4. CPI vs bond data alignment

The default config uses monthly CPI series (FRED's HICP/CPI data
is monthly) but daily bond series. The strategy resamples both
to month-end before computing signals; this is correct but
silently masks any data-frequency mismatch. If a daily CPI proxy
is passed in, the strategy still runs but the trailing 12-month
change is now computed over 252 daily observations, which is
noisier than the canonical 12-monthly observations.

## 5. Cluster correlation with sibling strategies

* `breakeven_inflation_rotation` — US-only level signal. Expected
  ρ ≈ 0.3-0.5 in regimes where US dominates the cross-country
  inflation signal.
* `real_yield_momentum` — US-only TIPS momentum. Expected
  ρ ≈ 0.2-0.4.
* `g10_bond_carry` — cross-country yield carry. Expected
  ρ ≈ 0.0-0.2 (different signal type entirely).
* `bond_tsmom_12_1` — single-asset bond momentum. Expected
  ρ ≈ 0.3-0.5 when one country dominates the cross-section.

None cross 0.95.

## 6. Country panel size dependence

With only 2 countries, the cross-section rank collapses to a
binary "long-short pair" trade. With 3, the middle country is
zero-weighted. Below ~5 countries the rank dispersion is coarse
and the strategy is noisy.

Real-feed Session 2H benchmark should target at least G7
(US/UK/Germany/France/Japan/Canada/Italy) for adequate rank
granularity.

## Regime performance (reference, gross of fees, IMR 2014 G7 panel)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Disinflation tail (1985-1999) | 1985-2000 | ~0.6 | −5% |
| Stable low-inflation (2000-2007) | 2000-2007 | ~0.5 | −6% |
| GFC + post-crisis (2008-2014) | 2008-2014 | ~0.4 | −8% |
| QE compression (2015-2019) | 2015-2019 | ~0.2 | −5% |
| 2021-22 inflation regime shift | 2021-2022 | ~−1.0 | −18% |
| 2023-25 normalisation | 2023-2025 | ~0.5 | −6% |

(Reference ranges from Ilmanen/Maloney/Ross (2014) Table 4 G7
inflation-momentum sleeve; the in-repo benchmark with synthetic
fixture proxies is authoritative for this implementation but
materially different from the IMR G7 paper version —
see [`benchmark_results.json`](benchmark_results.json).)
