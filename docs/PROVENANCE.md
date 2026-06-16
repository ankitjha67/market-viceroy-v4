# Provenance — alphakit port

The `alphakit-*` packages under [`packages/`](../packages/) were ported into
this monorepo from the public alphakit repository.

| Field | Value |
|---|---|
| Upstream | https://github.com/ankitjha67/alphakit |
| Branch | `main` |
| Commit (pinned) | `659c64b9a637524fd48ef577042d8d543a58d544` |
| Ported on | 2026-06-16 |
| Method | Lift into monorepo (fresh history); see CLAUDE.md port decision |
| License | Apache-2.0 (carried; see [`../LICENSE`](../LICENSE)) |

## What was lifted

- `packages/alphakit-core`, `packages/alphakit-data`, `packages/alphakit-bridges`,
  `packages/alphakit-bench`, and the nine `packages/alphakit-strategies-*`
  packages — unchanged source + their tests.
- Root `tests/`, `scripts/`, `benchmarks/` — unchanged.

## What was NOT carried (re-authored or out of scope for Phase 0)

- Root `pyproject.toml` — re-authored as the Market Viceroy v4 workspace root
  (project renamed; `requires-python` bumped to `>=3.12`; ruff/mypy targets
  bumped to 3.12; `mv-*` members + their deps added; coverage source extended
  to `["alphakit", "mv"]`).
- `README.md`, `.gitignore` — re-authored for v4.
- alphakit's `docs/` (mkdocs site), `notebooks/`, `mkdocs.yml`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CITATION.cff`,
  `.github/` workflows — not carried; v4 ships its own CI (`.github/workflows/ci.yml`).

## Reconciliation decisions (PRD/repo-audit §6)

- **pandas vs Polars:** Polars in the ingestion/storage plane; pandas kept at
  the strategy-vectorization/backtest seam (alphakit's `StrategyProtocol` is
  pandas-based for vectorbt). Not forced through the contract.
- **3.10 → 3.12:** baseline suite verified green on 3.12 before integration
  (2349 passed, 35 skipped, 92.15% coverage; mypy strict clean; ruff clean).
- **Decimal vs float:** float kept inside alphakit's vectorized backtest math;
  Decimal reserved for money/PnL/fills/accounting at the execution boundary
  (Phase 1+). ClickHouse bar OHLCV are stored as `Float64` (time-series
  market data), which is not accounting.
- **FRED no-train guardrail:** `alphakit-data`'s FRED adapter is a runtime
  input only. No model may be trained/fine-tuned on FRED data (CLAUDE.md
  non-negotiable, PRD FR-D11/BR-006). Enforced in the training pipeline config
  when that pipeline is built (Phase 3).
