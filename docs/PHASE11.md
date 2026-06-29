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
