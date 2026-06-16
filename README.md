# Market Viceroy v4

Autonomous multi-agent trading platform. Paper-first on free live data; agents
research → decide Buy/Sell/Hold → execute within **inviolable** risk limits;
tamper-evident decision journal + causal post-mortem; graduates to live only
through explicit gates. Crypto-first MVP → India → rest of world.

The authoritative product spec (PRD, build plan v2, repo audit) and the
engineering standards / non-negotiables are kept internal and are not
published to this repository.

## Status — Phase 0 (Foundations)

- `uv` workspace monorepo: ported `alphakit-*` (from
  [alphakit@659c64b](https://github.com/ankitjha67/alphakit), see
  [docs/PROVENANCE.md](docs/PROVENANCE.md)) + net-new `mv-*` typed skeletons.
- alphakit test suite green on Python **3.12**.
- CI: ruff, mypy `--strict`, pytest with the **≥85% coverage** hard gate.
- `docker compose` for ClickHouse + Postgres + Redis; secrets via `.env` /
  vault (see [docs/SECRETS.md](docs/SECRETS.md)).
- Thin end-to-end **data-pipe smoke** (`mv-failover`): one crypto instrument
  via CCXT → normalized → ClickHouse → read back.

See [docs/PHASE0.md](docs/PHASE0.md) for the exit-gate evidence.

## Quickstart

```bash
uv sync --extra dev          # install the workspace on Python 3.12

uv run pytest                # full suite + ≥85% coverage gate
uv run mypy --strict packages/
uv run ruff check .
uv run ruff format --check .

cp .env.example .env         # set local passwords
docker compose up -d         # ClickHouse + Postgres + Redis
MV_RUN_SMOKE=1 uv run mv-smoke   # CCXT -> ClickHouse round-trip (data-pipe smoke)
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
