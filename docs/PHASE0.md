# Phase 0 — Foundations: exit-gate evidence

Phase 0 exit gate (PRD §12): **one instrument streams end-to-end** and
**alphakit tests green on 3.12**. Deliverables 1–5 from the kickoff brief.

## Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | uv workspace monorepo (alphakit-* ported + mv-* typed skeletons) | done |
| 2 | alphakit ported in; suite green on Python 3.12 | done |
| 3 | CI: pytest (≥85% coverage gate), mypy --strict, ruff — on 3.12 | done (`.github/workflows/ci.yml`) |
| 4 | docker-compose (ClickHouse + Postgres + Redis) + secrets/vault approach | done (`docker-compose.yml`, `docs/SECRETS.md`) |
| 5 | Thin E2E smoke: CCXT → normalize → ClickHouse → readable | done (`mv-failover`; live round-trip via CI smoke job) |

## Evidence (local, Python 3.12.13)

- **Suite:** `uv run pytest --cov=alphakit --cov=mv --cov-fail-under=85`
  → **2363 passed, 36 skipped**, total coverage **92.17%** (gate ≥85%).
  Skips are network/optional-dep tests (incl. the gated smoke integration
  test) — none are failures.
- **Types:** `uv run mypy --strict packages/` → clean.
- **Lint:** `uv run ruff check .` → All checks passed;
  `uv run ruff format --check .` → all files formatted.
- **alphakit baseline** (unmodified, pre-integration) on 3.12: 2349 passed,
  92.15% coverage — confirming the port did not regress the source.

## The data pipe (deliverable 5)

`mv-failover` ships the thin end-to-end smoke:

```
CCXT (public OHLCV) -> normalize_ohlcv (Polars, canonical bars) -> ClickHouse.bars -> read back
```

- The **pure transform** (`normalize_ohlcv`) is fully unit-tested locally
  (100% line+branch coverage), deterministic, no I/O.
- The **live round-trip** (CCXT fetch → ClickHouse write → read-back) is the
  `RoundTrip` in `pipeline.py`, run by:
  - the CI **`smoke`** job (ClickHouse service container, `MV_RUN_SMOKE=1`,
    runs the integration test + `mv-smoke` CLI), and
  - locally via `MV_RUN_SMOKE=1 uv run mv-smoke` once `docker compose up -d`
    is running.

> **Docker note:** this host has no Docker installed, so the live round-trip
> is proven by the CI smoke job (per the agreed approach), not locally. Every
> other gate (suite, coverage, mypy, ruff) is verified locally on 3.12.

## Non-negotiables honored in Phase 0

- **Risk rails:** `mv-risk` is an empty typed skeleton; no risk logic exists
  to weaken. The kill-switch/limits are built (inviolable) in Phase 1.
- **Point-in-time / FRED no-train:** no model training exists yet; the FRED
  adapter is ported as a runtime-only input with the no-train rule recorded
  (`docs/PROVENANCE.md`).
- **Decimal vs float:** float kept only in alphakit's vectorized backtest
  math; ClickHouse bar OHLCV stored as `Float64` (market data, not
  accounting). Decimal is reserved for money/PnL/fills (Phase 1+).
- **No secrets in code:** config via env / `.env` (`pydantic-settings`);
  `.env` git-ignored; the smoke uses keyless public endpoints.
- **No slop:** skeletons are explicitly labeled stubs; no placeholder passed
  off as an implementation; no emojis/AI-sparkle.

## Not built (correctly deferred — out of Phase 0 scope)

Failover governor, risk engine, journal, agents, validation-gate extensions,
intelligence/NLP, the React UI, the point-in-time CI leakage check (FR-V6,
Phase 3), and the relational/feature schemas beyond the `bars` table — each is
introduced in its owning phase.
