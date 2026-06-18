# Phase 5 — Post-Mortem & governed meta-learning: exit-gate evidence

Phase 5 exit gate (US-005/006): **100% of closed trades carry a cause-tagged
causal attribution record, and the system explains every loss by cause and
demonstrates a governed improvement on a held-out window.** Built the full
Post-Mortem & Learning Engine (`mv-postmortem`): attribution, mistake taxonomy,
counterfactual replay, improvement ledger, and propose-only meta-learning —
turning the Phase-1 attribution stub into the real engine.

## Attribution — components sum to net (FR-P1, US-005)

```
journaled fills -> reconstruct_closed_trades (FIFO round trips) -> decompose()
   signal + timing + sizing + slippage + fees + regime  ==  net_pnl   (exactly)
```

- `decompose(trade)` splits realized net PnL via a telescoping additive scheme
  over the prices the trade saw (decision-reference, intended, actual). **signal**
  = idiosyncratic directional edge above the regime; **timing** = entry-delay;
  **sizing** = actual vs reference size; **slippage** = execution give-up on both
  legs; **fees** = the cost; **regime** = the benchmark/regime slice **plus any
  reconciliation residual**, so the six **sum to net PnL exactly** — proven by a
  500-case property test. The regime component is the labelled residual (drift
  unexplained by the rest), never silently padded.
- The loop's fill journaling is enriched with `intended_price` /
  `decision_ref_price` / `fees` / `slippage_bps` so real trades attribute.

## Mistake taxonomy (FR-P2)

`classify(attribution, context)` tags each **loser** with one category —
false_signal, late_entry, oversizing, stop_too_tight, regime_misread,
stale_data, slippage_blowout, correlated_pileup — using context signals first
(a data-quality event → stale_data; a correlated pile-up; an exit the market
then reversed) then the **dominant adverse component**. Winners return `None`
(honest — not every trade is a mistake). `mistake_stats` rolls up per-category
frequency + cumulative cost.

## Counterfactual replay (FR-P3)

`replay(run, base_params, variable)` re-runs a **recorded** scenario with **one
variable changed** (half size / limit-vs-market / no rotation) and returns the
PnL delta — the cost of the actual choice. The runner is injected, so the engine
re-runs over the recorded bars (no look-ahead, same point-in-time discipline);
`mv-postmortem` stays free of the paper-loop dependency.

## Governed meta-learning — propose-only (FR-P5)

`propose_weights(oos_sharpe, current_weights, …)` nudges strategy weights toward
out-of-sample Sharpe under a **Bayesian prior**, then applies, in order:

1. a **regime-eligibility gate** (ineligible strategies → 0 weight),
2. an **anti-whipsaw velocity cap** — all weights step toward the target by a
   single global rate, so no weight moves more than `max_velocity` per update
   while the weights still sum to 1 (a provable bound), and
3. **held-out validation** — the proposal is `adoptable` only if it beats the
   current weights on a held-out return window.

It returns a `WeightProposal` and **never mutates the loop or risk limits** — the
Operator adopts via the improvement ledger (FR-P4). This is the platform's most
important governance: the mitigation against naive PnL-chasing and overfitting.

## Non-negotiables honored

- **No naive PnL-chasing:** OOS Sharpe + Bayesian prior + anti-whipsaw cap +
  regime gate + **held-out validation before adoptable** + propose-only.
- **Inviolable risk:** meta-learning proposes only strategy weights, never risk
  limits or the kill-switch (Operator-only); never auto-promotes to live (FR-P6).
- **Validated, not proven:** an improvement counts only if it beats a held-out
  window; synthetic results never count as a real improvement.
- **Attribution honesty:** components sum to net by construction; 100% of closed
  trades get a record. **FRED no-train:** meta-learning trains on strategy OOS
  returns only. **Decimal** for all money/PnL.

## Post-Mortem Room API (data + API; UI is Phase 8)

`GET /api/v1/trades/{id}/attribution`, `GET /api/v1/postmortem/mistakes`,
`GET /api/v1/postmortem/improvements`, `POST /api/v1/postmortem/replay` — wired
via injected providers so the API stays decoupled from `mv-postmortem` and is
testable with fakes.

## Verification (all green)

- **Unit (CI, no network):** decomposition sums-to-net (500-case property test) +
  worked examples; trade reconstruction (round trips, partial closes, fee
  proration); mistake classifier (known attribution → expected tag, context
  precedence); counterfactual replay (injected runner); improvement ledger;
  meta-learning (anti-whipsaw cap, regime gate, shrinkage, **propose-only**,
  adoptable only on held-out improvement); the 4 endpoints (fakes).
- **Integration (CI):** `improvement` Postgres round-trip (FR-P4), via migration
  `0003_phase5_postmortem.sql`, alongside the existing journal/gate/features jobs.
- **Offline demo:** `uv run python scripts/run_postmortem.py` runs a recorded
  paper session then the full surface — attribution (sums to net), mistake
  trends, a half-size counterfactual, and an adoptable held-out weight proposal.
- Gates: full-tree `ruff check` + `ruff format`, `mypy --strict`, `pytest` with
  the ≥85% coverage gate.

## Scope boundaries (deferred by design)

- Meta-learning is **propose-only** (Operator adopts); auto-apply within caps is
  a future Operator toggle. Live promotion stays Phase 7 (FR-P6).
- Counterfactual realism is bounded by the recorded bars + the Phase-1 cost
  model (no full market-impact re-simulation).
- The Post-Mortem Room React UI is Phase 8; Phase 5 ships the data + API.
