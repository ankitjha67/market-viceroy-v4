/** Typed fetch wrappers over the mv-api REST surface.
 *
 * The base URL comes from NEXT_PUBLIC_API_URL (default localhost:8000). Mutating
 * calls (kill / reset) carry the Operator token header — the only writes the UI
 * makes; everything else is read-only. The token is never stored in code. */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!resp.ok) {
    throw new ApiError(resp.status, `${path} -> ${resp.status}`);
  }
  return (await resp.json()) as T;
}

async function postOperator(path: string, token: string): Promise<void> {
  const resp = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "X-Operator-Token": token },
  });
  if (!resp.ok) {
    throw new ApiError(resp.status, `${path} -> ${resp.status}`);
  }
}

/** Trip the inviolable kill-switch (Operator-authed, journaled server-side). */
export function killSwitch(token: string, reason: string): Promise<void> {
  return postOperator(`/api/v1/risk/kill?reason=${encodeURIComponent(reason)}`, token);
}

/** Operator-only re-enable after a kill (BR-004). */
export function resetKillSwitch(token: string, operatorId: string): Promise<void> {
  return postOperator(`/api/v1/risk/reset?operator_id=${encodeURIComponent(operatorId)}`, token);
}

export const ENDPOINTS = {
  health: "/api/v1/health",
  portfolio: "/api/v1/portfolio",
  portfolioHistory: "/api/v1/portfolio/history",
  ohlcv: "/api/v1/ohlcv",
  metrics: "/api/v1/metrics",
  trades: "/api/v1/trades",
  news: "/api/v1/news",
  positions: "/api/v1/positions",
  decisions: "/api/v1/decisions",
  sourceHealth: "/api/v1/health/sources",
  agents: (snapshot: string) => `/api/v1/decisions/${snapshot}/agents`,
  strategies: "/api/v1/strategies",
  arbitrage: "/api/v1/arbitrage",
  mistakes: "/api/v1/postmortem/mistakes",
  improvements: "/api/v1/postmortem/improvements",
  riskLimits: "/api/v1/risk/limits",
  settings: "/api/v1/settings",
  journal: "/api/v1/journal",
} as const;
