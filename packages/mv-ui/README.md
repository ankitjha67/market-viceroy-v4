# mv-ui

React/Next.js **Live Dashboard** for Market Viceroy v4 — a unified home (₹ equity
curve, day P&L, Buy/Sell/Hold feed, positions, models/strategies, risk, learning,
source health) that drills into 9 detail screens: Agent Room, Strategy Lab,
Post-Mortem Room, Arbitrage Monitor, Risk Console, Journal Explorer, Source Health,
Settings. Editorial/understated; **no emojis, no AI-sparkle iconography, no slop**.

Next.js 15 (App Router) + React 19 + TypeScript + SWR (polling) + an Operator-authed
WebSocket + `lightweight-charts` (the equity curve). Money arrives as Decimal
strings from `mv-api` and is only *formatted* (INR), never re-computed as float.

```bash
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev          # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build  # the frontend CI gate
```

Start the backend first — `uv run mv-serve --watch` (continuous, INR) with
`MV_OPERATOR_TOKEN` set. The dashboard polls it and updates each tick; the
kill-switch relays the Operator's authed halt/reset. See `docs/RUNBOOK.md`.
