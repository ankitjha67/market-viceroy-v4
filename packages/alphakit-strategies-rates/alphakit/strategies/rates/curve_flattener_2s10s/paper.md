# Paper — 2s10s Curve Flattener (Cochrane/Piazzesi 2005, after Litterman/Scheinkman 1991)

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

Identical to the steepener — Litterman/Scheinkman supplies the
*risk-factor* justification that the slope is mean-reverting,
Cochrane/Piazzesi supplies the *expected-return* justification that
trading on its deviations from the mean has positive expected return.
Neither paper prescribes the explicit "wide-spread → enter flattener"
rule; the rule is a market-practice synthesis of both results, and
this `paper.md` is honest about that synthesis.

## Flattener mechanics — what we are betting on

A 2s10s flattener position is **long the long-end / short the
short-end**. It profits when the 2s10s yield spread (10Y yield − 2Y
yield) narrows. The narrowing can come from:

* The long-end yield falling more than the short-end (long P_long
  gains as P_long rises), and/or
* The short-end yield rising more than the long-end (short P_short
  gains as P_short falls).

DV01-neutral sizing means parallel curve shifts produce zero P&L;
the position's net exposure is to the slope alone.

The flattener and steepener are **mirror images by construction**.
Their daily P&L correlation is approximately −1.0; running both at
the same time is meaningless. They are shipped as separate strategies
to make the user's intent explicit (which side of the slope are you
betting on?), not because they represent independent alpha sources.
The cluster-correlation note in `known_failures.md` documents this
acceptance.

## Published rules (slope mean-reversion synthesis)

For each daily bar:

1. ``log_spread = log(long_end_price) − log(short_end_price)``.
2. ``z = (log_spread − rolling_mean) / rolling_std`` over a
   ``zscore_window``-day trailing window.
3. **Flattener entry:** ``z < −entry_threshold``. The long-end has
   significantly under-performed → the yield spread is wide vs
   history. Mean-reversion implies the spread will narrow, earning
   positive P&L on a flattener.
4. **Exit:** ``z > −exit_threshold``. The hysteresis avoids whipsaw
   flips around the entry boundary.
5. **DV01-neutral weights** when the flattener is active::

       short_end_weight = −signal / 2 × (long_duration / short_duration)
       long_end_weight  = +signal / 2

| Parameter | Default | Notes |
|---|---|---|
| `zscore_window` | `252` | ≈ 1 year |
| `entry_threshold` | `1.0` σ | enter when long-end has under-performed by 1σ |
| `exit_threshold` | `0.25` σ | hysteresis avoids whipsaw |
| `long_duration` | `8.0` | 10Y constant-maturity Treasury |
| `short_duration` | `1.95` | 2Y constant-maturity Treasury |

## Implementation deviations from the source papers

Identical to the steepener:

1. **Simplified signal** — uses the 2s10s slope alone rather than the
   full 5-forward-rate tent factor.
2. **Mean-reversion entry rule** — discrete threshold-crossing on the
   z-score rather than a regression-forecast magnitude.
3. **DV01 neutrality via fixed durations** — default ratio 8.0 / 1.95
   ≈ 4.10 is exact only at the par yield used to define the
   constant-maturity Treasuries.
4. **No transaction-cost or short-borrow model** — bridge applies
   ``commission_bps`` per leg, but does not model short-borrow cost
   on Treasuries.

None of these change the **direction** of the trade relative to the
papers' economic content.

## Known replications and follow-ups

Same set as the steepener (Adrian/Crump/Moench 2013, Diebold/Li 2006).
Cross-reference `curve_steepener_2s10s/paper.md` for the full list.
