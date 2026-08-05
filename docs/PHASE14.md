# Phase 14: Open-source adoption (data sources + engines + end-to-end wiring)

Implements the adoptable capabilities identified in the open-source review of
Vibe-Trading (MIT), QuantDinger (Apache-2.0), MiroFish (AGPL, ideas only,
clean-room), crawl4ai (Apache-2.0, keyless-GDELT conclusion), and URS (MIT,
official-API pattern). The ToS-breaching candidates (twikit, twscrape, YARS
keyless scraping) were reviewed and DECLINED. Two PRs.

## PR 1: sources + engines

Seven source adapters (offline-gated fetch, pure tested normalization,
point-in-time stamps, absent-not-zero coverage discipline):

| Module | Source | Key |
|---|---|---|
| `mv-failover/adapters/funding_feed.py` | Binance USD-M perp funding + OI via CCXT; crowd-flow score | none |
| `mv-intelligence/sources/fear_greed.py` | alternative.me Fear & Greed | none |
| `mv-intelligence/sources/gdelt.py` | GDELT DOC 2.0 article search | none |
| `mv-intelligence/sources/reddit_api.py` | Reddit official OAuth reader + weighted lexicon sentiment | free client id |
| `mv-intelligence/sources/deribit.py` | Deribit public option book (OI, mark IV) | none |
| `mv-intelligence/sources/sec_13f.py` | 13F information-table parse + QoQ holdings diff | none |
| `mv-intelligence/sources/prediction_markets.py` | Polymarket implied probabilities (read-only) | none |

Three engines (pure, deterministic): `gex/engine.py` (real dealer-gamma
profile from a chain: BS gamma/delta, interpolated zero-gamma flip, +GEX
magnet, put/call mass centers, dealer delta balance; grade/minervini stay
caller-supplied), `options_payoff.py` (exact expiry breakevens/extrema/
scenario grid from the kink structure), `swarm/simulator.py` (MiroFish-
inspired, non-LLM, seeded crowd simulator: trend/reverter/herder/noise
species; news-shock, euphoria, liquidity-drought, calm presets).

## PR 2: end-to-end wiring

- The serve loop refreshes intel on the news cadence (Fear & Greed + funding
  keyless; Reddit social when `REDDIT_CLIENT_ID`/`SECRET` are set) and builds
  per-symbol features: `news_sentiment`, `sentiment` (mood blend), `flow`
  (funding crowd score), `regime` (signed efficiency). These thread through
  `run_paper_session(features=...)` into `AgentContext.features`, activating
  the previously neutral analysts (remediation item R8). End-to-end test: a
  strong sentiment feature makes the sentiment analyst journal bullish views
  while an uncovered analyst stays neutral.
- `GET /api/v1/intel` + the deck's Market intel panel (Fear & Greed, top
  funding rates in bp, social readings).
- India crypto tax (FR-X2) applied to realized round trips in the metrics
  panel: `tax_drag` + `after_tax_pnl` (30 percent on gains, no loss offset,
  + 1 percent TDS on exit transfer value). R6 partial: honest after-tax
  reporting; funding accrual on positions stays open until a perp instrument
  exists (the book is spot).
- `GET /metrics` in Prometheus exposition format (zero-dep, rendered from the
  same providers the deck reads) + an optional observability overlay
  (`docker-compose.observability.yml`: Prometheus + Grafana, loopback-only,
  password from env). QuantDinger adoption.
- `scripts/run_gex.py`: offline Deribit chain -> gamma profile -> Vol Desk
  levels, with Operator-supplied grade/minervini for the full grading pass.

## Deliberately not adopted

- twikit / twscrape: X scraping via account pools breaches X ToS. Declined.
- YARS: keyless Reddit scraping, ToS-gray, IP-ban-prone. Declined; the
  official API path shipped instead.
- MiroFish as a dependency: AGPL and LLM-cost-heavy; the swarm concept was
  adopted as a clean-room deterministic simulator instead.
- crawl4ai as a runtime dependency: heavy (browser stack); the news-breadth
  need is served keyless by GDELT. It remains available to the Operator as an
  offline research tool.
- QuantDinger full process separation: a rearchitecture of the serve loop,
  deferred (registered in ARCHITECTURE.md roadmap Wave 4).

## Gates

PR 1: 32 tests across ten files; ruff clean; mypy --strict clean (884 files).
PR 2: backend 40 targeted tests incl. the features end-to-end proof; frontend
tsc + eslint + 34 vitest + production build; repo-wide ruff format clean
(904 files); mypy --strict clean (887 files).
