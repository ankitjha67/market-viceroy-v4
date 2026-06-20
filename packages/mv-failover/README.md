# mv-failover

Data-plane **Failover Governor** — the single entry point for all market /
fundamental / macro / news data, with a provider registry, per-vendor
rate-limit token buckets, circuit breakers, primary→fallback ladders,
cross-source reconciliation, and a staleness guard (PRD §4.1).

**Status: Built (Phase 1+).** The full governor (circuit breakers, ladders, reconciliation, staleness, health) with regional adapters — crypto (CCXT), US (Finnhub/Alpaca), FX (Frankfurter), and India equities (Dhan primary, then Upstox/Kotak/Zerodha/Angel One). Originally the Phase-0 smoke that
proves the data pipe. The full governor extends `alphakit-data`'s
`registry` / `cache` / `rate_limit` in **Phase 1** and is not built here.

## Phase-0 smoke (`mv.failover.smoke`)

Proves: one crypto instrument pulled via **CCXT** → **normalized** (Polars,
canonical bars schema) → written to **ClickHouse** → read back. This is the
Phase-0 exit gate (together with the alphakit suite green on 3.12).

```bash
docker compose up -d                 # ClickHouse + Postgres + Redis
cp .env.example .env                 # set passwords
uv run mv-smoke                      # fetch -> normalize -> write -> read-back
```

- `smoke/normalize.py` — **pure, deterministic** `normalize_ohlcv(...)`
  (no I/O, no clock, no network); fully unit-tested.
- `smoke/pipeline.py` — I/O glue (CCXT fetch, ClickHouse write + read-back).
  Marked `# pragma: no cover`; exercised by the CI integration job against a
  ClickHouse service container, and by `uv run mv-smoke` locally.
- `smoke/config.py` — `pydantic-settings` config read from `.env`
  (no secrets in code). The smoke uses **public** CCXT endpoints, so it
  needs no exchange API key.
