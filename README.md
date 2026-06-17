# Market Viceroy v4

Autonomous multi-agent trading platform. Paper-first on free live data; agents
research → decide Buy/Sell/Hold → execute within **inviolable** risk limits;
tamper-evident decision journal + causal post-mortem; graduates to live only
through explicit gates. Crypto-first MVP → India → rest of world.

The authoritative product spec (PRD, build plan v2, repo audit) and the
engineering standards / non-negotiables are kept internal and are not
published to this repository.

## Status — Phase 1 (MVP: crypto-paper trading loop) complete

The end-to-end MVP loop runs on crypto data, paper only:

> Failover Governor (binance→kraken→coinbase) → all strategies → equal-weight
> ensemble → **inviolable risk gate** → NautilusTrader paper fill (fees +
> slippage + crypto-tax modeled) → **tamper-evident hash-chained journal**.

- **US-001/003/007/008** demonstrated (deterministic tests). See
  [docs/PHASE1.md](docs/PHASE1.md) for the exit-gate evidence; Phase 0 in
  [docs/PHASE0.md](docs/PHASE0.md).
- Execution spine: **NautilusTrader 1.228** (paper↔live parity via its native
  `Strategy`). Risk engine + **Operator-only kill-switch**. Failover governor
  (circuit breakers, reconciliation, staleness, health). Hash-chained journal.
- Gates on **3.12**: ~2477 passed, ~92.6% coverage (≥85 hard gate), mypy
  `--strict` clean, ruff clean. CI adds ClickHouse + Postgres service
  containers (migrations + journal round-trip + live CCXT smoke).

## Quickstart

```bash
uv sync --extra dev          # install the workspace on Python 3.12

uv run pytest                # full suite + ≥85% coverage gate
uv run mypy --strict packages/
uv run ruff check .
uv run ruff format --check .

cp .env.example .env         # set local passwords
docker compose up -d         # ClickHouse + Postgres + Redis
uv run mv-migrate            # apply the Postgres schema
MV_RUN_SMOKE=1 uv run mv-smoke   # CCXT -> ClickHouse round-trip (data-pipe smoke)
uv run mv-paper              # one live paper session (governor -> ensemble -> risk -> fills)
uv run mv-kill "reason"      # Operator kill-switch
```

## Package map (uv workspace)

| Package | Status | Responsibility |
|---|---|---|
| `alphakit-core` | ported | protocols, instruments, data structs, metrics, portfolio |
| `alphakit-strategies-*` (9) | ported | 109 strategy modules |
| `alphakit-bridges` | ported | vectorbt / backtrader / lean engine bridges |
| `alphakit-bench` | ported | benchmark/validation harness (→ validation gate, Ph2) |
| `alphakit-data` | ported | adapters + registry/cache/rate_limit (→ folds into mv-failover, Ph1) |
| `mv-failover` | skeleton + smoke | failover governor (Ph1); ships the Phase-0 data-pipe smoke |
| `mv-intelligence` | skeleton | point-in-time intelligence features (Ph3) |
| `mv-agents` | skeleton | LangGraph agents → Buy/Sell/Hold (Ph4) |
| `mv-journal` | skeleton | tamper-evident hash-chained journal (Ph1) |
| `mv-postmortem` | skeleton | attribution, mistake taxonomy, meta-learning (Ph5) |
| `mv-risk` | skeleton | risk engine + **inviolable** kill-switch (Ph1) |
| `mv-api` | skeleton | FastAPI + WebSocket (Ph1) |
| `mv-ui` | placeholder | React/Next.js Command Deck (Ph4/8) |

## License

Apache-2.0 (see [LICENSE](LICENSE)), inherited from alphakit.
