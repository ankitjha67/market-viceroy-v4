# Phase 13 — Strategy Inventor

An autonomous strategy-discovery loop: **generate** candidate strategies →
**backtest + validate** each through the existing gate → **propose** the survivors
for one-click Operator adoption into the paper roster. You already have the hard
part — the validation gate *is* the backtest-and-judge engine; this phase builds
the generator + the orchestration loop that feeds it, plus the propose/adopt
surface.

## Decisions (locked this session)
- **Invention methods: all three** — parameter search (foundation), genetic
  combination, and LLM-proposed strategies.
- **Deploy policy: propose, one-click adopt.** Gate-passers are proposed with
  their full validation evidence; the Operator adopts into the paper roster. The
  inventor **never auto-deploys** (paper or live), honoring CLAUDE.md #5's
  human-gated selection. Real-money live stays the separate Phase-7 gate.

## Non-negotiables (apply with full force)
- **Validated, not proven (#4).** No invented strategy reaches the roster without
  a full gate pass on real-feed data (walk-forward + deflated Sharpe + Monte Carlo
  + regime + cost-aware). Synthetic never counts; gross-positive alone never
  passes. The inventor is a candidate *firehose* only in front of the gate; behind
  it, almost everything is (correctly) rejected.
- **No naive PnL-chasing (#5).** Generation is bounded to composable building
  blocks — it cannot invent leverage / martingale mechanics; the gate + propose-
  only adoption are the governance.
- **Point-in-time + deterministic CI.** Backtests are date-gated; the pure
  generation/orchestration logic is CI-tested on fakes; real grading + the LLM
  proposer run offline (the Phase-2 pattern). No look-ahead.

## Build order
- **13.1 — Inventor core (SHIPPED, this PR).** `alphakit-bench/inventor/`: the
  `Candidate` spec, `parameter_search` + genetic `mutate`/`crossover`/`evolve`
  generators, the `run_inventor` loop (grades candidates through an injected
  evaluator, ranks survivors), and the propose-only `CandidateQueue`. Pure +
  tested against a fake gate.
- **13.2 — Real evaluator (SHIPPED).** `inventor/evaluator.py`: a `Candidate` ->
  live `StrategyProtocol` factory registry (ema/sma/donchian crosses,
  rsi/bollinger/zscore — the parameterizable crypto families) + `candidate_evaluator`,
  which grades a candidate through the existing `ValidationGate.evaluate` (fresh
  cost-aware backtest → walk-forward → regime → deflated Sharpe → Monte-Carlo →
  decide) over an injected price frame. `DEFAULT_GRIDS` + `valid_combo` define the
  search space. A broken candidate grades FAILED, never crashing the run; on
  synthetic data everything grades OBSERVE (the "validated, not proven" rail flows
  straight through — the loop yields zero survivors, proven end-to-end without a
  fake gate).
- **13.3 — LLM proposer (SHIPPED).** `inventor/llm.py`: `llm_propose` takes an
  injected `propose_fn` (prompt -> text; the real one wraps the Phase-4 router,
  offline-gated) and `parse_candidates` validates the JSON against the allowed
  templates + *in-range* params — an LLM may only pick a known template with params
  inside the grid's range (it cannot invent leverage/martingale), and any missing
  router / unparseable response falls back to a deterministic grid slice, so CI +
  offline stay reproducible. The gate is the safety net for whatever parses.
- **13.4 — Combined search + offline runner (SHIPPED).** `inventor/search.py`
  `full_search` combines all three methods deduped by spec (genetic uses
  *interpolating* mutation to reach novel in-range values a grid never enumerates,
  so it adds candidates beyond the exhaustive search). `scripts/run_inventor.py`:
  fetch bars via the governor -> `full_search` -> grade through the gate -> print +
  write a JSON report. The live `mv-serve` inventor now uses `full_search` too. A
  durable Postgres candidate store remains a follow-on (the zero-Docker Operator
  box persists via the JSON report / the served run).
- **13.5 — API + UI (SHIPPED).** `GET /api/v1/candidates` (the latest graded run +
  evidence) + `POST /api/v1/candidates/{name}/adopt` (Operator-authed). `mv-serve`
  runs a **background inventor** (`--no-invent` to disable): every ~30 min it
  searches the crypto families and grades them through the gate over the
  accumulated INR history, storing the run + the survivor queue. Adoption builds
  the candidate's strategy (uniquely named per parameterization) and appends it to
  the live paper roster. `mv-ui` **Strategy Inventor** screen: the graded
  candidates with their deflated-Sharpe / OOS-Sharpe / walk-forward evidence, the
  tested/survived summary, and an Operator-token Adopt button on the survivors.

## The honest constraint (crypto history depth)
The free CCXT feed caps ~500 bars with no date-range — not enough for a robust
walk-forward. So the inventor's crypto backtests run on **bar history the platform
accumulates over time** (the loop stores bars; validation deepens the longer it
runs) or a longer-history source. Early validation is shallow by construction;
this is disclosed, not hidden. The non-crypto real-feed families (rates / macro /
commodity) already have the history for a full gate today.

## 13.1 — what shipped
`alphakit-bench/inventor/`: `candidate.Candidate` (+ `make_candidate`),
`generate.parameter_search` + `mutate` / `crossover` / `evolve` (deterministic;
genetic ops take an injected RNG), `inventor.run_inventor` / `survivors` (grade +
rank via an injected `Evaluator = Candidate -> GateResult`, reusing the Phase-2
`GateStatus`/`GateResult`), and the propose-only `CandidateQueue` (propose only
ACTIVE, dedup, adopt). 9 tests; `ruff` + `mypy --strict` (full tree) green. Not
wired to the loop/UI — the tested core, with the real evaluator + surface as the
next slices.
