-- Market Viceroy v4 — ClickHouse equity curves (Phase 1).
--
-- Per-strategy and portfolio equity over time, for the live paper loop and the
-- Strategy Lab later. `scope` distinguishes an individual strategy's notional
-- curve ('strategy:<name>') from the executed portfolio ('portfolio').
-- Equity is Float64 here as a time-series metric. Authoritative money/PnL
-- accounting lives in PostgreSQL/NautilusTrader as Decimal.

CREATE TABLE IF NOT EXISTS marketviceroy.equity_curves
(
    scope       LowCardinality(String),   -- 'portfolio' or 'strategy:ema_cross_12_26'
    ts          DateTime64(3, 'UTC'),
    equity      Float64,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (scope, ts);
