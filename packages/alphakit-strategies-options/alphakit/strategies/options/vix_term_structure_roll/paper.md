# Paper — VIX Term Structure Roll (Whaley 2009 / Simon-Campasano 2014)

## Citations

**Initial inspiration:** Whaley, R. E. (2009). **Understanding
VIX.** *Journal of Portfolio Management*, 35(2), 98-105.
[https://doi.org/10.3905/JPM.2009.35.2.098](https://doi.org/10.3905/JPM.2009.35.2.098)

Whaley documents the construction and properties of the CBOE
Volatility Index (VIX) — the model-free implied-vol measure
underlying the VIX-futures market. The VIX-futures basis (spot
minus front-month future) is the canonical signal in this
family.

**Primary methodology:** Simon, D. P. & Campasano, J. (2014).
**The VIX Futures Basis: Evidence and Trading Strategies.**
*Journal of Derivatives*, 21(3), 54-69.
[https://doi.org/10.3905/jod.2014.21.3.054](https://doi.org/10.3905/jod.2014.21.3.054)

Simon-Campasano study the VIX-futures basis empirically and
document the systematic trading rule:

* **Contango** (``VIX_spot < VIX_front_future``): SHORT the
  front-month future. Profit from roll-down convergence as the
  future approaches expiry and converges down to spot.
* **Backwardation** (``VIX_spot > VIX_front_future``): LONG
  the front-month future. Profit from roll-up convergence.

The signal is unconditional — sign of the basis determines
direction. Position size is constant ±1 (per Simon-Campasano
canonical spec).

BibTeX entries: `whaley2009vix` (foundational) and
`simonCampasano2014` (primary).

## Differentiation from Phase 1 `vix_term_structure`

Phase 1's `vix_term_structure` (volatility family, also
Simon-Campasano-anchored) uses **realized vol of SPY as a proxy
for VIX** because Phase 1 had no real VIX feed available. The
proxy is documented honestly in that strategy's `paper.md` but
diverges from real VIX dynamics in important ways:

* Real VIX includes the option-implied component
  (forward-looking); RV-of-SPY is purely backward-looking.
* Real VIX has a steeper term structure (futures-implied vol);
  RV proxies are flatter.
* Real VIX spikes faster on stress events; RV proxies lag.

Phase 2's `vix_term_structure_roll` consumes **real ^VIX
(yfinance equities passthrough) + VIX=F (yfinance-futures
passthrough)** and trades the actual basis. The two slugs
co-exist on main:

* `vix_term_structure` (Phase 1): RV-proxied, ADR-002 mild
  deviation, volatility family.
* `vix_term_structure_roll` (Phase 2 Session 2F): real-data,
  options family.

Cluster expectation: ρ ≈ 0.40-0.65 in moderate-vol regimes;
divergent in stress regimes where real VIX leads RV.

## Strategy structure

For each daily bar:

1. Read ``^VIX`` (spot) and ``VIX=F`` (front-month future) from
   input prices.
2. Compute basis = ``VIX_spot − VIX_front_future``.
3. Position on ``VIX=F``:

   * ``+1.0`` (long) when ``basis > 0`` (backwardation)
   * ``-1.0`` (short) when ``basis < 0`` (contango)
   * ``0.0`` when ``|basis| < 1e-6`` (numerical noise)

4. ``^VIX`` is a signal-source column; not traded.

The continuous TargetPercent dispatch handles daily rebalances
naturally — no `discrete_legs` declaration needed.

## Bridge integration

No discrete legs. VIX=F is traded under standard TargetPercent
semantics; ^VIX is read but not traded (weight 0 throughout).

## Data Fidelity

* **Real VIX index data + real VIX futures via yfinance
  passthrough.** No options-chain dependency. The strategy
  bypasses the synthetic-options adapter entirely.
* **yfinance ^-prefix passthrough.** ``^VIX`` is a CBOE index
  ticker; yfinance's standard ``yfinance.download()`` accepts
  ^-prefixed tickers without modification. The yfinance equities
  adapter passes them through; the response shape is OHLCV with
  the ticker name in the columns. Documented in
  `known_failures.md` §9.
* **Real-data shape verification deferred to Session 2H.**
  Integration tests mock yfinance responses; real-feed runs
  scheduled for Session 2H benchmark-runner refactor.

## Expected real-feed Sharpe range

`0.4-0.7` per Simon-Campasano 2014 OOS analysis. The basis
trade is one of the most reliable systematic vol-trading
strategies on the literature record.

## Synthetic / fixture mode

The standard `BenchmarkRunner` provides both columns when the
universe is `[^VIX, VIX=F]`. If the runner falls back to
the offline fixture generator (no network), the synthetic
fixture generates plausible OHLCV for both tickers. The
strategy runs end-to-end in either case.
