# Phase 12 — US options / GEX (Vol Desk)

A new **asset class + data plane**: single-stock US options driven by **Gamma
Exposure (GEX) and dealer positioning** — the "Vol Desk" system. It fits the
platform's *framework* well (mechanical, filter-graded, regime-gated,
stop-managed — exactly what the seam + validation gate + risk engine + journal
host), but its **inputs** are a domain MV4 has scaffolding for and has never
populated: US-options dealer-gamma data, which is largely **paid and keyed**.
This phase builds that plane and runs Vol Desk through the same honesty gates as
every other strategy.

## What the strategy is (source spec, condensed)
Enter just above the positive transition level (pTrans) on a name whose dealer
delta is flipping bullish with strong options structure, and ride to +GEX (T1).
Five entry filters (grade ≥ 9/11, db_change ≥ 0.50 with DEEP/sustained
exceptions, COTMP cushion ≥ 2% with DEEP/high-db relaxation, no spike-crash, R/R
≥ 2), a confirmed 5-min-after-open close as the trigger, a four-stop exit
framework (nTrans close, −10% below pTrans, day-7 time stop, stalling rule) with
a single T1 discretion (bank or lock-and-ride to T2), and a daily 3-gate regime
overlay (SPY/QQQ, breadth, VIX dealer positioning; HYG/sector as a sizing
overlay). Two tracks: mechanical **P2P** (2/3 gates) and **B-Continuation** (3/3,
Minervini ≥ 100).

## Non-negotiables (apply with full force here)
- **Validated, not proven (#4).** The source's edge is *"db_change ≥ 0.50 → 100%
  win rate over two weeks."* That is a tiny sample; it **cannot** reach `active`
  until it clears the validation gate (walk-forward + deflated Sharpe + Monte
  Carlo + regime) on real GEX history. The platform holds it at `observe` and
  reports the honest result — this is the whole point of dropping it in here.
- **Point-in-time everything (#2).** GEX levels, grades, and the evening screen
  are as-of the session they were knowable; the entry uses the confirmed candle,
  never a pre-market snapshot. No look-ahead in the screen or the backtest.
- **Secrets in a vault (#6).** The options-data vendor key is scoped, read from
  env at call time, never in code.
- **Inviolable risk rails (#1).** Vol Desk's four stops are *strategy* exits; the
  `RiskEngine` (kill-switch, daily-loss, drawdown, exposure caps) still sits on
  top. Live is Operator-gated (Phase 7), capped, never automated by the agent.

## Build order
- **12.0 — Decision-logic scaffold (SHIPPED, this PR).** `mv-intelligence/gex/`:
  the gamma-screen record (`GammaRow`), the five-filter grading
  (CONFIRMED/PENDING/BLOCKED), the four-stop exit framework, and the 3-gate regime
  overlay — all pure, deterministic, and tested against a **mock** gamma screen.
  Proves the mechanical logic now, before the data question is settled.
- **12.1 — Options-GEX data adapter.** A `DataFeedProtocol` adapter for an
  options-chain / GEX source (OPRA-derived, or a vendor: SpotGamma / Unusual
  Whales / Menthor Q) + a `us.options.gex` governor domain with a failover
  ladder. Live fetch offline-gated; normalization tested on a fixture. **The
  vendor + cost decision is the fork everything else waits on.**
- **12.2 — GEX computation engine.** Options chain → dealer gamma → the transition
  levels (pTrans/nTrans/zeroGEX/+GEX/COTMP/COTMC) + grade + db_change, as
  point-in-time feature rows into the feature store. The heaviest net-new module.
- **12.3 — Evening screen.** The 700-name gamma screen + the P2P filtered list as
  a screener over the feature store (reuses the Strategy Lab surface).
- **12.4 — Regime overlay wiring.** SPY/QQQ/VIX/HYG breadth feeds → the Phase-12
  regime detector (the `regime.py` gate here) → entry approval per track.
- **12.5 — Seam + execution.** Vol Desk is **not** an OHLCV `StrategyProtocol`
  (it is row/event-based on the screen) — so add a GEX-native strategy adapter to
  the seam, US-session intraday entry (5-min-after-open), and equity/option
  execution via the NautilusTrader bridge (paper first).
- **12.6 — Validation + docs.** Run the gate across regimes; report the honest
  `active`/`observe` verdict; runbook + memory.

## Flags / risks
- **Data is paid + unbuilt.** This is the gating dependency; nothing downstream is
  free like the crypto feeds. Pick the vendor first.
- **New seam.** The OHLCV `StrategyProtocol` doesn't fit GEX; 12.5 adds a
  row-based adapter — a real design addition, kept additive to the 3-protocol seam.
- **US-session + options execution** differ from the 24/7 crypto spot loop.
- **The "100% over two weeks" claim is the thing the gate exists to test** — treat
  it as a hypothesis, not an edge, until walk-forward says otherwise.

## 12.0 — what shipped
`mv-intelligence/gex/`: `types.GammaRow` (+ derived db_change / cushion / R/R),
`grading.grade_setup` (the five filters → verdict), `exits.evaluate_exit` (the
four stops + T1/T2), `regime.regime_gate` (the 3-gate overlay + track minimums),
`mock_feed.mock_gamma_screen`. Tested: 23 cases across grading (each filter +
DEEP/pegged exceptions + PENDING/CONFIRMED), exits (each stop + hold/watch), and
the regime gate (2/3 vs 3/3 tracks). `ruff` + `mypy --strict` (full tree) green.
Not wired to the loop/UI — the logic scaffold only, pending the data plane.
