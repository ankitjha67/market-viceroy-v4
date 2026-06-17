# Phase 1 — Data plane + Failover + Execution + Risk + Journal (crypto, paper): exit-gate evidence

Phase 1 exit gate (PRD §12): **US-001 / US-003 / US-007 pass**, a forced
primary-source kill fails over seamlessly, and every decision is
journaled/replayable. The MVP loop runs end-to-end on crypto data, paper only.

## The MVP loop

```
Failover Governor (binance->kraken->coinbase) -> live bars (point-in-time, provenance)
  -> ALL MVP crypto strategies -> equal-weight ENSEMBLE -> BUY/SELL/HOLD (+conviction/dissent)
  -> Risk Manager (INVIOLABLE veto + kill-switch)
  -> NautilusTrader paper venue (same code paper<->live) -> fill (maker/taker fees; slippage + crypto-tax modeled)
  -> tamper-evident hash-chained Journal (every step + point-in-time snapshot)
  -> attribution stub
```

## Acceptance criteria — demonstrated (deterministic, offline)

| Story | Demonstration |
|---|---|
| **US-001** MVP loop | `mv-api/tests/test_paper_loop.py` — governor bars → strategies → ensemble → risk gate → NautilusTrader paper fill → journaled decisions/risk/executions; long position opened; `journal.verify()` intact. |
| **US-003** failover | `mv-failover/tests/test_router.py` — forced primary failure / staleness → fallback serves within one call, switch logged; open breaker skips a dead source; cross-source disagreement → data-quality event + halt. |
| **US-007** risk | `mv-risk/tests/test_engine.py`, `test_kill_switch.py`, and the API `test_app.py` — every hard limit vetoes with the named breach; kill-switch is terminal and Operator-only to reset (401 without the token). |
| **US-008** journal | `mv-journal/tests/test_chain.py` — payload tamper and broken links both detected; `test_store_integration.py` proves the chain survives a Postgres round-trip. |

## Gates (local, Python 3.12.13)

- **Suite:** `uv run pytest --cov=alphakit --cov=mv --cov-fail-under=85`
  → ~**2477 passed, 36 skipped**, coverage ~**92.6%** (gate ≥85).
- **Types:** `uv run mypy --strict packages/` → clean (~703 files).
- **Lint:** `uv run ruff check .` + `ruff format --check .` → clean.

## CI (`.github/workflows/ci.yml`)

- `lint` — ruff + ruff-format + mypy --strict.
- `test` — pytest with the ≥85% coverage hard gate (the deterministic MVP loop
  runs here — no Docker).
- `integration` — ClickHouse + Postgres service containers: applies the
  Postgres migrations (`mv-migrate`), runs the **journal Postgres round-trip**
  and the live **CCXT→ClickHouse** smoke (+ the `mv-smoke` CLI).

## Non-negotiables honored

- **Inviolable risk rails:** the risk engine gates every order; the kill-switch
  rejects all trading and only the Operator (authed) re-enables. Every
  veto/kill/halt is journaled.
- **No naive PnL-chasing:** the executed decision is a governed equal-weight
  ensemble; "pick the best performer" is explicitly deferred to Phase-5
  governed meta-learning.
- **Decimal for money:** risk limits, sizing, fees, and fills are Decimal;
  NautilusTrader's money model is Decimal-precise. `float` stays in alphakit's
  vectorized backtest math only.
- **Point-in-time:** the loop only ever sees bars through the current bar; the
  journal stores the exact snapshot each decision saw.
- **No slop:** the attribution decomposition and the LangGraph agents are
  labeled stubs/baselines, not passed-off implementations.

## Engine / design decisions (Phase 1)

- **NautilusTrader** `1.228.0` is the execution spine (validated by the Step-0
  spike on Windows/3.12). Its native `Strategy` is the paper↔live seam — orders
  are submitted inside the engine loop — so no external-submit executor
  protocol was added. Paper engines run with `bypass_logging` so multiple
  engines coexist in one process.
- **`httpx2`** (not `httpx`) is the test-client dependency — this environment's
  starlette dropped `httpx`.

## Deferred (correctly out of Phase 1 scope)

Validation gate + catalog port (Phase 2); intelligence/NLP, point-in-time
feature store + CI leakage check (Phase 3); LangGraph multi-agent debate
(Phase 4); attribution decomposition, mistake taxonomy, counterfactual replay,
governed meta-learning (Phase 5); India/US adapters + arb (Phase 6); live
trading + graduation (Phase 7).

## Local run (optional, needs Docker)

```bash
cp .env.example .env
docker compose up -d
uv run mv-migrate            # apply the Postgres schema
uv run mv-paper             # one live paper session via the governor
```
