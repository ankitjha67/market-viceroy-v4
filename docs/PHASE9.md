# Phase 9 — Finish deferred scope (incremental + heavy)

Phase 9 closes the deferred backlog in two tracks. **9A (incremental)** and
**9B (heavy: MLflow + forecasting)** ship as separate PRs. Two items are
**excluded and flagged, not built**:

- **India private-repo content** — *blocked*: the four private repos (india-preopen
  quant engine, nse-market-intel) have not been provided. The Angel One adapter +
  `india.prices` domain are ready; the repo-sourced strategies/research agent wait
  on the Operator sharing the repos.
- **Real-money go-live** — the Operator's manual, funded action and a
  non-negotiable: **the agent never places real-money orders.** The graduation
  machinery + runbook already exist (Phase 7).

## Track 9A — incremental

### Backing endpoints (decoupled, injected providers)
`GET /api/v1/risk/limits` (limits + live exposures), `GET /api/v1/journal`
(filter by `kind` + text `q` over the hash-chained journal), `GET /api/v1/settings`
(read-only config — ladders / LLM routing / mode; **never secrets**).

### WebSocket `/ws/stream`
A FastAPI websocket + an in-process `BroadcastHub` (`mv/api/ws.py`): the loop
publishes ticks / decisions / fills / source-health; every connected client
receives them (bounded queues, drop-on-full so a slow consumer never blocks the
loop). The UI `useStream` hook subscribes and **falls back to REST polling** on
disconnect — the stream is an optimization, never the only path.

### The six remaining UI screens (`mv-ui`)
Strategy Lab (`/strategies`), Post-Mortem Room (`/postmortem`), Arbitrage Monitor
(`/arbitrage`), Risk Console (`/risk`), Journal Explorer (`/journal`, with a
kind + text toolbar), Settings (`/settings`). Each consumes existing/9A.1
endpoints, renders all four states via `<StatePanel>`, and follows the editorial
anti-slop system. The nav now lists all nine screens.

### Phase-7 learning follow-ons
- **De-graduation** (`mv-risk/degraduation.py`): `evaluate_degradation(LiveRecord)`
  reverts a graduated strategy to paper on a projection-honesty breach, a live
  drawdown breach, or a risk-limit breach — **only ever de-risks**, journaled.
- **Cost-model write-back (FR-X4):** `alphakit.bridges.cost_model.set_slippage_calibration`
  / `calibrated_slippage_bps` — the post-mortem's `recalibrate_slippage` writes the
  empirical per-venue slippage back so the live cost model reads it instead of a
  stale estimate. It **informs** the model; it never relaxes a limit.

### LLM per-agent routing config (FR-A7)
`mv/agents/llm/config.py` — `router_from_config(mapping)` builds an `LLMRouter`
from `{agent: {provider, model}}`; unconfigured agents stay deterministic
(FR-A9). Opt-in; keys are read from env inside the adapters, never from config.

### Full FR-S5 (`mv-failover/strategy_feeds.py`)
`domain_for_strategy(asset_class, region)` resolves the registered governor
domain that serves a strategy's bars (crypto / US / India / FX), so any catalog
strategy pulls real feeds through the governor (failover, breaker,
reconciliation) instead of a fixture. Unmapped classes return `None` honestly.

### Verification (9A, all green)
- Backend: endpoint + WS TestClient tests; de-graduation + calibration write-back
  + LLM-config + FR-S5 unit tests. Full Python gate (ruff / mypy --strict / pytest
  **2714 passed**, coverage 93%).
- Frontend: **24 Vitest tests** (four states across all nine screens + the API
  client), `tsc --noEmit` + `next lint` clean, `next build` compiles all 9 routes.

## Track 9B — heavy (MLflow + forecasting)

See the 9B section appended with PR 9B: MLflow experiment tracking (local file
store, opt-in) and the forecasting layer (a seeded scikit-learn GBM forecaster —
point-in-time, leakage-checked, never trained on FRED — with LSTM/FinBERT as an
optional offline `forecasting-deep` extra and a deterministic fallback).
