# Market Viceroy v4: Reference Architecture

Autonomous multi-agent trading platform. Agents research, debate, and decide Buy/Sell/Hold; execution stays inside inviolable risk rails; every decision is journaled and attributable; strategies reach live capital only through explicit, Operator-signed gates.

| Document control | Value |
|---|---|
| Owner | Ankit Jha (Operator) |
| Version | 1.0 (architecture baseline, corrected to implementation) |
| Date | 14 July 2026 |
| Scope today | Crypto spot, paper trading, INR denominated, continuous loop |
| Expansion scope | US and India equities, FX, derivatives; India live trading after staged gates |
| Status | Living reference. Update per release (see Section 39) |
| Supersedes | The externally authored "Autonomous Indian Trading Platform" reference PDF (14 Jul 2026), whose structure this document adapts and whose claims are corrected against the codebase |

## 0. How to use this reference

This is the system's architectural source of truth. It records component boundaries, decision ownership, data contracts, strategy and validation standards, promotion gates, operational controls, and the forward roadmap. Code, phase records (`docs/PHASE0.md` through `docs/PHASE13.md`), and the runbook (`docs/RUNBOOK.md`) link back to decisions recorded here.

Unlike an aspiration document, every component here carries an implementation status verified against the code:

| Tag | Meaning |
|---|---|
| IMPLEMENTED | Wired into the running system and tested |
| PARTIAL | Working, with a named limitation |
| DORMANT | Built and tested, but not wired into the live path (module cited) |
| PLANNED | Design intent only; no code yet |

Sections 36 and 37 (remediation register and roadmap) list every DORMANT/PLANNED item with its activation wave.

### 0.1 Decision hierarchy

Authority is layered. A lower level can never be overridden by a higher one.

| Level | Authority | Where it lives | Status |
|---|---|---|---|
| 0. Safety | Kill switch (Operator-only reset), BR-005 live-order block, data-quality halts | `packages/mv-risk/mv/risk/kill_switch.py`, `live_guard.py`; reconcile halt in `packages/mv-failover/mv/failover/reconcile.py` | IMPLEMENTED (reconcile halt DORMANT in the live loop, Section 10.3) |
| 1. Risk | Position/exposure/loss limits; Operator-set profiles | `packages/mv-risk/mv/risk/limits.py`, `engine.py` | IMPLEMENTED (two defects, Section 25.3) |
| 2. Strategy | Validation gate, graduation, degraduation | `packages/alphakit-bench/alphakit/bench/validation/`, `packages/mv-risk/mv/risk/graduation.py` | IMPLEMENTED |
| 3. Agent | Research, debate, ranking, proposals; advisory until risk approves | `packages/mv-agents/` | IMPLEMENTED (deterministic-first) |
| 4. Presentation | Command Deck narratives; never a market-access dependency | `packages/mv-ui/` | IMPLEMENTED |

### 0.2 Companion registers

| Register | Realized as |
|---|---|
| Decision/event log | Hash-chained journal (`packages/mv-journal/`); tamper-evident, replayable |
| Strategy registry | Gate results storage + per-strategy `benchmark_results.json` provenance tags |
| Risk-policy catalogue | `RiskLimits` profiles (aggressive/moderate/conservative) + `GraduationThresholds` |
| Release evidence | `docs/PHASE*.md` (one per shipped phase) + CI history |
| ADR register | Section 35 of this document |
| Incident log | PLANNED (journal carries risk events; no separate incident record yet) |

## PART I: PURPOSE AND ARCHITECTURE

## 1. Mission, scope, and non-goals

Mission: convert heterogeneous market evidence into controlled, explainable, auditable trade decisions, prove them under cost-aware, point-in-time paper trading, and let only demonstrated edges graduate to live capital.

North Star (PRD): the count of strategies whose live risk-adjusted return stays within tolerance of their paper projection. The platform measures whether its own projections are honest; it does not flatter them.

### 1.1 Scope

| Domain | Today (implemented) | Expansion |
|---|---|---|
| Markets | Crypto spot via public CCXT (Binance, Kraken, Coinbase ladder), 11-pair USDT watchlist, INR denominated | US equities (Finnhub, Alpaca), India equities (Dhan primary; Upstox, Kotak, Zerodha, Angel One fallbacks), FX; derivatives after data + risk gates |
| Horizons | 1m to 1d bars, low-frequency systematic | Unchanged; HFT excluded permanently |
| Lifecycle | Research, validation gate, continuous paper loop, post-mortem, governed learning, graduation machinery | Shadow mode, limited live (Operator-gated) |
| Users | Single Operator (owner, approver, incident commander) | Unchanged |

### 1.2 Explicit non-goals

| Non-goal | Rationale |
|---|---|
| Unbounded self-learning | No model rewrites or promotes itself. Meta-learning and the strategy inventor are propose-only; the Operator adopts |
| LLM market authority | Language models never compute final size, approve risk, or submit orders. The LLM seam is advisory with deterministic fallback (FR-A9) |
| Automated real-money orders | The platform never places a live order without graduation plus Operator sign-off (BR-005). Real-money go-live is the Operator's manual action |
| Guaranteed returns | The architecture optimizes evidence and control. The honest result may be "no edge here" |
| HFT / co-location | Bar-driven, seconds-level cadence by design |
| Public data product | Internal use only; keeps freemium source ToS intact |

### 1.3 Success criteria

- Every decision is reconstructable from the journal plus recorded market data (replay).
- Paper and live share the same strategy, risk, and execution code; only the venue adapter differs (NautilusTrader bridge).
- A failed dependency produces a safe halt or failover, never a silent wrong number.
- Performance claims are net of the versioned fee/cost model, on point-in-time data, through the validation gate.

## 2. Architecture principles

| Principle | Implementation |
|---|---|
| Determinism at the boundary | All market-facing decisions are typed and deterministic; agent output is evidence, not authority |
| Point-in-time truth | As-of joins only; features stamped by knowable time; CI leakage check; FRED never in any training set |
| Inviolable rails | Kill switch, loss limits, exposure caps are infrastructure; only the Operator changes them |
| Validated, not proven | A strategy is `active` only after the full gate on real-feed data; synthetic evidence can never grade active |
| No naive PnL-chasing | Strategy weighting is market-structure driven (regime), never recent-PnL driven; adoption is human-gated |
| Decimal money | All money/PnL/fills use `Decimal`; float only inside vectorized backtest math |
| Version everything | Pinned `uv.lock`; commit SHA in backtest meta; journal reconstructs decisions |
| Fail closed on data | Circuit breakers, staleness guards, ladder failover; an exhausted ladder halts the domain |

## 3. End-to-end logical architecture

```
1. ACQUIRE          2. VALIDATE         3. ANALYZE           4. DECIDE            5. CONTROL           6. EXECUTE
Failover governor   Staleness guard     Strategy signals     Ensemble vote or     Risk engine veto     NautilusTrader
(CCXT ladder,       Circuit breakers    Regime detection     LangGraph agents     (limits, breakers,   paper venue
FX rate,            Empty-frame         News sentiment       (analysts, debate,   kill switch)         Fills, fees
news RSS)           rejection           (display)            risk, PM B/S/H)                           Journal append
                                                                                                             |
                    8. LEARN            7. ACCOUNT                                                           v
                    Post-mortem         FIFO round trips,    <------------------------------------  Hash-chained journal
                    attribution,        mark-to-market,                                              (decisions, fills,
                    mistakes, ledger,   equity curve,                                                regime, risk events)
                    inventor            metrics, blotter
```

The deck (FastAPI + Next.js) reads every stage through injected providers; the UI is an observer, never a dependency of the trading path.

### 3.1 Package map (uv workspace)

| Package | Responsibility | Status |
|---|---|---|
| `alphakit-core` | Protocols (Strategy/BacktestEngine/DataFeed/ExecutionEngine), instruments, metrics, portfolio math | IMPLEMENTED |
| `alphakit-strategies-*` (9 pkgs) | 109 strategy modules across 9 families | IMPLEMENTED (29 real-feed, 80 synthetic; Section 11) |
| `alphakit-bridges` | vectorbt, backtrader, lean, NautilusTrader bridges + cost model | IMPLEMENTED (cost model partially wired; Section 18) |
| `alphakit-bench` | Validation gate, benchmark runner, strategy inventor | IMPLEMENTED |
| `alphakit-data` | Backtest-plane feeds (yfinance, FRED, CFTC, EIA, synthetic options) | IMPLEMENTED (backtest only; never imported by `mv-*` runtime) |
| `mv-failover` | Live-plane governor: registry, ladders, breakers, staleness, reconcile, health + broker/vendor adapters | IMPLEMENTED (reconcile DORMANT in loop) |
| `mv-intelligence` | Feature store, as-of, leakage, indicators, SEC EDGAR, sentiment/news, forecasting, arbitrage, GEX | IMPLEMENTED as modules; mostly DORMANT in live decisions (Section 13) |
| `mv-agents` | LangGraph graph, agent roster, schemas, LLM seam, baseline ensemble + regime | IMPLEMENTED |
| `mv-journal` | Hash-chained journal + Postgres store | IMPLEMENTED (Postgres store DORMANT in serve; Section 31.2) |
| `mv-postmortem` | Attribution, mistakes, counterfactual replay, improvement ledger, governed meta-learning | IMPLEMENTED (attribution/replay providers DORMANT in serve) |
| `mv-risk` | Risk engine, limits, kill switch, graduation, compliance, degraduation, live guard | IMPLEMENTED |
| `mv-api` | FastAPI, WebSocket, paper loop, serve CLI, snapshot/metrics/blotter/chart/news/inventor views, telemetry | IMPLEMENTED |
| `mv-ui` | Next.js Command Deck (10 screens, dark terminal design system) | IMPLEMENTED |

## 4. Deployment topology

| Zone | Contents | Status |
|---|---|---|
| Operator workstation | Windows 11, uv-managed Python 3.12, Node; `Start-CommandDeck.ps1` one-shot launcher; zero-infra paper mode (in-process kill switch when Redis is absent) | IMPLEMENTED |
| Data plane (optional) | Docker Compose: ClickHouse (bars/features), Postgres (relational, journal store), Redis (kill-switch flag, hot state); all loopback-bound; passwords required from `.env` | IMPLEMENTED (optional; paper runs without it) |
| API | FastAPI on 127.0.0.1:8000; mutating endpoints Operator-token authed; non-loopback binds warn loudly | IMPLEMENTED |
| UI | Next.js dev server on 127.0.0.1:3000; SWR polling + authed WebSocket | IMPLEMENTED |
| CI | GitHub Actions: ruff + mypy strict; pytest + coverage gate (>= 85 percent); ClickHouse + Postgres integration; frontend lint/types/test/build | IMPLEMENTED |

Environment progression (research / backtest / paper / shadow / limited live / scaled): Section 28.

## 5. Runtime sequences

| Sequence | Steps | Status |
|---|---|---|
| Serve tick (every interval) | Per symbol: governor fetch (timed for telemetry), merge into the growing window, INR scale via FX rate, run the paper session (signals, regime, ensemble or agents, risk gate, fills), swap the aggregated view (portfolio, positions, chart, metrics, blotter) | IMPLEMENTED |
| News refresh | Every few ticks: fetch RSS feeds (size-capped), score with the local lexicon, aggregate per-instrument sentiment for the deck | IMPLEMENTED (display only) |
| Inventor cycle | Background, roughly every 30 minutes: full search (grid + genetic + LLM-fallback), grade each candidate through the validation gate over accumulated bars, queue survivors for one-click adoption | IMPLEMENTED |
| Kill behavior | Tripped switch rejects all orders in-process; watch and inventor loops pause; only the Operator resets | IMPLEMENTED |
| Failure semantics | One bad symbol skips its tick; one bad tick never kills the server; a failing source trips its breaker and the ladder fails over | IMPLEMENTED |
| Pre-open / session calendar | Not applicable to 24/7 crypto; required before equities go live | PLANNED (Wave 3) |

## PART II: DATA AND AGENTS

## 6. Data-source architecture

Two data planes exist and must not be confused:

1. Live plane (`mv-failover`): the failover governor the trading loop consumes.
2. Backtest plane (`alphakit-data`): feeds the validation gate and research scripts; never imported by runtime `mv-*` packages.

### 6.1 Live-plane governor domains

| Domain | Ladder (priority order) | Adapter reality | Status |
|---|---|---|---|
| `crypto.prices` | ccxt:binance, ccxt:kraken, ccxt:coinbase | Public OHLCV, keyless | IMPLEMENTED (the only domain the loop trades) |
| `equity.prices` (US) | finnhub, alpaca | Real HTTP adapters, env keys | DORMANT (registered, tested, not queried by the loop) |
| `equity.prices` (India) | dhan, upstox, kotak, zerodha, angelone | Real HTTP adapters, env keys; Zerodha internal-use only | DORMANT (same) |
| `fx.rates` | frankfurter (ECB) | Keyless | PARTIAL (used for the USD to INR display rate only) |

All adapters share the pattern: network call isolated and offline-gated, pure normalization unit-tested on fixtures, keys read from env at call time.

### 6.2 Backtest-plane feeds

| Feed | Content | Status |
|---|---|---|
| yfinance | Equities, adjusted | IMPLEMENTED (research/gate only) |
| yfinance-futures | Continuous front-month commodity futures | IMPLEMENTED (no multi-expiry chain) |
| FRED | Macro rates. Runtime input only; never in any training set (BR-006, enforced guardrail) | IMPLEMENTED |
| CFTC COT | Weekly positioning | IMPLEMENTED |
| EIA | Energy | IMPLEMENTED |
| synthetic-options | Black-Scholes chains, flat vol, full greeks | IMPLEMENTED (synthetic: can never grade a strategy active) |
| polygon options | Real vendor chains | PLANNED (stub raises; vendor decision open) |

### 6.3 Excluded sources

Hard-excluded from the registry by policy: IEX Cloud, legacy Polygon endpoints, OECD.Stat, ECB SDW, CoinCap v2, CryptoCompare free, investpy, yfinance-as-primary-live. Verified absent from the runtime registry.

## 7. Point-in-time data model

| Contract | Implementation | Status |
|---|---|---|
| As-of joins | `merge_asof(direction="backward")` in `mv-intelligence/asof.py` | IMPLEMENTED, DORMANT in live decisions |
| Leakage check | `assert_no_lookahead` panel checker; CI-tested against a deliberately leaky fixture | IMPLEMENTED |
| Feature store | ClickHouse-backed, stamped by knowable time (filing date for fundamentals, publish time for news) | IMPLEMENTED, DORMANT in live decisions |
| FRED no-train guardrail | `guard_training_sources` enforced inside every forecaster fit | IMPLEMENTED |
| Bitemporal revisions | Effective vs observed time on every entity | PARTIAL (feature rows carry ingest time; full bitemporal reference data PLANNED with the instrument master) |
| Instrument master / security reference | Symbol history, ISIN, lot/tick, corporate actions | PLANNED (Wave 3; prerequisite for India live, whose brokers key on numeric tokens) |

## 8. Agent catalogue

The decision layer has two interchangeable engines behind one seam: the deterministic baseline ensemble (default) and the LangGraph multi-agent pipeline (`--agents`).

| Agent | Responsibility | Boundary | Status |
|---|---|---|---|
| Technical analysts (the 9-strategy roster) | Per-strategy signals over the rolling window | Signals only; no sizing authority | IMPLEMENTED |
| Regime detector | Kaufman efficiency ratio to trend/meanrev family weights | Market-structure input, never PnL | IMPLEMENTED |
| News / Macro / Flow / Fundamentals / Valuation / Sentiment analysts | Feature-based stances | Degrade to neutral, low confidence when their feature is absent | PARTIAL: implemented, but the live loop passes signals only, so these six run neutral (Section 13) |
| Bull / Bear | Structured debate over analyst views | Claims must cite views | IMPLEMENTED |
| Research Manager | Weighs the debate into a verdict | Cannot size or execute | IMPLEMENTED |
| Portfolio Manager | Buy/Sell/Hold + target size proposal | Bounded by the risk engine | IMPLEMENTED |
| Risk Manager | The inviolable veto (the risk engine itself as a node) | Cannot be overridden by any agent | IMPLEMENTED |
| LLM seam | Per-agent routing (Ollama local, Anthropic cloud), cost/latency journaled | Offline by default; any failure falls back to the deterministic reasoner (FR-A9); never on the risk path | IMPLEMENTED (deterministic-first; no client wired in serve) |

Every agent output is a typed, journaled record (stance, score, rationale, snapshot id). The Agent Room screen renders the full transcript per decision.

## 9. Orchestration and permissions

| Role | Allowed | Prohibited |
|---|---|---|
| Research/analyst agents | Read features and signals; write journaled views | Broker secrets, order submission, risk changes |
| PM | Propose direction and size | Exceed risk caps, bypass the veto |
| Risk engine | Veto/clamp any order | Being disabled by any agent or autonomy setting |
| Meta-learning / inventor | Write proposals to the ledger / candidate queue | Auto-apply, auto-adopt, touch limits |
| Operator | Kill/reset, adopt candidates, graduate strategies, change limits (authed, journaled) | Bypass the journal |

## PART III: STRATEGY PLATFORM

## 10. Strategy platform philosophy

A strategy is a versioned decision specification, not an indicator. The unit of deployment is a `StrategyProtocol` implementation: `name`, `family`, `asset_classes`, `rebalance_frequency`, `generate_signals(prices) -> weights`, plus committed benchmark evidence with a data-source provenance tag.

Two orthogonal notions of "real" govern the platform, and the distinction is enforced in code:

1. Backtest provenance: `is_real_feed(data_source)` in the gate; synthetic evidence caps a strategy at `observe`.
2. Live-feed availability: `domain_for_strategy(asset_class, region)` resolves a governor ladder only for crypto/global, equity/us, equity/india, fx/global.

Known tension (by design, tracked): the 29 real-backtested strategies are macro/rates/commodity families with no live governor feed; the 9 live-traded crypto strategies carry synthetic committed backtests, so they run `observe` while accumulating real history. Closing this loop (deep real crypto history through the gate) is roadmap Wave 1.

## 11. Strategy library taxonomy

109 modules across 9 families. Counts verified from committed provenance tags: 29 real-feed, 80 synthetic.

| Family | Count | Real-feed | Representative members |
|---|---|---|---|
| trend | 15 | 0 | SMA/EMA/Donchian crosses, TSMOM 12-1, turtle, supertrend, ichimoku, dual momentum, 52-week high, residual momentum |
| meanrev | 15 | 0 | Bollinger, RSI(2/14), z-score, OU process, gap fill, overnight reversal, pairs (distance, Engle-Granger, Johansen, Kalman), statarb PCA |
| options | 15 | 0 | Covered call/BXM, CSP, iron condor, strangle, calendar, delta-hedged straddle, gamma scalping, VRP, skew, VIX term structure |
| rates | 13 | 11 | Bond TSMOM, carry/rolldown, curve steepener/flattener/butterfly, real-yield momentum, yield-curve PCA |
| macro | 11 | 11 | GTAA momentum, risk-parity ERC, min-variance, max-diversification, permanent portfolio, regime rotations |
| carry | 10 | 0 | FX carry G10/EM, dividend yield, vol carry, cross-asset carry, crypto funding carry |
| commodity | 10 | 7 | Curve carry, TSMOM, COT positioning, crack/crush spreads, seasonality |
| value | 10 | 0 | PE/PB/EV-EBITDA, FCF yield, magic formula, Piotroski F, Altman Z, country CAPE |
| volatility | 10 | 0 | Vol targeting, VRP harvest, VIX term structure, leveraged-ETF decay, option-proxy sleeves |

## 12. Live roster and strategy contract

The paper loop trades 9 crypto-capable single-symbol strategies concurrently on every watchlist pair:

- Trend (5): EMA 12/26 (long-only), SMA 10/30, SMA 50/200, Donchian 20, Donchian 55
- Mean reversion (4): RSI-2, RSI-14, Bollinger reversion, Z-score reversion

Signals blend through a governed ensemble: equal weight by default, regime-adaptive family weighting by market structure (efficiency ratio), with a floor keeping both families alive. Weights are never PnL-derived.

The remaining catalog (cross-sectional, multi-leg, macro panels) needs instruments or panels crypto paper does not have; those strategies stay observe-only in the Strategy Lab until Wave 3 breadth.

## 13. Intelligence layer wiring status

| Module | Purpose | Live wiring |
|---|---|---|
| News + sentiment | RSS to per-instrument lexicon scores | IMPLEMENTED, display-only (deck panel); agent feature feed is Wave 2 |
| Feature store / as-of / leakage | Point-in-time features | DORMANT in live decisions (tested; nothing populates `AgentContext.features`) |
| Indicators library | Shared technical indicators | DORMANT (live strategies compute their own) |
| SEC EDGAR | Point-in-time fundamentals by filing date | DORMANT (research only) |
| Forecasting (GBM; LSTM/FinBERT extras) | Point-in-time forecasters, FRED-guarded | DORMANT (not in the decision path) |
| Arbitrage (cross-exchange, triangular, funding) | After-cost, R/A/G-flagged opportunity detection | DORMANT in serve (offline script + endpoint provider unwired) |
| GEX / Vol Desk | Dealer-gamma setup grading, exits, regime gates | IMPLEMENTED logic, mock-fed only (real options GEX data is a paid-vendor decision) |
| MLflow tracking | Experiment logging (opt-in store) | DORMANT (not called by any runtime loop) |

The single highest-leverage intelligence upgrade is passing features into `AgentContext` (Wave 2): it activates six analysts at once with code that already exists.

## 14. Strategy lifecycle

```
idea -> synthetic backtest -> OBSERVE
                                 |         (real-feed evidence through the full gate)
                                 v
                              ACTIVE -> (sustained paper record + compliance + Operator signature) -> GRADUATED
                                 |                                                                        |
                              FAILED                                          (projection dishonesty or breach) -> DEGRADUATED (back to paper)
```

| Transition | Gate | Status |
|---|---|---|
| observe -> active | Full validation gate on real-feed data (Section 17) | IMPLEMENTED |
| active -> graduated | Conservative thresholds: >= 3 months paper, OOS Sharpe >= 1.0, max DD <= 10 percent, >= 100 trades, live cap <= 1 percent of equity; plus the compliance checklist all-clear; Operator-authed, journaled endpoint | IMPLEMENTED (machinery; live path disabled by default) |
| graduated -> live orders | `live_guard` clamps to the cap and blocks ungraduated keys (BR-005) | IMPLEMENTED, intentionally unwired in serve (paper-first) |
| live -> degraduated | Projection honesty breach (abs(live minus paper Sharpe) > 0.5), drawdown breach, or any limit breach; only ever de-risks | IMPLEMENTED |

## 15. Strategy inventor (autonomous research)

| Stage | Mechanism | Status |
|---|---|---|
| Generate | Parameter grids (6 templates), genetic mutation/crossover with interpolation between grid points, LLM proposer bounded to known templates and in-range params with deterministic fallback | IMPLEMENTED |
| Evaluate | Every candidate through the full validation gate over accumulated real INR bars | IMPLEMENTED |
| Propose | Survivors only, into a propose-only queue | IMPLEMENTED |
| Adopt | Operator one-click (token-authed); adopted strategy joins the live roster next tick | IMPLEMENTED |

Honest behavior: on short crypto history the gate rejects nearly everything; "N tested, 0 survived" is the system working. The LLM proposer cannot invent mechanics outside the bounded template space.

## 16. Capital allocation

| Layer | Today | Target (roadmap) |
|---|---|---|
| Across instruments | Equal split of starting capital per watchlist symbol | Risk-budgeted allocation (covariance-aware); Wave 2 |
| Across strategies | Governed ensemble vote (equal or regime-weighted) into one blended signal per symbol | Unchanged in principle; optional risk-parity weighting |
| Position sizing | Conviction fraction x max_position_pct x equity slice, then risk-gated | Volatility-targeted, stop-distance-based sizing; Wave 2 |
| Portfolio optimizer | None in the live path (ERC/min-var/max-div solvers exist inside three macro backtest strategies only) | Lift the existing covariance/ERC primitives into a book-level allocator; Wave 2 |

## PART IV: BACKTESTING AND PAPER TRADING

## 17. Validation gate (the honest filter)

`ValidationGate.evaluate(slug, strategy, prices, data_source)` runs, in order: cost-aware backtest, walk-forward, regime slicing, deflated Sharpe (multiple-testing aware), block-bootstrap Monte Carlo, then a pure decision:

| Rule | Effect |
|---|---|
| Synthetic data source | Can never grade ACTIVE (hard cap at OBSERVE) |
| Walk-forward consistency below floor | FAILED |
| Worst-regime Sharpe below floor | FAILED |
| Deflated Sharpe not significant | FAILED |
| Monte Carlo lower bound not positive | FAILED |
| Gross-positive alone | Never sufficient |

Status: IMPLEMENTED (CI-tested stages; offline runner `scripts/run_gate.py`; inventor reuses the same gate). Purged/embargoed CV and parameter-stability surfaces: PLANNED (Wave 4 hardening).

## 18. Cost model

| Component | Model | Status |
|---|---|---|
| Fees | Per-venue maker/taker bps (Binance 10/10, Kraken 16/26, Coinbase 40/60), applied in-venue on every paper fill | IMPLEMENTED |
| Slippage/impact | Depth-aware: half-spread + concave impact by order-notional vs depth | DORMANT in fills (wired only into arbitrage detection); realized fill-vs-intended slippage is journaled per fill. Wiring into fills + a liquidity size cap is Wave 1 |
| Live recalibration (FR-X4) | Realized-slippage recalibration + calibration store write-back | IMPLEMENTED (write-back consumed by the cost model seam) |
| Funding / borrow | Perp funding accrual on held positions | PLANNED (Wave 1; funding exists only as an arb signal today) |
| India crypto tax | 30 percent on gains + 1 percent TDS model | DORMANT (module tested, not applied to reported PnL); Wave 1 |
| Backtest costs | Flat commission bps + optional slippage bps via the vectorbt bridge | IMPLEMENTED (gate default: commission 5 bps) |

## 19. Paper trading architecture

Paper trading exercises the same strategy, risk, journal, and accounting code intended for live; only the venue is simulated (NautilusTrader `AccountType.CASH` venue with the maker/taker fee model).

| Mode | Mechanism | Status |
|---|---|---|
| Continuous real-time | `mv-serve --watch`: growing per-symbol windows anchored at launch, re-run per tick, one shared journal | IMPLEMENTED |
| One-shot session | `mv-paper` over a fetched window | IMPLEMENTED |
| Historical replay | Recorded frames through the same session (used by counterfactual replay) | PARTIAL (no first-class replay CLI) |
| Shadow (broker-state, no submit) | Compare intended vs feasible orders against a live broker session | PLANNED (Wave 4; prerequisite for India live) |
| Canary (champion/challenger) | New version beside approved version | PLANNED |

## 20. Paper fill realism

| Case | Today | Target |
|---|---|---|
| Market order | Full instantaneous fill at bar price, fees applied | Depth-capped size, modeled slippage applied to fill price (Wave 1) |
| Limit / stop orders | Not used by the loop | Order-policy layer with limit-first execution (Wave 3) |
| Partial fills | Never simulated | FillModel-based partials (Wave 3) |
| Rejects / cancels | No handlers | Reject/cancel handlers + journaled reasons (Wave 3) |
| Latency | None modeled | Measured-distribution latency injection (Wave 4) |

This is the platform's largest realism gap and is called out honestly wherever results are displayed: paper fills are currently systematically kinder than a real venue.

## 21. Paper operations

Daily cycle (24/7 crypto): continuous ticks; news refresh every few ticks; inventor every ~30 minutes; equity/history series appended per tick; Operator halts via the deck kill button or `mv-kill`.

Mandatory scenario coverage (gap opens, partial-fill races, feed loss mid-position, restart mid-session, clock drift): PLANNED as a scripted scenario suite (Wave 4). Today's coverage: unit/integration tests + the governor's failover/staleness/breaker paths + loop-level exception isolation.

## 22. Promotion gates

| Gate | Threshold (Conservative profile) | Status |
|---|---|---|
| Statistical | Full validation gate ACTIVE + >= 100 trades, OOS Sharpe >= 1.0, max DD <= 10 percent | IMPLEMENTED |
| Duration | >= 3 months sustained paper | IMPLEMENTED |
| Projection honesty | abs(live minus paper Sharpe) <= 0.5, enforced ongoing once live | IMPLEMENTED |
| Compliance | SEBI algo cleared, LRS/FEMA cleared, withdrawal-disabled + IP-allowlisted keys, tax configured; all must attest true | IMPLEMENTED (blocks graduation) |
| Operator signature | Authed, journaled graduate action per strategy | IMPLEMENTED |
| Capital cap | Initial live capital <= 1 percent of equity | IMPLEMENTED |
| Execution-quality gate | Calibrated fill model, resolved rejects | PLANNED (depends on Sections 18 and 20) |
| Reconciliation gate | Zero unexplained breaks vs broker | PLANNED (needs a live broker adapter; Wave 4) |

## PART V: EXECUTION AND RISK

## 23. Order lifecycle

Today (paper): PROPOSED -> risk gate -> (BLOCKED with journaled reason | AUTHORIZED) -> market order -> FILLED -> journaled with intended price, fill price, realized slippage bps, fees.

Target OMS state machine (adopted from the reference design, PLANNED with live execution): adds PENDING_SEND, SENT, ACKNOWLEDGED, PARTIAL, CANCEL_PENDING, REJECTED, EXPIRED, UNKNOWN with idempotent client order ids, duplicate-send freeze on UNKNOWN, and cancel/fill race handling.

## 24. Venue adapters and reconciliation

| Area | Today | Target |
|---|---|---|
| Execution venue | Single NautilusTrader paper venue | Live broker adapter behind the same `ExecutionEngineProtocol` (graduated strategies only) |
| Data-source reconciliation | Cross-source close comparison with halt-on-divergence exists (`get_bars_reconciled`) but the loop calls the plain read | Switch the loop to reconciled reads for the chart/decision symbol set (Wave 1) |
| Position/cash reconciliation | Not applicable (paper, internal ledger is authoritative) | Broker-vs-ledger reconciliation hierarchy before any live order (Wave 4) |
| Session controls (India) | Not built | Daily API logout/reset evidence, static-IP egress, algo tagging (Section 29) |

## 25. Risk architecture

### 25.1 Pre-trade checks (the inviolable gate)

Every order passes `RiskEngine.check`; all values are `Decimal` fractions of equity.

| Check | Aggressive default (active profile) |
|---|---|
| Kill switch | Tripped rejects everything |
| Daily loss breaker | 3 percent of day-start equity |
| Max drawdown breaker | 20 percent from peak |
| Single-position cap | 20 percent of equity |
| Concentration cap | 50 percent |
| Static per-position ceiling (named `kelly_fraction_cap`) | 50 percent; note: a static ceiling, not a Kelly formula |
| Gross exposure | 1.0x equity |
| Net exposure | 1.0x equity |

Profiles: aggressive (active), moderate, conservative (`RiskLimits` classmethods). Operator-set only.

### 25.2 Kill switch

Global, terminal until Operator reset (authed, journaled). Redis-shared so `mv-kill` reaches a running loop; falls back to an in-process switch with a warning when Redis is absent (the in-process veto still holds; the deck's kill button still works). Instrument- and strategy-scoped kill levels: PLANNED.

### 25.3 Known defects (verified, highest-priority remediation)

| Id | Defect | Evidence | Consequence | Fix (Wave 1/2) |
|---|---|---|---|---|
| R1 | The live loop builds `PortfolioState` with equity, peak, and day-start all equal to a never-re-marked starting slice | `packages/mv-api/mv/api/paper_loop.py` (state construction; `self._equity` assigned once) | Daily-loss and drawdown breakers can never fire in the running loop; drawdown shown on the deck is display-only | Mark equity to market into the risk state each bar (Wave 1) |
| R2 | Gross/net/concentration checks are coded portfolio-level but every caller feeds a single-symbol state | Same construction site; per-symbol sessions | Book-level caps degenerate to per-instrument caps; N correlated positions can stack | One shared cross-instrument `PortfolioState` (Wave 2) |

These are reported here deliberately: the platform's credibility rests on stating them, not on the breakers' theoretical existence.

### 25.4 Sizing

Today: signed conviction in [-1, 1] x max_position_pct x per-symbol equity slice, then risk-gated. Target: risk-based quantity (risk budget / stop distance, volatility floor, liquidity cap), adopted from the reference design (Wave 2).

## 26. Surveillance and stress

| Domain | Today | Target |
|---|---|---|
| Source telemetry | Measured per-source fetch latency p50/p95, request-rate quota vs public-tier budgets, green/amber/red, real last-failover stamps | IMPLEMENTED |
| PnL/exposure monitors | Deck panels (equity, day PnL, drawdown, exposures) polled live | IMPLEMENTED (display; automated de-risking depends on R1) |
| Bar sanity | Staleness guard (2x timeframe) + empty-frame rejection | PARTIAL: no OHLC sanity, gap, or outlier-wick guard at the bar boundary (Wave 1) |
| Halt awareness | None (halts read as staleness and fail over, which could source a price around a real halt) | Halt/limit-band state machine before equities (Wave 3) |
| Stress scenarios | None at book level (single-trade counterfactual replay exists) | Scenario engine: gap, vol spike, correlation-to-one, liquidity drought (Wave 4) |
| Crisis de-grossing | Static caps only | Vol-targeted exposure controller (Wave 2) |

## 27. Learning and governed adaptation

| Capability | Mechanism | Status |
|---|---|---|
| Attribution | Six-component causal decomposition (signal, timing, sizing, slippage, fees, regime residual) summing exactly to net | IMPLEMENTED (module); DORMANT as a serve provider (Wave 2 wiring) |
| Mistake taxonomy | Classifier over closed trades (false signal, late entry, oversizing, stale data, correlated pileup, ...) with frequency and cost stats | IMPLEMENTED (wired in serve) |
| Counterfactual replay | Re-run a recorded trade with one variable changed | IMPLEMENTED (module); DORMANT provider |
| Improvement ledger | Append-only record of proposed changes with held-out before/after evidence | IMPLEMENTED |
| Governed meta-learning | Bayesian-shrunk OOS-Sharpe weight proposals, anti-whipsaw velocity cap, regime eligibility, held-out validation; propose-only | IMPLEMENTED |
| Champion/challenger | Parallel versions | PLANNED |

## PART VI: LIVE READINESS AND INDIA COMPLIANCE

## 28. Environment progression

| Stage | Access | Status |
|---|---|---|
| Research | Backtest-plane data only | IMPLEMENTED |
| Backtest | Validation gate on historical/real-feed data | IMPLEMENTED |
| Paper | Live crypto data, simulated venue, full risk/journal | IMPLEMENTED (the operating mode today) |
| Shadow | Broker-observable state, no order submission | PLANNED (Wave 4) |
| Limited live | Graduated strategies, capped at 1 percent, Operator-keyed | Machinery IMPLEMENTED; disabled by default (BR-005); go-live is the Operator's manual, separately-keyed action |
| Scaled live | Staged increments on live-vs-paper honesty | PLANNED (governance defined via degraduation) |

## 29. India retail-algo requirements register (all PLANNED; gates any India live release)

Adopted from the reference design and current SEBI/NSE framework; to be revalidated against the chosen broker before any live release:

| Area | Requirement |
|---|---|
| API access | Unique credentials; approved/whitelisted static IP; explicit client/account mapping |
| Session | Compulsory daily API logout/reset with evidence before next session |
| Tagging | API orders treated as algo orders; exchange algo id/tag carried through intent, OMS, broker, and audit records |
| TOPS threshold | Order-per-second threshold compliance; above-threshold algos registered with unique ids |
| Hosting | Broker-hosted or permitted tech-savvy-client pattern per broker/exchange requirements |
| Keys | Scoped, withdrawal-disabled, IP-allowlisted (already the platform key policy; `docs/SECRETS.md`) |
| Compliance gate | `mv-risk` checklist (SEBI algo, LRS/FEMA, keys, tax) blocks graduation until attested; IMPLEMENTED today as the gating mechanism |

## 30. Release and rollback governance

| Control | Implementation | Status |
|---|---|---|
| Change control | PR-per-change, four CI gates (lint+types, tests+coverage, integration, frontend), merge on green | IMPLEMENTED |
| Reproducibility | Pinned `uv.lock`, commit SHA in backtest meta, deterministic seeds | IMPLEMENTED |
| Strategy rollback | Degraduation (live back to paper), de-adoption by roster restart | IMPLEMENTED / PARTIAL (adopted candidates do not persist across restarts yet) |
| Config rollback | Env-driven config; git history | IMPLEMENTED |
| Stop-the-line | Kill switch; loop pause on trip | IMPLEMENTED |

## PART VII: OBSERVABILITY, SECURITY, DASHBOARDS

## 31. Observability

### 31.1 Today

| Signal | Mechanism | Status |
|---|---|---|
| Health | `/api/v1/health` + per-source health with measured latency/quota | IMPLEMENTED |
| Performance | `/api/v1/metrics` JSON panel (Sharpe, Sortino, win rate, profit factor, expectancy, max DD) | IMPLEMENTED |
| Journal | Filterable journal explorer endpoint + UI | IMPLEMENTED |
| Real-time push | Authed WebSocket `/ws/stream` with polling fallback | PARTIAL (the serve loop does not publish to the hub yet; polling is the guaranteed path) |
| Metrics retention | In-memory per process | PARTIAL (history ring buffer only) |

### 31.2 Gaps (target design)

| Gap | Target | Wave |
|---|---|---|
| Prometheus/Grafana | Exporter + dashboards (compose profile exists for later use) | 4 |
| Alerting | Severity ladder S0 (runaway orders, kill failure) to S3 (cosmetic), each alert with owner and dedup key | 4 |
| Durable journal in serve | The loop rebuilds an in-memory `Journal()` per tick; the tested Postgres store is unwired, so the tamper-evident log is ephemeral across restarts | 1 |
| Incident records + runbooks RB-01..08 (broker down, unknown order, stale feed, position mismatch, loss stop, bad release, credential compromise, corporate-action error) | Adopt the reference runbook set; today's implemented subset is kill/reset, ladder failover, and staleness halts | 4 |

## 32. Security posture (verified by the security sweep)

| Control | State |
|---|---|
| Operator token | CSPRNG-generated by launchers, persisted to git-ignored `.env`; no static defaults; timing-safe comparison on every mutating endpoint |
| Transport surface | API and UI loopback-bound; loud warning on non-loopback binds; explicit-origin CORS; authed WebSocket (close-before-accept) |
| Secrets | Env-only at call time; `.env` git-ignored; no hardcoded keys (swept); exchange-key policy: scoped, withdrawal-disabled, IP-allowlisted |
| Injection surface | No eval/exec/pickle/yaml.load/shell=True; no SQL string building; XML parsing size-capped and namespace-tolerant; all HTTP calls carry timeouts |
| External content | RSS bodies size-capped (2 MiB), headlines length-capped server-side, escaped client-side |
| Supply chain | npm audit clean (0 vulnerabilities after the Next/postcss remediation); pinned Python lock; CI `contents: read` |
| Data plane | Compose services loopback-published, passwords required from env |

## 33. Resilience

| Concern | State |
|---|---|
| Zero-infra degradation | Paper trading runs with no Docker: in-process kill switch fallback with explicit warning |
| Process isolation | One bad symbol or tick never kills the server; background threads are non-fatal |
| Backups / DR | PLANNED (journal durability first, Wave 1; then scheduled export) |

## 34. Dashboard information architecture

Ten screens, dark trading-terminal design system (single token source in `packages/mv-ui/app/globals.css`: slate surfaces, monospace numerals, amber accent, reserved green/red, CVD-validated palette; no emojis, no decorative icons).

| Reference cockpit | Realized as | Status |
|---|---|---|
| Executive cockpit | Live Dashboard: INR equity curve, day PnL, drawdown, positions, B/S/H feed, regime chip, kill switch, price chart with trade markers, performance panel, blotter, news | IMPLEMENTED |
| Strategy lab | Strategy Lab (catalog, gate status) + Strategy Inventor (candidates, evidence, adopt) | IMPLEMENTED |
| Risk cockpit | Risk Console (limits, exposures, kill state) | IMPLEMENTED (headroom/stress views PLANNED) |
| Trading operations | Agent Room (decision transcripts) + Journal Explorer + blotter | IMPLEMENTED (order-funnel view PLANNED with OMS) |
| Data and model health | Source Health (real telemetry) + Post-Mortem Room | IMPLEMENTED |
| Compliance and audit | Settings (read-only config; never secrets) + journal | PARTIAL (dedicated compliance/audit workspace PLANNED with India live) |

## PART VIII: TECHNOLOGY, DECISIONS, ROADMAP

## 35. Technology stack (as built) and ADR register

Python 3.12 (uv workspace monorepo), Pydantic v2, mypy strict, ruff, Decimal money; Polars data plane with pandas only at the strategy/vectorbt seam; NautilusTrader execution spine; vectorbt research engine; LangGraph agents with an offline-gated LLM seam (Ollama local, Anthropic cloud); ClickHouse/Postgres/Redis via Docker Compose (optional for paper); FastAPI + WebSocket; Next.js + lightweight-charts; GitHub Actions CI. Considered and not adopted from the reference design: Streamlit (Next.js already shipped), DuckDB (ClickHouse + Parquet cover the plane), Prefect/Dagster (the watch loop and CI cover current orchestration needs).

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Crypto-first paper MVP in INR before equity breadth | Adopted |
| ADR-002 | alphakit 3-protocol seam as the backbone; everything plugs in via a protocol | Adopted |
| ADR-003 | NautilusTrader bridge for paper/live parity (same strategy code both sides) | Adopted |
| ADR-004 | Deterministic-first agents; LLM advisory with fallback; never on the risk path | Adopted |
| ADR-005 | Propose-only learning (meta-learning and inventor); Operator adopts | Adopted |
| ADR-006 | Live USD/INR via the FX governor with a fixed offline fallback; display currency INR | Adopted |
| ADR-007 | Validated-not-proven gate; synthetic evidence can never grade active | Adopted |
| ADR-008 | Paper-only default; live requires graduation + compliance + Operator signature (BR-005) | Adopted |
| ADR-009 | Single-source dark terminal design tokens; no decorative iconography | Adopted |
| ADR-010 | Zero-infra paper mode on the Operator workstation (no Docker required) | Adopted |
| ADR-011 | Limit-order-first execution policy for any live venue | Proposed (Wave 3) |
| ADR-012 | Event-sourced OMS with idempotent client order ids for live | Proposed (Wave 4) |

## 36. Remediation register (verified defects and dormant wiring)

Ordered by risk; each item cites its section.

| Id | Item | Section | Wave |
|---|---|---|---|
| R1 | Mark equity to market into the risk state (breakers currently inert) | 25.3 | 1 |
| R2 | Book-level shared `PortfolioState` across instruments | 25.3 | 2 |
| R3 | Wire depth-aware slippage + liquidity size cap into paper fills | 18, 20 | 1 |
| R4 | Switch the loop to reconciled multi-source reads; drop the hardcoded reconcile flag | 24 | 1 |
| R5 | Durable journal in serve (stop per-tick rebuild; wire the Postgres store) | 31.2 | 1 |
| R6 | Accrue perp funding; apply the India tax model to reported PnL | 18 | 1 |
| R7 | Bar-boundary guards: OHLC sanity, gap/outlier detection | 26 | 1 |
| R8 | Populate `AgentContext.features` (activates six analysts) | 13 | 2 |
| R9 | Risk-based sizing; rename the static kelly cap to what it is | 25.4 | 2 |
| R10 | Wire attribution/replay/arbitrage providers into serve | 27 | 2 |
| R11 | Persist adopted inventor candidates across restarts | 30 | 2 |
| R12 | WebSocket publisher from the serve loop | 31.1 | 2 |

## 37. Forward roadmap (four waves)

| Wave | Theme | Contents |
|---|---|---|
| 1. Correctness | Make what exists true | R1, R3, R4, R5, R6, R7; deep real-history gate runs for the live crypto roster |
| 2. Book-level risk and intelligence | Trade one book, not eleven silos | R2, R8, R9, R10, R11, R12; correlation-cluster limits; vol-targeted exposure controller; portfolio allocation beyond equal split |
| 3. Breadth | More markets, real derivatives, better orders | US/India/FX domains live behind flags; instrument master; session calendars + halt awareness; perp/options data adapters (real vol surface); event-driven strategies from existing SEC/news feeds; limit/stop orders, partial fills, reject handling |
| 4. Live-readiness operations | Institutional ops before real money | Prometheus/Grafana + alert ladder; shadow mode; scenario/stress engine; scripted failure drills; India SEBI retail-algo implementation (Section 29); broker execution adapter + reconciliation hierarchy; purged CV + parameter-stability in the gate |

Wave order is deliberate: nothing in Waves 2 to 4 is trustworthy while Wave 1 defects make the displayed risk posture kinder than reality.

## 38. Core API surface (implemented)

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /api/v1/health`, `/health/sources` | Liveness + per-source telemetry | none (loopback) |
| `GET /api/v1/portfolio`, `/portfolio/history`, `/positions`, `/metrics`, `/trades`, `/ohlcv`, `/news` | Deck data | none (loopback) |
| `GET /api/v1/decisions` (clamped), `/decisions/{id}/agents`, `/journal` (filter + clamp) | Decision transcripts and audit | none (loopback) |
| `GET /api/v1/strategies`, `/strategies/{slug}`, `/candidates`, `/arbitrage`, `/risk/limits`, `/settings` | Registry, inventor, risk, config (never secrets) | none (loopback) |
| `POST /api/v1/risk/kill`, `/risk/reset` | Kill switch | Operator token |
| `POST /api/v1/candidates/{name}/adopt` | Adopt an inventor survivor | Operator token |
| `POST /api/v1/strategies/{slug}/graduate` | Graduation (eligibility + compliance enforced) | Operator token |
| `WS /ws/stream` | Real-time push (polling fallback) | Operator token |

## 39. Glossary and maintenance

| Term | Definition |
|---|---|
| Governor | The failover data router: registry of domains, priority ladders, breakers, staleness, health |
| Gate | The validation pipeline that decides observe/active/failed |
| Graduation | Operator-signed promotion of an active strategy to capped live eligibility |
| Projection honesty | abs(live Sharpe minus paper Sharpe); the North Star tolerance is 0.5 |
| Provenance tag | The committed `data_source` string that marks backtest evidence real or synthetic |
| Observe-only | Tradable in paper research but barred from active/live by evidence class |
| Operator | The single human owner; the only authority for kill reset, limits, adoption, graduation |

Maintenance cadence:

| Cadence | Update |
|---|---|
| Every merged PR that changes architecture | The affected section + status tags + remediation register |
| Every phase completion | Package map, roadmap wave status, ADR register |
| On external change (broker API, SEBI circular, fee schedule, data-source ToS) | Sections 6, 18, 29 |

## Appendix A: Implementation-status master table

| Component | Module | Status |
|---|---|---|
| Failover governor (ladder, breaker, staleness, health) | `mv-failover` | IMPLEMENTED |
| Cross-source reconciliation in the live loop | `mv-failover/router.get_bars_reconciled` | DORMANT |
| US / India / FX governor domains | `mv-failover/ladders.py` | DORMANT (registered, unqueried) |
| Point-in-time feature store, as-of, leakage check | `mv-intelligence` | IMPLEMENTED, DORMANT in live decisions |
| FRED no-train guardrail | `mv-intelligence/guardrail.py` | IMPLEMENTED |
| News to sentiment (deck panel) | `mv-api/news_feed.py` | IMPLEMENTED (display only) |
| Strategy catalog (109) with provenance | `alphakit-strategies-*` | IMPLEMENTED (29 real / 80 synthetic) |
| Live crypto roster (9) + regime ensemble | `mv-api/roster.py`, `mv-agents/baseline` | IMPLEMENTED |
| Validation gate (walk-forward, regime, DSR, MC) | `alphakit-bench/validation` | IMPLEMENTED |
| Strategy inventor (grid + genetic + LLM, propose-only) | `alphakit-bench/inventor`, `mv-api/inventor_view.py` | IMPLEMENTED |
| LangGraph agent pipeline + LLM seam | `mv-agents` | IMPLEMENTED (six analysts neutral pending features: PARTIAL) |
| Risk engine + limits + kill switch | `mv-risk` | IMPLEMENTED (defects R1, R2 registered) |
| Graduation / compliance / degraduation / live guard | `mv-risk` | IMPLEMENTED (live path disabled by default) |
| NautilusTrader paper venue + fees | `alphakit-bridges/nautilus_bridge.py` | IMPLEMENTED |
| Depth-aware slippage model in fills | `alphakit-bridges/cost_model.py` | DORMANT (arb detection only) |
| India crypto tax in PnL | `alphakit-bridges/cost_model.py` | DORMANT |
| Hash-chained journal | `mv-journal` | IMPLEMENTED (ephemeral in serve; Postgres store DORMANT) |
| Post-mortem attribution / replay / ledger / meta-learning | `mv-postmortem` | IMPLEMENTED (serve providers partially DORMANT) |
| Source telemetry (latency, quota, failover stamps) | `mv-api/telemetry.py` | IMPLEMENTED |
| GEX / Vol Desk logic | `mv-intelligence/gex` | IMPLEMENTED (mock-fed) |
| Arbitrage detection (after-cost, R/A/G) | `mv-intelligence/arbitrage` | IMPLEMENTED (offline; serve provider DORMANT) |
| Forecasting (GBM; deep extras) + MLflow | `mv-intelligence` | DORMANT |
| Command Deck (10 screens, dark terminal tokens) | `mv-ui` | IMPLEMENTED |
| Prometheus / Grafana / alerting | none | PLANNED |
| Shadow mode / OMS state machine / broker execution adapter | none | PLANNED |
| Instrument master / corporate actions / session calendars | none | PLANNED |

## Appendix B: Open decisions

| Decision | Question | Blocking |
|---|---|---|
| Options data vendor | Paid chain/GEX source (Polygon or alternative) for real vol surfaces | GEX go-live, options strategies beyond synthetic |
| India execution broker | Which broker API executes (data ladder already Dhan-first) | Shadow mode, India live |
| LLM routing defaults | Which agents route to Ollama vs cloud when enabled | Agent-mode depth (safe default: deterministic) |
| India private repos | Fold in `india-preopen-quant-engine` and `nse-market-intel` content | India strategy breadth (Operator to provide) |
