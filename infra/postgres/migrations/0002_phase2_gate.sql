-- Market Viceroy v4 — Phase 2 validation-gate results (PRD FR-V3).
--
-- Append-only history of gate runs. Each run records the verdict
-- (active/observe/failed), the data-source provenance, the per-stage metrics,
-- and the reasons. The latest run per strategy is the current gate status; the
-- Strategy Lab reads it. Keyed by strategy name (text) so a gate run does not
-- require a pre-existing `strategy` row.

CREATE TABLE IF NOT EXISTS strategy_gate_run (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name TEXT NOT NULL,
    family        TEXT,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    status        TEXT NOT NULL,                 -- active | observe | failed
    data_source   TEXT NOT NULL,                 -- provenance (real-feed vs synthetic)
    metrics       JSONB NOT NULL,                -- per-stage metrics
    reasons       JSONB NOT NULL,                -- decision reasons
    commit_sha    TEXT,                          -- reproducibility
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS strategy_gate_run_name_ts_idx
    ON strategy_gate_run (strategy_name, ts DESC);
CREATE INDEX IF NOT EXISTS strategy_gate_run_status_idx
    ON strategy_gate_run (status);
