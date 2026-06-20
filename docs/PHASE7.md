# Phase 7 — Live trading (gated, staged): exit-gate evidence

Phase 7 exit gate (PRD §12, US-010): **per strategy — a sustained honest paper
record + inviolable limits respected + Operator sign-off → capped live.** This
phase builds and tests the graduation machinery, the capped-live wiring, live-
slippage recalibration, and projection-honesty tracking.

> **Safety posture (read first).** This phase ships the *machinery* for going
> live. **It does not place real-money orders, and CI never does.** The live
> order path is exercised only against the paper venue. Real capital go-live is
> the Operator's manual, separately-keyed action (funded, withdrawal-disabled,
> IP-allowlisted keys) — see the runbook below.

## Graduation gate (BR-005 / US-010) — Conservative bar

`mv-risk/graduation.py`: `evaluate_graduation(PaperRecord, thresholds) ->
GraduationVerdict(eligible, reasons, live_cap_pct)`. A strategy is eligible only
when **every** criterion passes (Conservative defaults):

| Criterion | Bar |
|---|---|
| Gate status | `active` (real-feed, validated — never synthetic) |
| Sustained paper | ≥ 3 months |
| OOS Sharpe | ≥ 1.0 |
| Max drawdown | ≤ 10% |
| Paper trades | ≥ 100 |
| Projection honesty (once live) | \|live − paper Sharpe\| ≤ 0.5 |
| Initial live capital | capped ≤ 1% of equity |

Thresholds are stored config (`conservative` / `moderate` / `aggressive`
presets), retunable. Projection honesty is an **ongoing post-live** check —
absent before any live history, enforced after.

## Compliance pre-checks (§13)

`mv-risk/compliance.py`: graduation is **blocked** until the `ComplianceChecklist`
is all-clear — SEBI algo obligations, LRS/FEMA cross-border, withdrawal-disabled
keys, tax configured. A gate, not legal advice: it records the Operator's
attestations and blocks while anything is unresolved.

## Live-order guard (BR-005 / FR-P6 / FR-X1)

`mv-risk/live_guard.py` + the loop: `LiveGuardConfig(mode, graduated, live_cap_pct)`.
In **paper** mode every order passes (default — unchanged). In **live** mode an
order is allowed **only** if its strategy is graduated, and its size is **clamped
to the cap**; the inviolable `RiskEngine` still gates it afterwards. The loop
journals a `live_blocked` event for an ungraduated live order. The order path is
identical paper↔live (FR-X1); only the venue clients differ for real go-live.

## Recalibration (FR-X4) + projection honesty (North Star)

- `mv-postmortem/recalibrate.py`: `recalibrate_slippage(real_fills)` learns the
  empirical slippage (intended vs actual fill, reusing the Phase-5 `Fill`) and
  blends it with the model prior — so the cost model stops flattering net-PnL
  with a stale estimate. It informs the cost model; it never relaxes a limit.
- `mv-postmortem/honesty.py`: `projection_honesty(paper, live)` + `HonestyTracker`
  — the North Star |live − paper Sharpe| per graduated strategy; a breach beyond
  tolerance is an input to de-graduation.

## Operator sign-off (FR-P6)

`POST /api/v1/strategies/{slug}/graduate` (single-operator-token, journaled).
`build_graduate_handler` composes eligibility + compliance; the endpoint promotes
**only** when both pass AND the Operator signs off. Meta-learning has **no**
promotion path. Every attempt — success or rejection — is journaled
(`graduation`) and persisted (`0004_phase7_graduation.sql` / `GraduationStore`).
`/strategies` surfaces each strategy's `live_status` (`paper` / `live`).

## Operator go-live runbook (manual, outside CI)

1. Confirm the strategy is gate-`active` with a sustained honest paper record.
2. Complete the §13 compliance checklist (SEBI/LRS/keys/tax) — attest each item.
3. Provision **scoped, withdrawal-disabled, IP-allowlisted** exchange keys in the
   vault; never in code.
4. `POST /strategies/{slug}/graduate` with the Operator token → promotes if
   eligible + compliant.
5. Run the loop with `live_guard=LiveGuardConfig(mode="live", graduated={...},
   live_cap_pct=Decimal("0.01"))` pointed at the live venue clients, tiny capital.
6. Watch projection honesty; the kill-switch remains terminal and Operator-only.

## Non-negotiables honored

- **Live requires graduation (BR-005):** no code path reaches a live order
  without graduation; everything defaults to paper.
- **Operator-only promotion (FR-P6):** authed + journaled; no autonomous/meta-
  learning promotion exists.
- **Inviolable risk live:** the same `RiskEngine` + terminal kill-switch gate
  live orders; live capital capped ≤ 1%.
- **Secrets in a vault (#6):** live keys scoped/withdrawal-disabled/IP-allowlisted,
  from env at call time — never in code. No real-money orders by the agent or CI.
- **Projection honesty (North Star)** tracked; **Decimal** money throughout.

## Verification (all green)

- **Unit (CI, no real trades):** graduation gate (each criterion; synthetic/
  non-active never eligible); compliance (any unresolved flag blocks); live guard
  (ungraduated → no live order; graduated → capped, still risk-gated); the loop
  in live mode (`live_blocked` journaled; graduated fills clamped to the cap);
  recalibration + honesty; the graduate endpoint (Operator-authed; ineligible/
  uncompliant → 422 with reasons; journaled) + the composition handler.
- **Integration (CI):** `graduation` Postgres round-trip (FR-P6), via migration
  `0004`, alongside the existing journal/gate/features/improvement jobs.
- Gates: full-tree `ruff check` + `ruff format`, `mypy --strict`, `pytest` with
  the ≥85% coverage gate.

## Scope boundaries

- **No real-money trading in this phase** — machinery only; go-live is the
  Operator's manual funded action.
- De-graduation automation (acting on a projection-honesty breach) and live-fill
  cost-model write-back are follow-ons; Phase 7 ships the measurement + the guard.
- The Command Deck live-trading UI is Phase 8; Phase 7 ships the data + API.
