# RUNBOOK — running Market Viceroy v4 end-to-end

This is the operator's guide: set the platform up, get and place every API key,
run **real-time paper trades**, **backtest**, watch the **agents** reason and
improve strategies, and read **P&L** — on the terminal and in the Command Deck
UI. Paper-first throughout; **the platform never places a real-money order on its
own** (live go-live is your manual, gated action — see §13).

A useful fact up front: **the crypto paper loop and every offline demo run with
zero API keys.** Keys are only for breadth (US / India / macro) and the optional
cloud LLM. You can see the whole system work today without signing up for
anything.

---

## 0. The 60-second path (no keys, no Docker account needed)

**Windows, one command** — the launcher does setup + infra + migrations, prompts
you for each API key (Enter to skip), then gives a run menu. The only thing you
type is keys:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-MarketViceroy.ps1
```

Or do it by hand (any platform):

```bash
uv sync --extra dev                 # install the workspace
docker compose up -d                # Redis (+ Postgres, ClickHouse) — needed for the kill-switch
uv run mv-paper                     # real-time crypto paper session -> decisions, fills, P&L
```

`mv-paper` pulls the latest **real** BTC/USDT bars through the failover governor
(Binance→Kraken→Coinbase, public data, no key), runs the strategies → risk gate →
NautilusTrader paper fills, and prints decisions, fills, open positions, and
realized P&L. Everything below expands on this.

> Windows note: the commands are shown in `bash`. In PowerShell, `cp` is `Copy-Item`
> and inline `VAR=value cmd` becomes `$env:VAR='value'; cmd`.

---

## 1. One-time setup

| Step | Command | Why |
|---|---|---|
| Install | `uv sync --extra dev` | the uv workspace + dev tools (ruff/mypy/pytest) |
| Infra | `docker compose up -d` | ClickHouse (bars/features), Postgres (journal/relational), Redis (hot state + kill-switch) |
| Env | `cp .env.example .env` | your local config + keys (git-ignored, never committed) |
| DB schema | `uv run mv-migrate` | apply the Postgres migrations (journal, gate, graduation, …) |

Verify the toolchain is green any time:

```bash
uv run ruff check .          # lint
uv run mypy --strict packages/   # types
uv run pytest -q             # full suite (≥85% coverage gate)
```

**Docker is optional for paper trading.** `mv-paper`/`mv-serve` run with zero
infra: if Redis is unreachable they print a warning and fall back to an
in-process kill-switch (the inviolable in-process veto still holds; the UI's kill
button still works; only a separate `mv-kill` from another terminal can't reach
the run). Docker adds the **shared** kill-switch, journal/gate **persistence**
(Postgres via `mv-migrate`), and the ClickHouse feature store. Start it with
`docker compose up -d` when you want the full stack.

---

## 2. API keys — what, where to get them, where to paste them

**Where to paste:** all keys go in **`.env`** at the repo root (copy it from
`.env.example`). Uncomment the line and fill the value. Nothing reads keys from
code; every adapter reads from the environment at call time. `.env` is
git-ignored — never commit it, never paste a key into a `.py`/`.ts` file.

**Policy (enforced before any live use):** exchange/broker keys must be **scoped,
withdrawal-DISABLED, IP-allowlisted**, and vault-stored for shared use. For paper
trading you can use read-only/market-data tokens. See [SECRETS.md](SECRETS.md).

| Key (`.env` var) | For | Needed? | Where to get it |
|---|---|---|---|
| *(none)* | **Crypto** OHLCV (Binance/Kraken/Coinbase) | **Not needed** — CCXT public data | — |
| `FRED_API_KEY` | Macro series for the backtest gate's 4 macro-hybrid strategies | Optional (those stay `observe` without it) | https://fred.stlouisfed.org/docs/api/api_key.html (free). **Runtime input only — never trained on.** |
| `FINNHUB_API_KEY` | **US** equities (primary) | Optional (US breadth) | https://finnhub.io — free tier |
| `ALPACA_API_KEY` / `ALPACA_API_SECRET` | US equities (fallback) | Optional | https://alpaca.markets — free paper account |
| `DHAN_ACCESS_TOKEN` / `DHAN_CLIENT_ID` | **India** equities — **PRIMARY** | Optional (India breadth) | https://dhanhq.co → DhanHQ API → access token + client id |
| `UPSTOX_ACCESS_TOKEN` | India fallback 1 | Optional | https://upstox.com/developer/ → create an API app |
| `KOTAK_ACCESS_TOKEN` / `KOTAK_CONSUMER_KEY` | India fallback 2 | Optional | Kotak Neo → API portal |
| `ZERODHA_API_KEY` / `ZERODHA_ACCESS_TOKEN` | India fallback 3 (Kite) | Optional | https://kite.trade (Kite Connect). **Internal-use only — no data redistribution.** |
| `ANGELONE_API_KEY` / `ANGELONE_ACCESS_TOKEN` | India fallback 4 (SmartAPI) | Optional | https://smartapi.angelbroking.com |
| `EIA_API_KEY`, `POLYGON_API_KEY` | Energy / extra market data | Optional | https://www.eia.gov/opendata/ , https://polygon.io |
| `ANTHROPIC_API_KEY` | Cloud LLM for agent reasoning | Optional (agents are deterministic by default) | https://console.anthropic.com |
| `MV_OPERATOR_TOKEN` | Guards kill / reset / graduate; required by `mv-serve` | **Yes if you run the API/UI** | you choose it — a long random secret |

**India broker tokens expire frequently** (typically daily) — Dhan / Upstox /
Zerodha access tokens are regenerated through each broker's login flow. That's
expected; refresh them in `.env` when a fallback adapter reports an auth error.
The governor falls through the ladder, so a stale fallback doesn't stop you.

---

## 3. Run real-time paper trades

```bash
uv run mv-paper                                  # BTC/USDT 1h, deterministic ensemble
uv run mv-paper --symbol ETH/USDT --timeframe 15m --limit 300
```

What happens, end to end:

1. **Governor** fetches the latest `--limit` real bars for `--symbol` (CCXT
   public; fails over Binance→Kraken→Coinbase, logs the source used).
2. The **strategies** (EMA-cross, SMA-cross, Donchian-breakout) produce signals;
   the deterministic **ensemble** turns agreement into a Buy/Sell/Hold with
   conviction and dissent.
3. The **inviolable risk engine** gates every order (position/exposure caps,
   daily-loss, drawdown breaker, kill-switch). It cannot be bypassed.
4. **NautilusTrader** fills the approved orders on its **paper venue** (modeled
   slippage + fees + crypto-tax) — the *same* code path used for live.
5. The **hash-chained journal** records every decision, fill, and risk event.

Output:

```
[paper] BTC/USDT 1h via ccxt:binance (ensemble): 7 decisions, 3 fills, 1 open positions
[paper]   realized P&L (closed trades): -142.50  |  equity ~ 999857.50
```

**Important honesty note on "real-time":** each `mv-paper` run acts on the latest
window of bars and runs **one** session (it is not a always-on streaming daemon).
To act on new bars, re-run it (e.g. on a schedule). The strategies are
deterministic, so re-running over the *same* window gives the same result; new
bars (a new hour/minute elapsing) produce new decisions.

---

## 4. Switch the decision engine to the AGENTS

By default `mv-paper` runs the deterministic **ensemble**. To have the
**LangGraph multi-agent pipeline** take over the Buy/Sell/Hold instead:

```bash
uv run mv-paper --agents
```

Now the journaled decision is produced by the agent graph — Research pod →
analysts → bull/bear debate → Research Manager verdict → **inviolable risk veto**
→ Portfolio Manager B/S/H — rather than the ensemble. (The risk gate and paper
execution are identical; only the brain changes.) The agents reason
deterministically over point-in-time features by default; wiring a real LLM is
optional and offline (see §8 and `ANTHROPIC_API_KEY`).

---

## 5. The Command Deck UI + live P&L

One command runs a paper session and serves the API the React UI reads:

```bash
export MV_OPERATOR_TOKEN=your-long-random-secret   # PowerShell: $env:MV_OPERATOR_TOKEN='...'
uv run mv-serve --watch --interval 60 --timeframe 1m   # continuous; or plain `mv-serve` for one-shot
```

`mv-serve` runs a paper session (§3/§4), then serves the Command Deck API on
`http://127.0.0.1:8000` with the session's journal, computed equity/P&L, and open
positions. **With `--watch` it stays live**: every `--interval` seconds it re-runs
over the most recent window of bars and swaps the served data in place, so the
deck's equity/positions/decisions and the server logs keep updating as new bars
close (a short `--timeframe` like `1m` moves visibly each minute). Then start the
front end:

```bash
cd packages/mv-ui
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
```

Open http://localhost:3000 — the **Command Deck** shows live equity / day P&L /
drawdown, the open-positions table, and the latest B/S/H feed; the **kill-switch**
(top of the deck) trips the inviolable halt using your `MV_OPERATOR_TOKEN`. The
other screens — Agent Room, Strategy Lab, Post-Mortem Room, Arbitrage, Risk
Console, Journal Explorer, Source Health, Settings — read the same API.

Notes:
- **`--watch` keeps it live** — equity, positions, decisions, and logs update each
  interval as new bars close (the polling UI picks them up automatically). Without
  `--watch`, `mv-serve` serves one session over the latest window; restart it to
  refresh. Each tick re-runs over the most recent window, so equity reflects that
  rolling window rather than a single anchored start.
- The displayed position *entry* is the average fill on that side (a paper
  approximation); **realized P&L is exact** from closed round trips.
- `MV_OPERATOR_TOKEN` must be set or `mv-serve` refuses to start (it guards the
  mutating endpoints). The UI's only mutation is the kill-switch.

---

## 6. Backtest — the validation gate

Backtesting here is not a single equity curve; it's the **validation gate**
(walk-forward + regime + cost-aware + deflated Sharpe + Monte-Carlo) that decides
whether a strategy's edge is real enough to reach `active`.

```bash
uv run python scripts/run_gate.py                 # grade the real-feed candidates
uv run python scripts/run_gate.py --slug ema_cross_12_26
uv run python scripts/run_gate.py --limit 5
```

It runs offline over the real-feed strategies and assigns each `active` /
`observe` / `failed` **honestly** — a strategy is `active` only if it passes every
stage (gross-positive alone never passes; synthetic data never passes). The 4
macro-hybrid candidates need `FRED_API_KEY` to grade, else they stay `observe`.
Results land in each strategy's `benchmark_results.json` and Postgres, and surface
on the **Strategy Lab** UI screen and `GET /api/v1/strategies`.

For the broader alphakit benchmark harness (all families):
`uv run python scripts/benchmark_all.py`.

---

## 7. See how the strategies/agents work (glass box)

```bash
uv run python scripts/run_agents.py                        # deterministic transcript
uv run python scripts/run_agents.py --sentiment 0.8 --regime -0.4
```

Prints the full agent transcript over one point-in-time snapshot: each analyst's
stance/score/rationale, the bull/bear debate, the Research Manager's verdict, the
inviolable risk check, and the PM's Buy/Sell/Hold. No network, no LLM. This is the
same pipeline `mv-paper --agents` runs per bar; the **Agent Room** UI screen
renders it from the journal.

---

## 8. How the agents improve the strategies

```bash
uv run python scripts/run_postmortem.py
```

This is the learning engine, run offline and deterministically over a recorded
session:

1. **Attribution (FR-P1)** — every closed trade's net P&L is decomposed into
   signal / timing / sizing / slippage / fees / regime (the components **sum to
   net** by construction).
2. **Mistake taxonomy (FR-P2)** — losers are classified (false-signal, late-entry,
   oversizing, regime-misread, …) and rolled up by frequency and cost.
3. **Counterfactual replay (FR-P3)** — re-runs the recorded bars with one variable
   changed (e.g. half size) and reports the delta — the cost of the actual choice.
4. **Governed meta-learning (FR-P5)** — proposes new strategy weights from
   out-of-sample Sharpe under a Bayesian prior, an anti-whipsaw velocity cap, a
   regime-eligibility gate, and **held-out validation**.

Crucially this is **propose-only**: a weight proposal is written to the
improvement ledger with before/after held-out metrics; **it never auto-applies to
the loop and never touches risk limits.** You (the Operator) adopt it or not. That
governance — slow, validated, human-gated — is the platform's most important
guardrail against naive P&L-chasing. The **Post-Mortem Room** UI screen shows
attribution, the mistake trends, and the improvement ledger.

---

## 9. Check P&L — every surface

- **Terminal:** `mv-paper` prints realized P&L + approximate equity per run;
  `mv-serve` prints the same on startup.
- **API:** `GET /api/v1/portfolio` (equity / day P&L / drawdown / peak) and
  `GET /api/v1/positions` once `mv-serve` is up.
- **UI:** the **Command Deck** (equity, day P&L, drawdown gauge, positions table).
- **Attribution:** `scripts/run_postmortem.py` / `GET /api/v1/trades/{id}/attribution`
  for the *why* behind the P&L (which component drove each trade).
- **Journal:** `GET /api/v1/journal` or the **Journal Explorer** screen — the
  full hash-chained record every number is derived from.

---

## 10. Arbitrage monitor (optional)

```bash
uv run python scripts/run_arbitrage.py
```

Cross-exchange / funding / triangular crypto opportunities shown **after** fees +
slippage + transfer cost, each tagged Red/Amber/Green for executability — gross
spreads are never presented as edge. Cross-border is monitor-only (always Red).
Surfaces on the **Arbitrage** UI screen and `GET /api/v1/arbitrage`.

---

## 11. The kill-switch (always reachable)

```bash
uv run mv-kill "reason for halt"           # trip the inviolable halt
```

Or from the Command Deck (Operator token). Tripping it makes the risk engine
reject every order immediately. It is terminal and **only the Operator can
re-enable it** (`POST /api/v1/risk/reset` with the token) — no agent and no
autonomy setting can. The kill-switch state is shared (Redis) across the loop, the
CLI, and the API.

---

## 12. Command reference

| Command | Does | Keys |
|---|---|---|
| `uv run mv-paper [--agents] [--symbol …] [--timeframe …]` | one real-time crypto paper session → decisions/fills/P&L | none |
| `uv run mv-serve [--agents] [--port …]` | paper session **+ serve the Command Deck API** | `MV_OPERATOR_TOKEN` |
| `npm run dev` (in `packages/mv-ui`) | the Command Deck UI | — |
| `uv run mv-kill "reason"` | trip the inviolable kill-switch | none |
| `uv run python scripts/run_gate.py [--slug … | --limit …]` | backtest / validation gate → active/observe/failed | `FRED_API_KEY` (4 strategies) |
| `uv run python scripts/run_agents.py` | agent-pipeline transcript (glass box) | none |
| `uv run python scripts/run_postmortem.py` | attribution + governed, propose-only improvement | none |
| `uv run python scripts/run_arbitrage.py` | after-cost arbitrage monitor (R/A/G) | none |
| `uv run mv-migrate` | apply Postgres migrations | DB env |
| `uv run mv-smoke` | live CCXT→ClickHouse data-pipe smoke | none |

---

## 13. Going live (gated) — and the hard stops

Live trading is **gated, staged, and manual**. The platform builds and tests all
the machinery; it does **not** flip itself to real money:

1. A strategy must **graduate**: ≥ 3 months sustained honest paper, OOS Sharpe
   ≥ 1.0, max drawdown ≤ 10%, ≥ 100 paper trades, projection-honesty within
   tolerance — and initial live capital **capped at ≤ 1% of equity**.
2. The **§13 compliance checklist** (SEBI-algo, LRS/FEMA, withdrawal-disabled
   keys, tax) must be all-clear — it *blocks* graduation otherwise.
3. **You** sign off per strategy via the Operator-authed, journaled
   `POST /api/v1/strategies/{slug}/graduate`. **Meta-learning can never
   auto-promote.** The same risk engine and kill-switch gate live orders; live
   keys must be funded, scoped, **withdrawal-disabled**, IP-allowlisted.

**Non-negotiable:** the agent never places a real-money order, and nothing in this
runbook automates real-money go-live. That step is yours, with funded keys, after
the gate and your sign-off.

---

## 14. Troubleshooting

- **`mv-paper` warns "Redis unavailable"** → harmless; it falls back to an
  in-process kill-switch and runs. Start Docker (`docker compose up -d`) only if
  you want the shared kill-switch + persistence.
- **`mv-serve` exits "set MV_OPERATOR_TOKEN"** → export the token first (§5).
- **UI shows empty / network error** → confirm `mv-serve` is up on the port and
  `NEXT_PUBLIC_API_URL` matches it; CORS allows `MV_UI_ORIGIN` (default
  `http://localhost:3000`).
- **A backtest strategy stays `observe`** → it's synthetic-data or missing
  `FRED_API_KEY`; that's the honest gate, not a bug.
- **An India fallback errors on auth** → the broker token expired; refresh it in
  `.env`. The governor falls through the ladder regardless (Dhan is primary).
- **Governor can't reach an exchange** → it fails over automatically and logs the
  source actually used (`via ccxt:kraken`, etc.).
