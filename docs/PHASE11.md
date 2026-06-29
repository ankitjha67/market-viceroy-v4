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

## 11A.3 — Trade blotter (shipped)

The "what did we actually trade" record:

- `mv-api/blotter.py` (pure, tested) — each FIFO-reconstructed closed round trip as
  a row: direction, qty, entry/exit, net PnL, fees, return, and hold duration.
- `GET /api/v1/trades` (`ApiState.trades_provider`).
- `mv-ui` — a **Closed trades** panel on the Command Deck: newest-first table of
  closed/instrument/side/entry/exit/P&L/return/held.

This completes **11A**.

## 11B.1 — Multi-instrument engine (shipped)

The loop is no longer single-symbol. It trades a **watchlist concurrently**:

- `mv-api/instruments.py` (tested) — `crypto_instrument(symbol)` builds a Binance
  `CurrencyPair` for any `BASE/USDT` from NautilusTrader's currency registry, so
  the loop is no longer pinned to the BTC/USDT test preset.
- `mv-serve --symbols` — a default watchlist of 11 liquid USDT majors (BTC, ETH,
  SOL, BNB, XRP, ADA, DOGE, AVAX, LINK, DOT, LTC), fully overridable. Each tick
  runs a paper session **per symbol into one shared journal** with the capital
  split across symbols (`start_equity / n` per slice); a bad/illiquid symbol is
  skipped for that tick without breaking the others.
- Because everything lands in one journal **tagged by instrument**, the existing
  snapshot / metrics / blotter helpers **aggregate across the book automatically**
  — the positions table now shows a row per instrument, equity sums across them,
  and the blotter spans all symbols. The price chart focuses on `--symbol` (its
  candles + its own fills); the regime chip reflects that symbol.
- `mv-ui` — the mode strip shows an `N markets` chip (the watchlist).

Note: every pair on the exchange is impractical (rate limits + dust positions on
a ₹5,000 book), so the default is a broad liquid set and `--symbols` takes any
list. More symbols = a heavier tick.

Next: **11B.2** — a chart symbol-selector + a per-instrument P&L/exposure panel.
