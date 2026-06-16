# Known failure modes — vix_3m_basis

> Phase 2 Session 2F real-data VIX basis trade at 3-month
> constant-maturity tenor. Reframed from `vix_front_back_spread`
> per `docs/phase-2-amendments.md` 2026-05-01. Whaley 2009 +
> Alexander/Korovilas/Kapraun 2015.

## 1. Reframe transparency (vix_front_back_spread → vix_3m_basis)

The Phase 2 master-plan slug `vix_front_back_spread` is **not**
a Phase 2 strategy. The reframe is documented in
`docs/phase-2-amendments.md` 2026-05-01.

The economic content (term-structure basis trade) is
preserved; only the *tenor* changes from "front vs back month
futures" (not implementable on yfinance) to "spot vs 3-month
constant maturity index" (implementable).

## 2. ^VIX3M is an index, not tradeable

This is the primary substrate gap. ``^VIX3M`` is a CBOE-
published index measuring the 3-month constant-maturity VIX;
it is NOT a directly-tradeable instrument.

Real production deployments require the **VXZ ETN** (Barclays
iPath S&P 500 VIX Mid-Term Futures ETN) or a similar
exchange-traded proxy. The strategy's ``longer_symbol``
constructor argument can be swapped to `"VXZ"` for real-feed
runs; the basis dynamics are similar (VXZ tracks 4-7-month
VIX-futures-weighted index, close to but not identical to the
3-month constant-maturity ^VIX3M).

The synthetic-fixture benchmark uses ^VIX3M as a placeholder;
real-feed verification with VXZ deferred to Phase 3.

## 3. Cluster overlap

* **`vix_term_structure_roll`** (Commit 15): ρ ≈ 0.55-0.75.
  Same basis-trade family, different tenor (front-month vs
  3-month).
* **Phase 1 `vix_term_structure`** / **`vix_roll_short`**:
  ρ ≈ 0.30-0.55 — RV-proxied vs real-data versions.

## 4. Lower per-cycle P&L vs front-month basis

The 3-month basis moves more slowly than the front-month
basis. Per-cycle P&L is correspondingly smaller — the
strategy ships with lower expected Sharpe than its
front-month sibling.

Trade-off: lower turnover (lower bid-ask drag), more stable
position. Suits longer-horizon investors.

## 5. yfinance ^-prefix passthrough assumption

Same as `vix_term_structure_roll` §6. Both ^VIX and ^VIX3M
use yfinance's ^-prefix passthrough; real-data shape
verification deferred to Session 2H.

## 6. ^VIX3M historical depth

CBOE began publishing the 3-month constant-maturity VIX (^VIX3M,
formerly ^VXV) in 2007. Real-feed backtests pre-2007 require
synthetic backfill. The synthetic-fixture benchmark for this
strategy starts at 2005-01-01 and uses fictional ^VIX3M values
for 2005-2007; **the early-period results are not real-data
representative**. Phase 3 with VXZ ETN data (also begins 2009)
will further constrain the start date.

## 7. Composition-wrapper transparency

`VIX3MBasis` is a thin composition wrapper over
`VIXTermStructureRoll` with the second symbol redirected.
Bug fixes in the parent flow through automatically. The
metadata (`name`, `paper_doi`, `family`) is independent.

## 8. Standard substrate caveats

No options chains. No skew / bid-ask / volume / OI from the
synthetic-options family.
