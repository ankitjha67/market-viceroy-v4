# Phase 4 — Multi-agent orchestration (LangGraph → Buy/Sell/Hold): exit-gate evidence

Phase 4 exit gate (US-002): **agents produce a journaled, debated, risk-checked
Buy/Sell/Hold; the PM proposes sizing; the autonomous journaled B/S/H drives
paper execution within the inviolable limits.** Built the LangGraph agent
pipeline that replaces the Phase-1 deterministic ensemble as the source of the
decision — the "fund in a glass box."

## The pipeline (PRD §4.5, §5, FR-A1–A9)

```
AgentContext (point-in-time feature snapshot + Phase-1 strategy ensemble)
  -> analysts   : News, Macro, Flow, Fundamentals, Valuation, Technical, Sentiment  -> [AnalystView]
  -> debate     : Bull vs Bear marshal the evidence                                 -> [DebateTurn]
  -> research_manager : adjudicate bull/bear strengths                              -> ResearchVerdict
  -> portfolio_manager: net stance -> explicit BUY/SELL/HOLD + sizing               -> TradeDecision (proposed)
  -> risk       : the inviolable gate (RiskEngine)                                  -> RiskAssessment + GatedDecision
```

A real **LangGraph** `StateGraph` (1.2.5, pinned) with a `MemorySaver`
checkpointer wires the nodes; **every node journals its record** as it runs, so
the hash-chained journal is the persistent decision log (FR-A1/A3). The result
is the same `GatedDecision` the paper loop already consumes — a drop-in for the
Phase-1 ensemble. `build_agent_graph` / `run_decision` live in
`packages/mv-agents/mv/agents/graph/`.

## Deterministic-first, LLM seam wired (FR-A7/A9)

Every agent reasons **deterministically** over the point-in-time evidence — no
network, no LLM, no keys by default — so CI is fully deterministic and US-002 is
met with zero external dependencies. The LLM layer is the *optional* enhancement:

- `mv/agents/llm/client.py` — `LLMClient` protocol + `LLMRequest`/`LLMResponse`
  (provider, model, tokens, **latency, cost** → the journaled `llm_meta`).
- `mv/agents/llm/router.py` — `LLMRouter`: **per-agent** routing (FR-A7); an
  unrouted agent stays deterministic.
- `mv/agents/llm/providers/{ollama,anthropic}.py` — offline adapters (local
  Ollama; cloud Anthropic with per-call dollar cost). Network I/O is
  `# pragma: no cover`; request-build / parse / cost are tested via an injected
  transport. The Anthropic key is read from `ANTHROPIC_API_KEY` at call time
  (vault-supplied, never hardcoded — CLAUDE.md #6).
- `reason_or_fallback` — the **FR-A9 rule**: try the routed LLM, parse a typed
  record, and on **any** failure (transport/timeout/parse) fall back to the
  deterministic reasoner. An LLM is never on the path of a risk check.

## Non-negotiables honored

- **Inviolable risk rails (FR-A6/R2):** the Risk Manager *is* the Phase-1
  `RiskEngine` — the PM proposes, the engine disposes. The single sizing+risk
  path (`gate_proposed_trade`) is shared by the baseline and the graph, so a
  vetoed decision produces no order, journaled with the breach. No agent or
  autonomy setting re-enables a limit — only the Operator.
- **Point-in-time everything:** agents read **only** the `AgentContext` snapshot
  (Phase-3 as-of features, leakage-checked); every record carries the shared
  `snapshot_id`. No look-ahead.
- **FRED no-train:** the Macro analyst reads regime/FRED features as runtime
  inputs only; nothing is trained.
- **No naive PnL-chasing:** the PM acts on a debated, risk-gated thesis, not
  momentary-best switching; governed selection stays Phase 5.
- **Glass box / Decimal / honest:** every agent output journaled; money is
  `Decimal`; **sparse-data assets (crypto MVP) degrade to neutral/zero-confidence
  with an honest rationale — never a fabricated stance.**

## Loop + Agent Room API (FR-A8)

- `mv/api/paper_loop.py` — `AgentGraphStrategy` (subclasses `EnsembleStrategy`,
  swaps only the decision for the graph); `run_paper_session(..., use_agents=True)`
  selects it. Same NautilusTrader plumbing, sizing, and risk gate; the agent path
  adds the journaled debate transcript and runs autonomously (no human approval
  in paper).
- `mv/api/app.py` — `GET /api/v1/decisions/{snapshot_id}/agents` returns the full
  journaled pipeline for one decision (the Agent Room data; React UI is Phase 8).
- `scripts/run_agents.py` — offline transcript demo (no network/LLM).

## Verification (all green)

- **Unit (CI, no network):** §5 schemas; LLM router + FR-A9 fallback + adapter
  request/parse/cost (fake transports); each agent reasoner (known features →
  expected stance/verdict/decision; sparse → neutral); the **end-to-end graph**
  (synthetic snapshot → full journaled transcript → B/S/H); risk-veto → no order;
  HOLD journaled; determinism.
- **Integration (per-push, NautilusTrader):** `use_agents=True` paper session →
  the full transcript journaled (7 analyst views + debate + verdict + risk +
  decision per bar) + a paper fill + an intact hash chain
  (`test_paper_loop.py::test_agent_graph_loop_journals_full_transcript_and_fills`).
- **Offline (not per-push):** `uv run python scripts/run_agents.py` prints the
  glass-box transcript; `--llm ollama`/`anthropic` exercises a real provider
  offline (cost/latency journaled).
- Gates: full-tree `ruff check` + `ruff format`, `mypy --strict` (756 files),
  `pytest` (2589 passed) with the ≥85% coverage gate.

## Scope boundaries (deferred by design)

- Real LLM **routing in production** is wired but defaults to deterministic;
  turning on Ollama/Claude is an Operator config + offline runs.
- Crypto MVP analysts (fundamentals/valuation/news) mostly degrade to neutral —
  the Technical analyst (the strategy ensemble) carries the signal. Multi-asset
  agent depth grows in Phase 6; governed strategy selection + post-mortem
  meta-learning are Phase 5.
