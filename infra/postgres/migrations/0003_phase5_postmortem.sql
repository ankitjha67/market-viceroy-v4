-- Market Viceroy v4 — Phase 5 post-mortem & governed meta-learning (PRD FR-P2/P4/P5).
--
-- `mistake`  — the taxonomy: one row per classified losing trade, with the
--   category and the cost it carried (frequency + cumulative cost trend).
-- `improvement` — the learning ledger: every adjustment, which mistake it
--   targets, what changed, the before/after held-out metric, and whether the
--   Operator adopted it. Append-only.
-- `weight_proposal` — governed meta-learning output: a proposed strategy-weight
--   set with its held-out before/after metric and adoptable flag. PROPOSE-ONLY —
--   nothing here changes the running loop until the Operator adopts it.

CREATE TABLE IF NOT EXISTS mistake (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id   TEXT NOT NULL,
    category   TEXT NOT NULL,                  -- false_signal | late_entry | ...
    cost       NUMERIC NOT NULL,               -- positive magnitude of the loss cause
    detail     TEXT,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mistake_category_ts_idx ON mistake (category, ts DESC);

CREATE TABLE IF NOT EXISTS improvement (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mistake_category TEXT,                     -- the mistake this targets (nullable)
    change_kind    TEXT NOT NULL,              -- strategy_weight | param_prior | risk_limit
    change_desc    TEXT NOT NULL,
    before_metric  DOUBLE PRECISION,           -- held-out metric before
    after_metric   DOUBLE PRECISION,           -- held-out metric after
    adopted        BOOLEAN NOT NULL DEFAULT FALSE,
    ts             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS improvement_ts_idx ON improvement (ts DESC);

CREATE TABLE IF NOT EXISTS weight_proposal (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    weights        JSONB NOT NULL,             -- proposed per-strategy weights
    before_metric  DOUBLE PRECISION,           -- held-out metric of current weights
    after_metric   DOUBLE PRECISION,           -- held-out metric of proposed weights
    adoptable      BOOLEAN NOT NULL,           -- passed held-out validation
    adopted        BOOLEAN NOT NULL DEFAULT FALSE,  -- Operator decision (propose-only)
    ts             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS weight_proposal_ts_idx ON weight_proposal (ts DESC);
