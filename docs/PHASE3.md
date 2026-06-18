# Phase 3 — Intelligence layer (point-in-time feature store): exit-gate evidence

Phase 3 exit gate (PRD FR-V6): **features are available point-in-time and the
CI leakage check is green.** Built the Core scope — feature store + as-of joins
+ leakage check + indicator library + SEC EDGAR fundamentals + rule-based
sentiment + the FRED no-train guardrail. Forecasting (GBM/LSTM/FinBERT) deferred.

## The linchpin — point-in-time feature store

```
producers (technicals / fundamentals / sentiment)  -> features table (effective ts)
   -> asof_join(decisions, features)  [backward only]  -> point-in-time panel
   -> assert_no_lookahead(panel)  [CI exit gate]
```

- **`features`** (ClickHouse, `infra/clickhouse/init/03_features.sql`): long-format
  `(instrument, feature_name, ts, value, source)`. `ts` is the **effective /
  knowable** time, never a future-dated period end.
- **`asof_join`** (`mv/intelligence/asof.py`): `pandas.merge_asof(direction="backward")`
  — each feature is its most-recent at-or-before value; retains `<name>__asof_ts`.
- **`assert_no_lookahead`** (`mv/intelligence/leakage.py`): the exit gate. It
  **fails on a leaky panel** (a forward-dated feature or a forward join), not
  just passes on a clean one — verified by `test_leakage.py`.

## Feature producers (all point-in-time)

| Producer | Module | As-of timestamp |
|---|---|---|
| Technicals | `indicators/core.py` (sma/ema/rsi/macd/bollinger/zscore/vol/drawdown/momentum) | bar time (causal: `rolling`/`ewm`/`shift`) |
| Fundamentals | `sources/sec_edgar.py` | **filing date** (not fiscal period end) |
| Sentiment | `sentiment.py` + `news.py` (local lexicon over RSS) | **publish time** |

## Non-negotiables honored

- **Point-in-time everything:** backward as-of joins; fundamentals by filing
  date; sentiment by publish time; indicators causal. The leakage check enforces
  `feature_ts <= decision_ts` and is proven to catch violations.
- **FRED no-train (FR-D11/BR-006):** `guardrail.assert_no_fred_in_training`
  rejects FRED-derived sources from any training set (FRED stays runtime-only).
  Built now even though forecasting is deferred.
- **Sentiment is local + date-gated:** a deterministic local lexicon — no
  remote/LLM call, no look-ahead.
- **Deterministic / no heavy deps:** pure scoring/joins/indicators unit-tested;
  no torch/sklearn/transformers. Network fetches (SEC EDGAR, RSS) are gated.

## Gates

- Suite + ≥85% coverage; `mypy --strict` clean; ruff clean. The intelligence
  modules (`asof`, `leakage`, `indicators`, `guardrail`, `sentiment`,
  `sec_edgar`, `news`) are unit-tested deterministically with no network.
- CI `integration` job: applies all ClickHouse `init/*.sql` (incl. `features`)
  and runs the **feature-store round-trip** (write → read → as-of → leakage
  check) alongside the journal / gate / CCXT integration tests.

## Offline ingestion (network, not per-push CI)

```bash
# SEC EDGAR (keyless; descriptive User-Agent required):
python -c "from mv.intelligence.sources.sec_edgar import fetch_company_facts, normalize_company_facts; ..."
# RSS news -> sentiment features:
python -c "from mv.intelligence.news import fetch_rss, parse_rss, score_news; ..."
```

Real ingestion is offline (yfinance/SEC/RSS are network/fragile) — the same
pattern as the Phase-2 grader.

## Deferred (out of Phase 3 scope)

Forecasting (GBM/LSTM) + FinBERT (torch); valuation/DCF beyond the SEC
fundamentals; HMM regime (Phase 5); wiring the 78 synthetic strategies to real
feeds (FR-S5, Phase 3→6); the React intelligence/feature UI (Phase 4/8); full
governor multi-domain routing for fundamentals/news ladders.
