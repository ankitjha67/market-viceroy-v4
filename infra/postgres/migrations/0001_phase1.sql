-- Market Viceroy v4 — Phase 1 relational schema (PRD §6.1 subset).
--
-- The crypto-paper MVP loop's relational store: instruments, sources,
-- strategies, signals, point-in-time snapshots, hash-chained decisions, the
-- order/fill/trade lifecycle, attribution (stub in Phase 1), risk events,
-- data-quality events, and the tamper-evident journal ledger.
--
-- Money/PnL/price/fee columns are NUMERIC (Decimal), never float
-- (engineering standards). Timestamps are TIMESTAMPTZ (UTC). UUID PKs via
-- pgcrypto's gen_random_uuid() (extension enabled in 01_init.sql). Tables
-- not needed before their owning phase are intentionally omitted.

-- --- Reference / registry -------------------------------------------------

CREATE TABLE IF NOT EXISTS source (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,          -- e.g. 'ccxt:binance'
    domain        TEXT NOT NULL,                 -- e.g. 'crypto.prices'
    priority      INTEGER NOT NULL,              -- ladder rank (0 = primary)
    rate_cap      TEXT,                          -- published cap, free-text
    licensing_tag TEXT NOT NULL DEFAULT 'internal-only',
    health_score  DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS instrument (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol      TEXT NOT NULL,                   -- e.g. 'BTC/USDT'
    asset_class TEXT NOT NULL,                   -- 'crypto', ...
    venue       TEXT NOT NULL,                   -- 'binance', ...
    base        TEXT,
    quote       TEXT,
    tick_size   NUMERIC,
    lot_size    NUMERIC,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, venue)
);

CREATE TABLE IF NOT EXISTS strategy (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,            -- e.g. 'ema_cross_12_26'
    family      TEXT NOT NULL,                   -- 'trend', 'meanrev', ...
    gate_status TEXT NOT NULL DEFAULT 'observe', -- active | observe | failed
    data_source TEXT,                            -- provenance (real-feed/synthetic)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --- Point-in-time inputs + signals ---------------------------------------

CREATE TABLE IF NOT EXISTS feature_snapshot (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts            TIMESTAMPTZ NOT NULL,          -- point-in-time the agents saw
    instrument_id UUID NOT NULL REFERENCES instrument (id),
    payload       JSONB NOT NULL                 -- everything the decision saw
);
CREATE INDEX IF NOT EXISTS feature_snapshot_instrument_ts_idx
    ON feature_snapshot (instrument_id, ts);

CREATE TABLE IF NOT EXISTS signal (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id   UUID NOT NULL REFERENCES strategy (id),
    instrument_id UUID NOT NULL REFERENCES instrument (id),
    ts            TIMESTAMPTZ NOT NULL,
    weight        NUMERIC NOT NULL,              -- StrategyProtocol output
    snapshot_id   UUID REFERENCES feature_snapshot (id)
);
CREATE INDEX IF NOT EXISTS signal_strategy_ts_idx ON signal (strategy_id, ts);

-- --- Decisions (hash-chained) + agent records -----------------------------

CREATE TABLE IF NOT EXISTS decision (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID NOT NULL REFERENCES instrument (id),
    ts            TIMESTAMPTZ NOT NULL,
    action        TEXT NOT NULL,                 -- BUY | SELL | HOLD
    conviction    DOUBLE PRECISION NOT NULL,
    target_size   NUMERIC NOT NULL,
    snapshot_id   UUID REFERENCES feature_snapshot (id),
    prev_hash     TEXT,                          -- hash chain (tamper-evident)
    hash          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS decision_instrument_ts_idx ON decision (instrument_id, ts);

CREATE TABLE IF NOT EXISTS agent_record (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decision (id) ON DELETE CASCADE,
    agent       TEXT NOT NULL,
    payload     JSONB NOT NULL,
    confidence  DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS agent_record_decision_idx ON agent_record (decision_id);

-- --- Order / fill / trade lifecycle ---------------------------------------
-- "order" is a reserved word in SQL; the table is named order_ to avoid quoting.

CREATE TABLE IF NOT EXISTS order_ (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id    UUID NOT NULL REFERENCES decision (id),
    type           TEXT NOT NULL,                -- market | limit | post_only
    side           TEXT NOT NULL,                -- BUY | SELL
    qty            NUMERIC NOT NULL,
    intended_price NUMERIC,
    status         TEXT NOT NULL,                -- filled | partial | rejected | cancelled
    ts             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS order_decision_idx ON order_ (decision_id);

CREATE TABLE IF NOT EXISTS fill (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id     UUID NOT NULL REFERENCES order_ (id) ON DELETE CASCADE,
    price        NUMERIC NOT NULL,
    qty          NUMERIC NOT NULL,
    slippage_bps DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    fees         NUMERIC NOT NULL DEFAULT 0,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fill_order_idx ON fill (order_id);

CREATE TABLE IF NOT EXISTS trade (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID NOT NULL REFERENCES instrument (id),
    entry_fill    UUID REFERENCES fill (id),
    exit_fill     UUID REFERENCES fill (id),
    gross_pnl     NUMERIC,
    net_pnl       NUMERIC,
    opened_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at     TIMESTAMPTZ
);

-- Attribution: full signal/timing/sizing/slippage/fees/regime decomposition is
-- Phase 5; the table exists now so the Phase-1 stub can record net PnL.
CREATE TABLE IF NOT EXISTS attribution (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL REFERENCES trade (id) ON DELETE CASCADE,
    signal   NUMERIC,
    timing   NUMERIC,
    sizing   NUMERIC,
    slippage NUMERIC,
    fees     NUMERIC,
    regime   NUMERIC
);

-- --- Safety / data-quality events -----------------------------------------

CREATE TABLE IF NOT EXISTS risk_event (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
    type           TEXT NOT NULL,                -- veto | kill_switch | halt | resume
    breached_limit TEXT,
    action         TEXT NOT NULL,
    detail         JSONB
);
CREATE INDEX IF NOT EXISTS risk_event_ts_idx ON risk_event (ts);

CREATE TABLE IF NOT EXISTS data_quality_event (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    instrument_id UUID REFERENCES instrument (id),
    sources       JSONB NOT NULL,               -- the sources compared
    discrepancy   DOUBLE PRECISION,
    action        TEXT NOT NULL                 -- e.g. 'halt'
);
CREATE INDEX IF NOT EXISTS data_quality_event_ts_idx ON data_quality_event (ts);

-- --- Tamper-evident journal ledger (hash-chained) -------------------------
-- Append-only. Every step (decision, risk event, failover, fill, ...) is one
-- entry; each links to the previous by hash. Populated in Step 5 (mv-journal).

CREATE TABLE IF NOT EXISTS journal_entry (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq        BIGSERIAL NOT NULL UNIQUE,        -- monotonic append order
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind       TEXT NOT NULL,                    -- 'decision' | 'risk_event' | 'failover' | ...
    payload    JSONB NOT NULL,
    prev_hash  TEXT,
    hash       TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS journal_entry_kind_idx ON journal_entry (kind);
