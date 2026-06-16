# Paper — 2s10s Curve Steepener (Cochrane/Piazzesi 2005, after Litterman/Scheinkman 1991)

## Citations

**Initial inspiration:** Litterman, R. & Scheinkman, J. (1991).
**Common factors affecting bond returns.** *Journal of Fixed Income*,
1(1), 54–61. [https://doi.org/10.3905/jfi.1991.692347](https://doi.org/10.3905/jfi.1991.692347)

**Primary methodology:** Cochrane, J. H. & Piazzesi, M. (2005).
**Bond risk premia.** *American Economic Review*, 95(1), 138–160.
[https://doi.org/10.1257/0002828053828581](https://doi.org/10.1257/0002828053828581)

BibTeX entries are aggregated in `docs/papers/phase-2.bib` under
`littermanScheinkman1991` (foundational) and `cochranePiazzesi2005`
(primary).

## Why two papers

The strategy is a market-practice synthesis of two distinct results:

* **Litterman/Scheinkman (1991)** decompose the yield curve into
  three principal components — level, slope, and curvature — and
  show that each is a stationary process with a long-run mean.
  The 2s10s spread is the canonical proxy for the second principal
  component (slope). Because PC2 is stationary, deviations from
  its long-run mean revert.
* **Cochrane/Piazzesi (2005)** show that a single linear combination
  of forward rates — the "tent factor" — predicts excess returns
  on Treasury bonds across maturities. The slope of the curve is
  one of the largest weights in the tent factor. When the slope
  is at an extreme, the implied excess-return forecast is
  asymmetric and a slope-based trade has positive expected return.

Neither paper prescribes the explicit "narrow-spread → enter
steepener" rule. The rule is a market-practice synthesis: take
Litterman/Scheinkman as the *risk-factor* justification for treating
the slope as mean-reverting, and Cochrane/Piazzesi as the
*expected-return* justification for trading on its deviations. The
implementation is honest about this synthesis — the rule is not
literally taken from a single equation in either paper.

## Steepener mechanics — what we are betting on

A 2s10s steepener position is **long the short-end / short the
long-end**. It profits when the 2s10s yield spread (10Y yield −
2Y yield) widens. The widening can come from:

* The long-end yield rising more than the short-end (the short
  long-end leg gains as the 10Y bond price falls), and/or
* The short-end yield falling more than the long-end (the long
  short-end leg gains as the 2Y bond price rises).

Sized DV01-neutral, parallel curve shifts produce zero P&L; the
position's net exposure is to the *slope* of the curve alone.

## Published rules (slope mean-reversion synthesis)

For each daily bar:

1. Compute the log-price spread between the long-end and short-end
   bond proxies::

       log_spread = log(long_end_price) − log(short_end_price)

   Because long-duration prices react more strongly to yield moves,
   a *narrowing* yield spread (10Y − 2Y falls) corresponds to a
   *rising* log-price spread. The two are inversely related; mean-
   reversion of the slope therefore manifests as mean-reversion on
   either signal.

2. Z-score the log-price spread over a trailing window
   (default 252 trading days = 1 year)::

       z = (log_spread − rolling_mean) / rolling_std

3. Steepener entry: when ``z > +entry_threshold`` — the long-end
   has significantly outperformed the short-end → the yield spread
   is narrow vs history. Mean-reversion implies the yield spread
   will widen, which earns positive P&L on a steepener.

4. Exit: when the z-score falls back to ``< +exit_threshold``,
   close the position. The hysteresis avoids whipsaw flips around
   the entry boundary.

5. DV01-neutral weights when the steepener is active::

       short_end_weight = +signal / 2 × (long_duration / short_duration)
       long_end_weight  = −signal / 2

| Parameter | Default | Notes |
|---|---|---|
| `zscore_window` | `252` | ≈ 1 year |
| `entry_threshold` | `1.0` σ | enter when long-end has out-performed by 1σ |
| `exit_threshold` | `0.25` σ | hysteresis avoids whipsaw |
| `long_duration` | `8.0` | 10Y constant-maturity Treasury |
| `short_duration` | `1.95` | 2Y constant-maturity Treasury |

## In-sample period (Cochrane/Piazzesi 2005)

* Data: 1964–2003 (Fama-Bliss zero-coupon Treasury yields)
* The "tent factor" is fit on monthly forward rates and predicts
  one-year excess returns on bonds with R² ≈ 0.30 — strong evidence
  that bond-risk-premia time-variation is forecastable from the
  current yield curve.
* The 2s10s slope alone (a much simpler signal) recovers most of
  the predictive power; this strategy uses the simpler signal so
  that it is implementable from FRED's `DGS2` and `DGS10`.

## Implementation deviations from the source papers

1. **Simplified signal.** Cochrane/Piazzesi use a 5-forward-rate
   linear combination; this strategy uses only the 2s10s slope (a
   2-yield linear combination). The simpler signal recovers most
   of the predictive power per Cochrane/Piazzesi Table 2 but
   sacrifices some R².
2. **Mean-reversion entry rule.** The paper estimates a regression
   forecast and trades on the magnitude of expected returns. This
   strategy enters on a discrete threshold-crossing of the z-score
   to keep the rule reproducible without re-fitting the regression.
3. **DV01 neutrality via fixed durations.** The default duration
   ratio (8.0 / 1.95 ≈ 4.10) is exact only at the par yield used
   to define the constant-maturity Treasuries. Real durations
   drift with the yield level; for ETF-based runs the durations
   should be re-estimated from each ETF's actual basket. The
   approximation biases the steepener's residual exposure to
   parallel curve shifts; see `known_failures.md`.
4. **No transaction-cost or short-borrow model.** Bridge applies
   ``commission_bps`` per leg but does not model the borrow cost
   of shorting Treasuries. Real-feed Session 2H benchmarks need
   a borrow assumption (10–25 bps annualised is typical).

None of these change the **direction** of the trade relative to the
papers' economic content.

## Known replications and follow-ups

* **Adrian, Crump & Moench (2013)** — "Pricing the Term Structure
  with Linear Regressions", JFE. Term-premium decomposition that
  refines the Cochrane/Piazzesi forecast and allows a more
  granular slope-based signal.
* **Diebold & Li (2006)** — "Forecasting the Term Structure of
  Government Bond Yields", JoE. Three-factor Nelson-Siegel
  decomposition with explicit slope dynamics; supports the same
  mean-reversion intuition.
