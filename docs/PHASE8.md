# Phase 8 — Command Deck UI (MVP-three): exit-gate evidence

Phase 8 ships the **Command Deck UI** (PRD §8) — the fund made visible. A
React/Next.js front end (`packages/mv-ui`) consuming the REST API built across
Phases 0–7. Exit: the **MVP-three screens** render live paper data with all four
states, in an **editorial, anti-slop** design, kill-switch always reachable.

## Screens (MVP-three, §8.2)

- **Command Deck** (`/`) — equity, day P&L (sign-coloured), a drawdown gauge
  (hand-built SVG vs the breaker), the **kill-switch** (inline confirm + Operator
  token); an open-positions table; a feed of the latest Buy/Sell/Hold (action,
  conviction, one-line rationale, link to the Agent Room); a source-health strip.
- **Agent Room** (`/agents`) — pick a decision → its pipeline as a vertical flow
  (analyst stance/score → bull/bear debate → Research Manager verdict → Risk
  verdict (approve/**VETO**) → PM Buy/Sell/Hold), each node expandable to its full
  journaled record. The "fund in a glass box."
- **Source Health** (`/health`) — a grid of sources by domain (status dot, quota
  burn, p50/p95 latency, last failover) + a reconciliation strip.

Every screen renders **Loading / Empty / Error / Loaded** explicitly via the
shared `<StatePanel>` (the error state is a degraded-mode banner).

## Design (anti-slop, §8.3 / CLAUDE.md #7)

Editorial "broadsheet" system in `app/globals.css` — warm paper, ink, an oxblood
accent, muted status (green/amber/red); serif display, system body, **tabular
mono** for every number; hairline rules, dense tables; a hand-drawn SVG monogram.
**Zero emojis, zero AI-sparkle iconography, no neon, no gradient text.** CSS
Modules per component (hand-crafted, not utility-soup). WCAG: visible focus,
semantic HTML, `prefers-reduced-motion`.

## Data + real-time

- `lib/api.ts` (typed fetch + `NEXT_PUBLIC_API_URL`), `lib/types.ts`,
  `lib/hooks.ts` (SWR polling, ~2 s `refreshInterval`). **Poll REST** — no
  WebSocket this phase; a `/ws/stream` is a documented follow-on.
- Money arrives as **Decimal strings** and is formatted for display only
  (`lib/format.ts`), never re-computed as float.
- Two small additive backend endpoints (injected providers, decoupled, tested):
  `GET /api/v1/portfolio` (equity/day-P&L/drawdown/peak) and
  `GET /api/v1/health/sources` (per-source status/quota/latency/failover/reconcile).

## Non-negotiables honored

- **Kill-switch reachable + Operator-only:** top of the deck; calls the
  token-authed, journaled `POST /risk/kill` / `/risk/reset`. The UI never
  re-enables limits itself.
- **No secrets in the UI:** no exchange keys; the Operator token is held in
  session memory only (`lib/token.ts`), never in code. (Settings/keys screen is
  deferred.)
- **Honest surfaces:** the UI shows exactly what the APIs report (B/S/H, gate
  status, VETO, after-cost edges) without embellishment. **No AI slop.**

## Verification (all green)

- **Frontend (new CI job `mv-ui`):** `next lint` clean; `tsc --noEmit` clean;
  **16 Vitest tests** (the four states per screen + the API client, mocked
  fetch); `next build` (production) compiles all three routes.
- **Backend:** the two new endpoints TestClient-tested with fakes; the full
  Python gate (ruff / mypy --strict / pytest ≥85%) stays green.
- **Local run:** `docker compose up -d` + `uv run mv-paper` (backend) +
  `NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev` in `packages/mv-ui`
  renders the deck over live paper data; the kill-switch trips with the token.

## Scope boundaries (deferred by design)

- **MVP-three** only; the other six §8.1 screens (Strategy Lab, Post-Mortem Room,
  Arbitrage Monitor, Risk Console, Journal Explorer, Settings) are incremental —
  their APIs already exist.
- **Polling, not WebSocket** (`/ws/stream` follow-on).
- Richer charts (ECharts heatmaps, lightweight-charts equity tape) land with the
  Strategy Lab / Post-Mortem screens; the MVP uses hand-built SVG.
