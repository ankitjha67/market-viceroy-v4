# Phase 6 — Breadth (India + US + FX) + executable arbitrage: exit-gate evidence

Phase 6 exit gate (PRD §12, US-009/US-011, BR-007): **multi-asset paper stable;
the arbitrage monitor shows honest after-cost edges.** Grew breadth behind the
existing contracts — new regional data adapters + the executable crypto
arbitrage engine — without rearchitecting.

## Regional data adapters (US + India + FX)

New `BarFeed` adapters in `mv-failover/adapters/`, each following the
`CcxtBarFeed` pattern — live fetch `# pragma: no cover` (offline), **pure JSON
reshape** unit-tested on fixtures, keys read from env at call time (never
hardcoded, CLAUDE.md #6):

| Adapter | Source | Shape | Key env |
|---|---|---|---|
| `FinnhubBarFeed` | US equities (IEX RT) | column arrays, seconds | `FINNHUB_API_KEY` |
| `AlpacaBarFeed` | US equities (fallback) | row objects, RFC-3339 | `ALPACA_API_KEY`/secret |
| `AngelOneBarFeed` | India equities (SmartAPI) | rows, IST-offset ISO | `ANGELONE_API_KEY`/token |
| `FrankfurterRateFeed` | FX ECB rates (keyless) | rate→flat bar | — |

## Governor breadth (same failover, new domains)

`registry.py` adds `US_PRICES` (`equity/us`), `INDIA_PRICES` (`equity/india`),
`FX_RATES` (`fx/global`); `ladders.py` registers them in `build_default_registry`
— US: finnhub→alpaca, India: angelone, FX: frankfurter. The **same** router /
circuit-breaker / staleness / reconciliation governs them. A test proves a US
domain fails over finnhub→alpaca exactly like the crypto ladder, and a **catalog
strategy (`SMACross1030`) runs on governor-served US bars** unchanged (FR-S5 /
US-009 — breadth without rearchitecting).

## Executable arbitrage (US-011, BR-007, §1.2)

`mv-intelligence/arbitrage/` — pure detectors, every edge shown **after** cost:

- **cross_exchange** — cheapest-ask → dearest-bid across venues, after taker fees
  (both legs) + liquidity-aware slippage + transfer cost.
- **funding_rate** — perp-vs-spot funding + basis, after the four-leg fees.
- **triangular** — one-unit cycle product, after a per-leg fee.

Each returns an `ArbOpportunity(gross_edge_bps, after_cost_edge_bps,
executability)`. The **Red/Amber/Green** rule (`classify_executability`): Green =
positive after-cost + executable + deep + low-latency; Amber = marginal/thin/
slow; **Red = non-positive after cost OR not executable**. **Cross-border
dislocations are monitor-only — always Red, never routed to execution** (LRS/FEMA,
§1.2). Reuses the Phase-1 `cost_model` (`venue_fees`, `slippage_bps`).

`GET /api/v1/arbitrage` serves the ranked opportunities (injected provider, API
decoupled). The offline `scripts/run_arbitrage.py` prints the monitor — e.g. a
10bps gross cross-exchange spread resolves to **−69bps after cost → RED**, while
a 100bps spread is **+58bps → GREEN**; a 180bps cross-border gross is **RED
(monitor-only)**. Honest after-cost edges — the gate.

## Non-negotiables honored

- **Arbitrage executability honesty (BR-007):** gross spreads are never shown as
  edge; every opportunity carries its after-cost edge + R/A/G.
- **No executable global cross-border arb (§1.2):** cross-border is monitor-only,
  always Red, never executed.
- **Secrets in a vault (#6):** broker/market keys read from env at call time;
  live fetch offline, CI on fixtures.
- **Same contracts / failover discipline:** new feeds implement `BarFeed` and
  plug into the existing governor — no parallel data path. **Decimal** for all
  money/edges.

## Verification (all green)

- **Unit (CI, no network):** each adapter's JSON reshape (fixture → canonical
  bars; timestamp math); the new ladders + a US finnhub→alpaca failover walk; a
  catalog strategy on governor-served US bars; the arb engine (after-cost edges,
  R/A/G, thin-spread→Red, cross-border→monitor-only Red); the `/arbitrage`
  endpoint (fakes).
- **Offline:** `scripts/run_arbitrage.py` monitor demo; gated live-adapter smokes
  with keys.
- Gates: full-tree `ruff check` + `ruff format`, `mypy --strict`, `pytest` with
  the ≥85% coverage gate.

## Scope boundaries (deferred by design)

- **India strategy content deferred** — the india-preopen quant engine + the
  nse-market-intel research agent (the four private repos) fold in once the
  Operator shares them; Phase 6 lands the **Angel One adapter + `india.prices`
  domain** they plug into, with no fabricated strategy stubs.
- Live broker/market trading + cross-border real-money stay Phase 7+ (SEBI algo,
  LRS/FEMA); this phase is paper + monitor.
- Full FR-S5 (all 92 synthetic strategies wired to real feeds) is incremental;
  Phase 6 proves the seam on a representative US symbol.
- The Arbitrage Monitor + multi-asset React UI is Phase 8; Phase 6 ships data + API.
