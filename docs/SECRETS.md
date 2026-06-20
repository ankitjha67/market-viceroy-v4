# Secrets & vault approach

**Non-negotiable (CLAUDE.md #6, PRD NFR §9):** secrets live in a vault, never
in code. Exchange API keys are scoped, **withdrawal-disabled**, and
IP-allowlisted. Mutating endpoints (kill-switch, limits, graduate) are
Operator-authed and journaled.

## Phase 0 — what is in place

- **No secret is committed.** `.gitignore` excludes `.env`, `.env.*`, `*.pem`,
  `*.key`, `secrets/`, `credentials.json`. The only tracked env file is
  `.env.example` (placeholders only).
- **Config is read from the environment**, not literals. Python config uses
  `pydantic-settings` (`mv.failover.smoke.config.SmokeSettings`) reading from
  `.env` / environment. `docker-compose.yml` reads the same `.env` and uses
  `${VAR:?error}` so it refuses to start if a required password is unset.
- **The Phase-0 smoke needs no API key** — it uses public CCXT market-data
  endpoints. So Phase 0 is secret-free beyond local DB passwords.

## Local development

```bash
cp .env.example .env       # fill in DB passwords; never commit .env
```

`.env` holds only local dev credentials for ClickHouse / Postgres / Redis.

## Path to a real vault (Phase 1+)

The pattern is "env var at runtime, sourced from a vault — never a literal in
code or a committed file." Concrete options, in order of preference for a
single-operator self-host:

1. **SOPS + age** — encrypt a `secrets.enc.yaml` committed to the repo;
   decrypt to env at deploy time with an age key held outside the repo. Simple,
   git-friendly, auditable.
2. **Docker secrets / Compose secrets** — mount secrets as files into
   containers rather than env where the platform supports it.
3. **HashiCorp Vault** — if/when the deployment grows beyond a single host;
   dynamic secrets + leasing.

CI uses the platform's encrypted secret store (GitHub Actions secrets); the
Phase-0 CI smoke job uses throwaway service-container credentials, not real
ones.

## Exchange / broker keys (read from env at call time, never in code)

Every market-data / broker adapter reads its key(s) from environment variables
inside the network-gated fetch, places them only into request headers, and never
logs or returns them. Missing-key errors carry a static message (no key value).
The full placeholder list is in `.env.example`. By region:

- **Crypto** — CCXT public OHLCV needs no key (`BINANCE_API_KEY`/secret only for
  trading).
- **US equities** — `FINNHUB_API_KEY` (primary), `ALPACA_API_KEY`/`ALPACA_API_SECRET`.
- **FX** — Frankfurter is keyless.
- **India equities** — **Dhan primary** (`DHAN_ACCESS_TOKEN`/`DHAN_CLIENT_ID`),
  then Upstox (`UPSTOX_ACCESS_TOKEN`), Kotak (`KOTAK_ACCESS_TOKEN`/`KOTAK_CONSUMER_KEY`),
  Zerodha (`ZERODHA_API_KEY`/`ZERODHA_ACCESS_TOKEN` — Kite is **internal-use only,
  no redistribution**), Angel One (`ANGELONE_API_KEY`/`ANGELONE_ACCESS_TOKEN`).
- **Macro/other** — `FRED_API_KEY` (runtime input ONLY — never trained on),
  `EIA_API_KEY`, `POLYGON_API_KEY`. LLM: `ANTHROPIC_API_KEY` (optional, offline).

## Exchange-key policy (enforced before any live trading — Phase 7)

- **Scoped** to trading only; **withdrawals DISABLED** on the key.
- **IP-allowlisted** to the deployment host.
- Stored in the vault, injected as env at runtime; rotated on any suspected
  compromise. Withdrawal-disabled keys bound the blast radius of a leak.

## API / network posture (Phase 9 hardening)

- **Operator token** guards every mutating/expensive route (kill, reset,
  graduate, replay) and the `/ws/stream` WebSocket; compared **constant-time**
  (`hmac.compare_digest`). The app refuses to start with an empty token.
- **CORS** is an explicit, non-wildcard allow-list (`MV_UI_ORIGIN`, default the
  Next.js dev origin) — never `*`, since reads expose the trading posture.
- **Reads are open** for the single-operator UX but should be reached only over
  loopback (`127.0.0.1`) or behind an authenticating reverse proxy before any
  non-local exposure. All SQL is parameterized; the journal search filters
  in-memory with a clamped limit.
- The `/settings` endpoint returns an **allow-list of non-secret config** only —
  never the `Settings` model (which carries DB passwords). Keep it that way when
  wiring the provider.
