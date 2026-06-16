-- Market Viceroy v4 — ClickHouse time-series schema (Phase 0).
--
-- Only the `bars` table is needed for the Phase-0 smoke (one crypto
-- instrument pulled via CCXT, normalized, written here, read back).
-- `ticks`, `order_book_snapshots`, `features`, and `equity_curves`
-- (PRD §6.2) are added in their owning phases — not pre-built here.
--
-- `source` is recorded on every row for provenance / failover audit.
-- OHLCV are stored as Float64: this is market-data storage in the
-- time-series plane, NOT money/PnL/accounting (which use Decimal at the
-- execution + accounting boundary, per the engineering standards).

CREATE DATABASE IF NOT EXISTS marketviceroy;

CREATE TABLE IF NOT EXISTS marketviceroy.bars
(
    venue       LowCardinality(String),   -- e.g. 'binance'
    symbol      LowCardinality(String),   -- e.g. 'BTC/USDT'
    ts          DateTime64(3, 'UTC'),     -- bar open time, millisecond precision, UTC
    timeframe   LowCardinality(String),   -- e.g. '1m', '1h', '1d'
    open        Float64,
    high        Float64,
    low         Float64,
    close       Float64,
    volume      Float64,
    source      LowCardinality(String),   -- provenance: which adapter served the row
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (venue, symbol, timeframe, ts);
