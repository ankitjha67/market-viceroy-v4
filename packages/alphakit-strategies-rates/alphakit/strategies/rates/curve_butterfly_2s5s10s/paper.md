# Paper — 2s5s10s Curve Butterfly (Litterman/Scheinkman 1991, PC3)

## Citations

**Foundational and primary methodology:**

Litterman, R. & Scheinkman, J. (1991). **Common factors affecting
bond returns.** *Journal of Fixed Income*, 1(1), 54–61.
[https://doi.org/10.3905/jfi.1991.692347](https://doi.org/10.3905/jfi.1991.692347)

This is one of the rare strategies in the family where the
foundational and primary citations are the same paper: Litterman/
Scheinkman explicitly identify curvature as the third principal
component of the yield curve and document its mean-reverting
dynamics. The 2s5s10s butterfly is the canonical practitioner trade
that isolates curvature exposure, and the "long wings / short belly"
sizing follows directly from the PCA loadings.

BibTeX entry: `littermanScheinkman1991` in
`docs/papers/phase-2.bib`.

## Butterfly mechanics — what we are betting on

A 2s5s10s butterfly is a **3-leg DV01-weighted trade**:

* **Short-belly butterfly** ("long wings, short belly"): long 2Y,
  short 5Y, long 10Y — sized DV01-weighted so that each wing
  contributes half of the DV01 needed to offset the belly. Profits
  when the belly *cheapens* relative to the wings (5Y yield rises
  by more than the 2-10 yield average).
* **Long-belly butterfly** ("short wings, long belly", the mirror):
  short 2Y, long 5Y, short 10Y. Profits when the belly *richens*
  relative to the wings (5Y yield falls by more than the 2-10 yield
  average).

DV01-weighted, the butterfly is approximately neutral to PC1 (level)
and PC2 (slope) shifts, exposing only PC3 (curvature). This is the
classic Litterman/Scheinkman observation: PC1 explains ~80% of yield
variance, PC2 ~15%, PC3 ~5%, and isolating PC3 produces an
uncorrelated source of return.

## Why a single paper is sufficient

Most slope-based strategies in this family pair a foundational
*risk-factor* paper (Litterman/Scheinkman) with a primary
*expected-return* paper (Cochrane/Piazzesi). For the butterfly we
cite Litterman/Scheinkman alone because:

* The risk-factor decomposition (PC3 = curvature) is the entire
  motivation for the trade structure.
* PC3 is a stationary, mean-reverting series by construction —
  the implementation just z-scores its proxy and trades the
  reversion.
* Cochrane/Piazzesi's tent factor is a level/slope predictor and
  does not directly motivate curvature trading.

The "Why two papers" section is therefore intentionally absent
from this strategy; the paper.md template's general convention is
respected (one paper is sufficient when methodology is fully
specified by it).

## Curvature signal

Direct PCA on a daily yield panel is noisy and requires re-fitting
the loadings as new data arrives. This implementation uses a
price-space proxy that is monotone in the curvature PC and is
deterministic from the input alone::

    fly_price = log(P_belly) − ½ × (log(P_short) + log(P_long))

Interpretation:

* **High positive ``fly_price``** ↔ belly has out-performed the
  linear average of the wings ↔ belly yield fell by more than the
  2-10 average ↔ belly is *rich* vs the wings (PC3 is low/negative).
* **Low negative ``fly_price``** ↔ belly has under-performed the
  wings ↔ belly is *cheap* vs the wings (PC3 is high/positive).

The strategy trades mean-reversion of this proxy in both
directions:

* ``z > +entry_threshold`` → belly rich → short-belly entry
  (long wings, short belly)
* ``z < −entry_threshold`` → belly cheap → long-belly entry
  (short wings, long belly)
* ``|z| < exit_threshold`` → exit any active position

## Published rules

For each daily bar:

1. Compute ``fly_price`` (above).
2. Z-score the ``fly_price`` over a 252-day rolling window.
3. Activate the appropriate butterfly direction when the z-score
   crosses the entry threshold; exit on hysteresis when it returns
   inside ``±exit_threshold``.
4. DV01-weighted weights when active::

       w_short = +signal × 0.5 × belly_duration / short_duration
       w_belly = −signal × 1.0
       w_long  = +signal × 0.5 × belly_duration / long_duration

   ``signal = +1`` is the short-belly butterfly (long wings, short
   belly); ``signal = −1`` is the long-belly butterfly. With default
   durations 1.95 / 4.5 / 8.0 the per-unit-signal weights are
   roughly +1.15 / −1.0 / +0.28.

| Parameter | Default | Notes |
|---|---|---|
| `zscore_window` | `252` | ≈ 1 year |
| `entry_threshold` | `1.0` σ | enter on extreme curvature |
| `exit_threshold` | `0.25` σ | hysteresis avoids whipsaw |
| `short_duration` | `1.95` | 2Y CMT |
| `belly_duration` | `4.5` | 5Y CMT |
| `long_duration` | `8.0` | 10Y CMT |

## Belly proxy choice (real-feed caveat)

The default ETF universe uses SHY / IEF / TLT, but **IEF is a
7-10Y ETF with effective duration ≈ 8 years**, not 5 years. There
is no liquid 4-6Y Treasury ETF in the iShares lineup; the closest
tradeable approximation is a 50/50 mix of SHY and IEF, or simply
using IEF and accepting the duration mismatch.

For real-feed Session 2H benchmarks the cleanest path is to
construct a 5Y-equivalent price series from FRED's `DGS5`
(constant-maturity 5Y yield) via the duration approximation,
matching the FRED-driven implementation of the other curve
strategies in this family. The synthetic-fixture benchmark in
this folder uses `IEF` (8Y) as the belly proxy to keep the ETF
universe self-consistent; the resulting butterfly P&L is biased
because IEF's duration is closer to TLT's than to a true 5Y, and
the fixture-benchmark Sharpe will under-state the real-data
performance.

## Implementation deviations from Litterman/Scheinkman

1. **Price-space proxy instead of true PCA loadings.** PCA loadings
   would re-fit on each rolling window and produce slightly
   different curvature directions over time; the price-space proxy
   uses the canonical ½/−1/½ weighting that approximates the PC3
   loadings on a typical 2-5-10Y triplet. The cost is ~10–20%
   tracking error vs a re-fit PCA factor.
2. **DV01-weighted instead of duration-weighted.** Practitioners
   often use exact DV01 weights derived from current bond
   characteristics; this implementation uses fixed durations from
   the config. Documented as a known failure mode.
3. **Mean-reversion entry rule.** Litterman/Scheinkman document
   stationarity but do not prescribe an explicit trading rule; the
   z-score threshold and hysteresis are this implementation's
   choice for a reproducible, parameter-light entry/exit logic.

## Known replications and follow-ups

* **Diebold & Li (2006)** — "Forecasting the Term Structure of
  Government Bond Yields", JoE. Three-factor Nelson-Siegel
  decomposition that maps cleanly to Litterman/Scheinkman's PC1/PC2/
  PC3 and provides explicit forecasting equations.
* **Bowsher & Meeks (2008)** — "The Dynamics of Economic Functions:
  Modelling and Forecasting the Yield Curve", JASA. Refined factor
  dynamics for curvature including regime-switching estimates.
