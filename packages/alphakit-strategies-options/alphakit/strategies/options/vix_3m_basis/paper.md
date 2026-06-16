# Paper — VIX 3M Basis (Whaley 2009 / Alexander-Korovilas-Kapraun 2015)

## Reframe context

This strategy is the **reframe** of the original Phase 2 plan
slug `vix_front_back_spread` — see
[`docs/phase-2-amendments.md`](../../../../../../docs/phase-2-amendments.md)
2026-05-01 entry "reframe vix_front_back_spread → vix_3m_basis".

The original plan targeted a front-month vs back-month VIX
futures calendar spread. yfinance exposes only a single
continuous-front-month VIX future (``VIX=F``); back-month
per-maturity contracts are not available. The strategy was
reframed to trade the **spot vs 3-month constant-maturity
index basis** (^VIX vs ^VIX3M), which Alexander, Korovilas &
Kapraun (2015) study explicitly under the same theoretical
framework.

## Citations

**Initial inspiration:** Whaley, R. E. (2009). **Understanding
VIX.** *Journal of Portfolio Management*, 35(2), 98-105.
[https://doi.org/10.3905/JPM.2009.35.2.098](https://doi.org/10.3905/JPM.2009.35.2.098)

**Primary methodology:** Alexander, C., Korovilas, D. &
Kapraun, J. (2015). **Diversification with Volatility
Products.** *Journal of International Money and Finance*, 65,
213-235.
[https://doi.org/10.1016/j.jimonfin.2015.10.005](https://doi.org/10.1016/j.jimonfin.2015.10.005)

Alexander et al. study the term-structure of VIX-related
products (spot, front-month future, 3-month constant-maturity
index, mid-term VIX ETNs) and document a systematic basis trade
between spot VIX and the 3-month constant-maturity index:

* **Contango** (``VIX_spot < VIX3M``): SHORT the 3-month leg.
  Profit from roll-down convergence.
* **Backwardation** (``VIX_spot > VIX3M``): LONG the 3-month
  leg.

Lower turnover than the spot-vs-front-month sibling; the
3-month CMI moves more slowly than the front-month future.

BibTeX entries: `whaley2009vix` (foundational, registered in
Commit 15) + `alexanderKorovilasKapraun2015` (primary).

## Differentiation from `vix_term_structure_roll` (Commit 15)

* `vix_term_structure_roll`: spot vs FRONT-month future (~30-day
  tenor) — Simon-Campasano 2014.
* `vix_3m_basis` (this strategy): spot vs 3-MONTH constant
  maturity (~90-day tenor) — Alexander/Korovilas/Kapraun 2015.

Cluster expectation: ρ ≈ 0.55-0.75. Different tenors of the
same basis-trade family. The 3-month basis is more stable but
produces smaller per-cycle P&L. The two strategies ship as
parametric variants for users who want either tenor.

## Strategy structure

For each daily bar:

1. Read ``^VIX`` (spot) and ``^VIX3M`` (3-month CMI) from
   input prices.
2. Compute basis = ``VIX_spot − VIX3M``.
3. Position on ``^VIX3M``: ``+1.0`` long when basis > 0
   (backwardation); ``-1.0`` short when basis < 0 (contango);
   ``0.0`` when |basis| < 1e-6.

## Bridge integration

Composition wrapper over `VIXTermStructureRoll` with the second
symbol redirected from ``VIX=F`` to ``^VIX3M``. Identical
dispatch semantics: standard TargetPercent on the 3-month leg;
^VIX is signal-source only.

## Data Fidelity

* **Both legs are CBOE indices.** ``^VIX3M`` is the 3-month
  constant-maturity VIX index, *not* a directly-tradeable
  instrument. Real production requires the **VXZ ETN** (or
  similar mid-term VIX ETN) as the tradeable proxy. The
  Phase 2 implementation uses ^VIX3M as a placeholder; users
  swapping to real-feed VXZ should update the
  ``longer_symbol`` constructor argument.
* **yfinance ^-prefix passthrough.** Both ^VIX and ^VIX3M are
  passed through unchanged. Real-data shape verification
  deferred to Session 2H.
* No options-chain dependency.

## Expected real-feed Sharpe range

`0.3-0.6` per Alexander et al. 2015 OOS analysis. Lower than
`vix_term_structure_roll`'s 0.4-0.7 because the 3-month tenor
basis has lower variance.

## Synthetic / fixture mode

Same as `vix_term_structure_roll`: the standard `BenchmarkRunner`
provides both columns when the universe is `[^VIX, ^VIX3M]`;
fixture generator produces plausible OHLCV.
