# Paper — Skew Reversal (Bakshi-Kapadia-Madan 2003 / Garleanu-Pedersen-Poteshman 2009)

## ⚠ Critical substrate caveat (read first)

The **synthetic-options chain has flat implied volatility across
strikes by construction** (ADR-005). The put-skew z-score this
strategy monitors is *structurally zero* on the synthetic
substrate. The conditional trigger ``skew_zscore > entry_threshold``
**NEVER FIRES** on synthetic data — the strategy emits all-zero
weights and the backtest is a degenerate no-trade case.

**The synthetic backtest of this strategy is uninformative.** It
verifies that the strategy class is StrategyProtocol-conforming
and that the bridge dispatch is wired correctly, but cannot
evaluate the strategy's expected return because the trigger
condition is structurally unattainable on the substrate.

The strategy ships in Phase 2 as a faithful implementation of
the published methodology with documented Phase 3 verification
path against real options chains via Polygon (ADR-004 stub).

## Citations

**Initial inspiration:** Bakshi, G., Kapadia, N. & Madan, D.
(2003). **Stock Return Characteristics, Skew Laws, and the
Differential Pricing of Individual Equity Options.** *Review of
Financial Studies*, 16(1), 101-143.
[https://doi.org/10.1093/rfs/16.1.0101](https://doi.org/10.1093/rfs/16.1.0101)

**Primary methodology:** Garleanu, N., Pedersen, L. H. &
Poteshman, A. M. (2009). **Demand-Based Option Pricing.**
*Review of Financial Studies*, 22(10), 4259-4299.
[https://doi.org/10.1093/rfs/hhp005](https://doi.org/10.1093/rfs/hhp005)

The conditional skew-reversal trade is built on the
demand-based microfoundation: when end-user demand for left-tail
protection spikes (e.g., before known events), put-skew widens
beyond its long-run level. The mean-reversion of skew toward
its average produces a positive expected return for sellers.

The trigger threshold (z-score > 1.5) targets the *upper tail*
of the put-skew distribution — the regime where systematic
short-skew is most rewarded.

BibTeX entries: same as `put_skew_premium` —
`bakshiKapadiaMadan2003` (foundational) +
`garleanuPedersenPoteshman2009` (primary).

## Strategy structure

For each first trading day of a calendar month:

1. **Compute skew z-score.** ``skew = put_iv − call_iv`` at
   matched OTM offsets (5 %). Z-score over rolling 252-day
   window.
2. **Trigger.** If ``skew_zscore > entry_threshold`` (default
   1.5), enter a short OTM put. Otherwise no position.
3. **Hold to expiry.** Same lifecycle as
   `cash_secured_put_systematic`.

⚠ On synthetic chains: skew_iv = put_iv − call_iv = 0 → z-score
= 0 → trigger never fires → all-zero weights.

## Differentiation from `put_skew_premium` (Commit 13)

* `put_skew_premium`: **unconditional** short put + long call
  every cycle.
* `skew_reversal`: **conditional** short put only when
  skew-z > 1.5.

Real-feed cluster expectation: ρ ≈ 0.85-0.95 with
`put_skew_premium` in regimes where both fire; lower ρ
elsewhere because skew_reversal trades less frequently.

On synthetic chains both strategies are uninformative for
different reasons:

* `put_skew_premium`: trades every cycle but the put-skew
  premium is zero by construction → zero P&L expected.
* `skew_reversal`: never trades (trigger never fires) → zero
  P&L by definition.

## Bridge integration

1 discrete leg (short put when triggered). Underlying weight 0.
On synthetic substrate: degenerate Mode 2 (no trade ever).

## Data Fidelity

Same caveats as `put_skew_premium` — the substrate caveat is
the load-bearing limitation. The trigger threshold (1.5σ) is
not testable on synthetic chains because the underlying signal
(put-skew z-score) is zero.

Real-feed verification with realistic skew dynamics is
**mandatory** for any meaningful evaluation of this strategy.
Phase 3 path:

1. Polygon real-chain integration (ADR-004 → active).
2. Compute put-skew z-score per chain snapshot.
3. Confirm trigger fires on a small fraction of days (~5-10 %
   of months under typical regimes).
4. Quantify the systematic short-skew premium per fired cycle.

## Expected synthetic-chain Sharpe range

**Mode 1 (synthetic chain):** 0.0 exactly — all-zero weights
produce zero P&L.

**Mode 1 (real chain, conditional trigger):** estimated
0.4-0.7 in cycles where the trigger fires (based on
Garleanu-Pedersen-Poteshman §V) — but this is NOT what the
synthetic backtest produces.

**Mode 2 (degenerate underlying-only):** all-zero weights.
