# Market Viceroy v4

Autonomous multi-agent trading platform. Paper-first on free live data; agents
research → debate → decide Buy/Sell/Hold → execute within **inviolable** risk
limits; tamper-evident decision journal + causal post-mortem; graduates to live
only through explicit, Operator-signed gates. Crypto-first → India → US/FX.

The authoritative product spec (PRD, build plan, repo audit) and the engineering
standards / non-negotiables are kept internal and are not published here.

## Status — Phases 0–9 complete

The full platform is built end-to-end (paper-first; no real-money orders are
ever placed autonomously). Each phase shipped behind hard CI gates — `ruff`,
`mypy --strict`, `pytest` ≥85% coverage, plus a frontend gate (`eslint` / `tsc`
/ `vitest` / `next build`). See `docs/PHASE0.md … PHASE9.md` for per-phase
exit-gate evidence.

```
Failover Governor (multi-source, circuit-broken) → point-in-time features
  → multi-agent pipeline: Research → Bull/Bear debate → Research Manager
     → Risk veto (inviolable) → Portfolio Manager → Buy/Sell/Hold
  → NautilusTrader execution (paper↔live parity; modeled fees/slippage/tax)
  → tamper-evident hash-chained journal
  → Post-Mortem: causal attribution + mistake taxonomy + counterfactual replay
  → governed, propose-only meta-learning (held-out validated; human-gated to live)
```

### What's built
- **Data plane + Failover Governor** — circuit breakers, primary→fallback
  ladders, reconciliation, staleness, health. Adapters: crypto (CCXT), US
  (Finnhub→Alpaca), FX (Frankfurter), **India equities (Dhan→Upstox→Kotak→
  Zerodha→Angel One)**.
- **Validation gate** — walk-forward + regime + deflated Sharpe + Monte-Carlo;
  honest `active`/`observe`/`failed`. Synthetic results can never reach `active`.
- **Intelligence** — point-in-time feature store (as-of joins, CI leakage check),
  indicators, SEC-EDGAR fundamentals, rule-based sentiment, **FRED no-train**
  guardrail; **forecasting** (deterministic GBM; optional offline FinBERT/LSTM).
- **Agents** — a real LangGraph pipeline (deterministic-first; per-agent hybrid
  LLM routing wired, offline) producing the journaled Buy/Sell/Hold.
- **Risk** — pre-trade limits (position/exposure/concentration/daily-loss/
  drawdown/Kelly), **Operator-only kill-switch**, capped-live guard (BR-005).
- **Post-Mortem & learning** — attribution that sums to net, mistake taxonomy,
  counterfactual replay, improvement ledger, **propose-only** governed weights;
  live-slippage recalibration; projection-honesty tracking.
- **Gated live** — Conservative graduation bar + §13 compliance checklist +
  per-strategy Operator sign-off; de-graduation on breach. **No real-money
  orders are ever automated.**
- **Executable arbitrage** — crypto cross-exchange / funding / triangular, shown
  after cost with Red/Amber/Green executability; cross-border is monitor-only.
- **Command Deck UI** — a React/Next.js app (9 screens): Command Deck, Agent
  Room, Strategy Lab, Post-Mortem Room, Arbitrage Monitor, Risk Console, Journal
  Explorer, Source Health, Settings. REST polling + an authed WebSocket stream;
  editorial, anti-slop design.
- **MLflow** experiment tracking (opt-in, local SQLite store).

## Security posture
Single-operator self-host. Mutating endpoints (kill / reset / graduate / replay)
and the WebSocket are **Operator-token-authed** (constant-time compare). Reads
are open but behind an explicit, non-wildcard CORS allow-list — bind the API to
`127.0.0.1` (or an authenticating proxy) before any non-local exposure. Secrets
live in env/vault, **never in code**; exchange keys are scoped, withdrawal-
disabled, IP-allowlisted. All SQL is parameterized.

## Quickstart

```bash
uv sync --extra dev              # install the Python workspace on 3.12
uv run pytest                    # full suite + ≥85% coverage gate
uv run mypy --strict packages/
uv run ruff check . && uv run ruff format --check .

cp .env.example .env             # set local passwords + any API keys
docker compose up -d             # ClickHouse + Postgres + Redis
uv run mv-migrate                # apply the Postgres schema
uv run mv-paper                  # one live paper session (governor → agents → risk → fills)
uv run mv-kill "reason"          # Operator kill-switch

# Command Deck UI
cd packages/mv-ui && npm ci && npm run dev   # http://localhost:3000
```

Offline demos: `scripts/run_agents.py` (agent transcript), `scripts/run_postmortem.py`
(attribution + learning), `scripts/run_arbitrage.py` (after-cost arb monitor).

## Package map (uv workspace)

| Package | Responsibility |
|---|---|
| `alphakit-core` | protocols, instruments, data structs, metrics, portfolio |
| `alphakit-strategies-*` (9) | 109 strategy modules (`StrategyProtocol`) |
| `alphakit-bridges` | NautilusTrader paper/live bridge + cost model; vectorbt/backtrader/lean |
| `alphakit-bench` | validation gate (walk-forward, regime, deflated Sharpe, Monte-Carlo) |
| `alphakit-data` | data adapters + registry/cache/rate-limit |
| `mv-failover` | failover governor + regional adapters (crypto/US/India/FX) |
| `mv-intelligence` | point-in-time features, sentiment, forecasting, MLflow tracking |
| `mv-agents` | LangGraph multi-agent pipeline + LLM seam → Buy/Sell/Hold |
| `mv-journal` | tamper-evident hash-chained decision journal |
| `mv-postmortem` | attribution, mistake taxonomy, replay, governed meta-learning |
| `mv-risk` | risk engine, inviolable kill-switch, graduation/de-graduation, live guard |
| `mv-api` | FastAPI + WebSocket (Operator-authed mutations) |
| `mv-ui` | React/Next.js Command Deck (9 screens) |

## License

Apache-2.0 (see [LICENSE](LICENSE)), inherited from alphakit.
