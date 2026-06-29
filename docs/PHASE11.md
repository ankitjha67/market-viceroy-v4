# Phase 11 — The professional desk

Surfaces the platform's existing sophistication (validation gate, risk engine,
post-mortem, regime-adaptive ensemble) in a **trading-desk-grade** dashboard and
broadens what it trades — turning the "toy-looking" single-instrument,
equity-squiggle deck into something a real desk would recognise. Paper-first
throughout; strategies still earn `active` only via the validation gate; regime
weighting stays market-driven (no PnL-chasing); risk rails inviolable.

Delivered in three slices, each independently green:

- **11A — Real chart + metrics:** a candlestick **price chart** with the
  strategies' indicators, volume, and BUY/SELL **trade markers**; a live
  performance-**metrics** panel (Sharpe/Sortino/Calmar/win-rate/profit-factor/…);
  a **trade blotter** of closed round-trips.
- **11B — Breadth:** a multi-instrument watchlist (BTC/ETH/SOL/…) with
  per-instrument + per-strategy P&L, and an expanded strategy roster.
- **11C — Order realism + deep analytics:** limit/stop/trailing orders + an
  open-orders panel; rolling Sharpe, regime history, MAE/MFE, exposure heatmap.

## 11A.1 — Candlestick price chart with trade markers (shipped)

The deck now shows **what the market did and where we traded**, not just an
equity line:

- `mv-api/chart.py` (pure, tested) — turns the loop's INR OHLCV frame + journaled
  fills into the chart shapes: epoch-second **candles**, a **volume** series, and
  **BUY/SELL markers** placed on the bar each order filled. The loop stamps each
  fill with its `bar_ts` so markers land on the right candle.
- `GET /api/v1/ohlcv` (`ApiState.ohlcv_provider`) — recent candles + markers,
  swapped in each `--watch` tick alongside portfolio / positions.
- `mv-ui` `PriceChart` — lightweight-charts candlesticks + volume pane + **EMA 12 /
  EMA 26** overlays (the lines the trend strategies cross, `lib/indicators.ts`) +
  arrow markers at fills; times in the viewer's local zone. New hero panel on the
  Command Deck, above the equity curve.

Gates: `ruff` + `mypy --strict` (full tree) + backend tests (`chart` + loop
`bar_ts`); `tsc` + `eslint` + `vitest` (PriceChart + EMA + dashboard) +
`next build`.

## 11A.2 — Live performance metrics panel (shipped)

The deck now reads like a real desk's stats, not three numbers:

- `mv-api/metrics.py` (pure, tested) — two honest sources, kept separate from the
  backtest/validation Sharpe (that stays the Strategy Lab gate): **trade stats**
  over the journal's closed round trips (win rate, profit factor, expectancy, avg
  and largest win/loss, a per-trade Sharpe/Sortino) and **equity-curve risk** over
  the live session (max drawdown, total return). Stdlib only; money `Decimal`.
- `GET /api/v1/metrics` (`ApiState.metrics_provider`) — recomputed each tick from
  the equity history + closed trades.
- `mv-ui` — a **Performance** panel on the Command Deck: Sharpe, Sortino, win rate,
  profit factor, expectancy, total P&L, max drawdown, trades, avg win/loss.

Honesty note: these are **session-to-date** stats over paper round trips, distinct
from a strategy's gated backtest Sharpe. Empty until the first trip closes.
