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

## Exchange-key policy (enforced before any live trading — Phase 7)

- **Scoped** to trading only; **withdrawals DISABLED** on the key.
- **IP-allowlisted** to the deployment host.
- Stored in the vault, injected as env at runtime; rotated on any suspected
  compromise. Withdrawal-disabled keys bound the blast radius of a leak.
