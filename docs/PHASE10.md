# Phase 10 — Live INR Command Deck: unified dashboard + continuous tracking

Supersedes the static, USD-scale Command Deck. The platform now runs
**continuously**, denominates everything in **INR from a ₹5000 start**, and is
rendered in a single **unified live dashboard** drillable to the most granular
level. Delivered in three independently-green PRs (backend → dashboard → docs).

## Exit-gate evidence

**Continuous, in INR.** `mv-serve --watch` re-runs the paper session every
`--interval` seconds over a window that grows from launch, so equity accumulates
from **₹5000**. Every price is converted USDT→INR via a live USD/INR rate from the
FX governor (Frankfurter; fixed `MV_USD_INR_FALLBACK`, default ₹83, offline) —
scaling all prices by one constant is signal-neutral, so the **whole pipeline**
(journal, fills, decisions, positions, equity) is in INR. At ₹5000 the crypto
positions are small fractions of a coin; the `%` risk caps are currency-agnostic,
so they scale.

**Time series for the curve.** Each tick appends `{ts, equity, day_pnl, decisions,
fills, open_positions}` to an in-memory history buffer, served at
`GET /api/v1/portfolio/history`. The UI charts it (lightweight-charts) — the live
equity curve updates each tick until the Operator halts the loop (which pauses it).

**Unified dashboard.** The home screen (`LiveDashboard`) shows ₹ equity / P&L /
drawdown, a mode strip (paper · engine · symbol · timeframe · FX), the kill-switch,
the equity curve, open positions, the Buy/Sell/Hold feed, models & strategies,
risk & exposure, learning, and source health — each tile a four-state `StatePanel`
that drills into one of the 9 detail screens.

## What shipped

- `mv-api/fx.py` — `usd_inr_rate` (live FX + fallback), `scale_prices`, `latest_rate` (pure, tested).
- `mv-api/bars.py` — `merge_bars` growing-window helper (pure, tested).
- `mv-serve --watch` — INR + ₹5000 + growing window + history; `GET /api/v1/portfolio/history` (`ApiState.portfolio_history_provider`); `/settings` exposes `currency`/`fx_usd_inr`. `mv-paper` runs in ₹.
- `mv-ui` — `LiveDashboard` (new home) + `EquityChart`; `useHistory`; `formatMoney` defaults to INR (`en-IN`); the old Command Deck component subsumed.
- Docs refreshed to INR + continuous + the dashboard (this set; the per-phase history kept).

## Gates

Backend: `ruff`, `mypy --strict`, `pytest` ≥85% (new `fx` / `bars` / history tests).
Frontend: `eslint`, `tsc`, `vitest` (LiveDashboard four-state + EquityChart mocked +
INR format), `next build`. Paper-only throughout; no real-money order; the
inviolable kill-switch pauses the loop.
