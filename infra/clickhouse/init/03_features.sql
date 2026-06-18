-- Market Viceroy v4 — point-in-time feature store (Phase 3, PRD §6.2/FR-I2).
--
-- Long-format, as-of feature observations. `ts` is the feature's EFFECTIVE
-- (knowable) time — the filing date for fundamentals, the publish time for
-- sentiment, the bar time for technicals — NOT a future-dated period end. The
-- as-of join (mv.intelligence.asof) and the leakage check enforce that a
-- feature is only ever consumed at or after its `ts`, never before. `source`
-- records provenance (e.g. 'sec_edgar', 'fred', 'rss:reuters', 'technicals').

CREATE TABLE IF NOT EXISTS marketviceroy.features
(
    instrument   LowCardinality(String),
    feature_name LowCardinality(String),
    ts           DateTime64(3, 'UTC'),   -- effective / as-of time (point-in-time)
    value        Float64,
    source       LowCardinality(String), -- provenance of the producer
    ingested_at  DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (instrument, feature_name, ts);
