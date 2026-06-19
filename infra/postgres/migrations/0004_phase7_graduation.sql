-- Market Viceroy v4 — Phase 7 graduation to live (PRD BR-005, US-010, FR-P6).
--
-- Append-only record of every graduation action. A strategy reaches live only
-- via an explicit Operator-authed entry here (sign-off per strategy); the latest
-- row per strategy is its current live status. The thresholds snapshot + the
-- recorded reasons make each promotion auditable; the live cap bounds capital.
-- A rejected attempt is recorded too (graduated = FALSE) for the audit trail.

CREATE TABLE IF NOT EXISTS graduation (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy      TEXT NOT NULL,
    graduated     BOOLEAN NOT NULL,              -- TRUE = promoted to live
    operator      TEXT NOT NULL,                 -- the signing Operator (FR-P6)
    live_cap_pct  NUMERIC NOT NULL DEFAULT 0,    -- capital cap as a fraction of equity
    thresholds    JSONB NOT NULL,                -- the bar snapshot at decision time
    reasons       JSONB NOT NULL,                -- blocking reasons (empty on success)
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS graduation_strategy_ts_idx ON graduation (strategy, ts DESC);
