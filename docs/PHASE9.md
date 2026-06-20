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

### MLflow experiment tracking (`mv-intelligence/tracking.py`)
`log_experiment(experiment, params, metrics, tags, uri)` logs one run to a local
**SQLite** MLflow store (MLflow 3.x retired the file store) and returns the
run_id. **Opt-in + no-op by default:** with no `uri`/`MLFLOW_TRACKING_URI` it
returns `None` and touches nothing, so the per-push gate stays deterministic and
side-effect-free. It is the log point for the validation gate, governed
weight-proposals, and forecaster training. Tested against a temp store.

### Forecasting layer (`mv-intelligence/forecasting/`)
- **`GBMForecaster`** — the deterministic CI default: a **seeded** scikit-learn
  `GradientBoostingRegressor`. **Point-in-time** (`fit_window` slices to rows
  strictly before the as-of — no look-ahead), **FRED-no-train** (`guard_training_sources`
  rejects FRED-derived sources, FR-D11/BR-006), reproducible (identical
  predictions across runs).
- **`FinBERTSentiment`** / **`LSTMForecaster`** — the optional offline deep
  forecasters (`forecasting-deep` extra: torch/transformers). They run **offline
  only** (model load/inference `# pragma: no cover`) and **fall back
  deterministically** when the extra is absent (the CI default): FinBERT → the
  Phase-3 rule-based lexicon; LSTM → the seeded GBM. The fallback selection, the
  FinBERT signed-label mapping, and the FRED guard are unit-tested. Real wiring
  with a real fallback — not a stub.

### Dependencies
`scikit-learn` + `mlflow` enter the core lock (build time ↑). **torch/transformers
stay in the `forecasting-deep` optional extra**, *not* installed by the per-push
CI (`uv sync --extra dev`), so CI runs the deterministic fallback path and stays
light.

### Verification (9B, all green)
MLflow temp-store logging round-trip; GBM determinism + as-of/no-look-ahead +
FRED-no-train; the deep forecasters' offline fallbacks + FinBERT label mapping.
Full Python gate: ruff / mypy --strict (810 files) / **pytest 2725 passed**,
coverage 93%. The deep extra is not exercised in CI by design.

## Excluded (flagged, not built)
- **India private-repo content** — blocked; share the four private repos to fold
  in the india-preopen quant engine + nse-market-intel research agent.
- **Real-money go-live** — the Operator's manual, funded action; the agent never
  automates real-money orders. The graduation machinery + runbook exist (Phase 7).
