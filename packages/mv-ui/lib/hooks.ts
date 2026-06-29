"use client";

import useSWR from "swr";
import { ENDPOINTS, getJson } from "./api";
import type {
  AgentPipeline,
  AgentRecord,
  ArbOpportunity,
  CategoryStat,
  DecisionRow,
  Health,
  HistoryPoint,
  Improvement,
  NewsData,
  OhlcvData,
  Portfolio,
  Position,
  SourceHealthRow,
  Strategy,
  TradeRow,
} from "./types";
import type { LoadState } from "@/components/StatePanel";

const POLL_MS = 2000;

export interface Polled<T> {
  data: T | undefined;
  state: LoadState;
  error: unknown;
}

function toState<T>(data: T | undefined, error: unknown, isEmpty: (d: T) => boolean): LoadState {
  if (error) return "error";
  if (data === undefined) return "loading";
  return isEmpty(data) ? "empty" : "loaded";
}

function usePolled<T>(
  key: string | null,
  isEmpty: (d: T) => boolean,
): Polled<T> {
  const { data, error } = useSWR<T>(key, getJson, { refreshInterval: POLL_MS });
  return { data, state: toState(data, error, isEmpty), error };
}

const never = () => false;

export const useHealth = (): Polled<Health> => usePolled<Health>(ENDPOINTS.health, never);

export const usePortfolio = (): Polled<Portfolio> =>
  usePolled<Portfolio>(ENDPOINTS.portfolio, never);

export const useHistory = (): Polled<HistoryPoint[]> =>
  usePolled<HistoryPoint[]>(ENDPOINTS.portfolioHistory, (d) => d.length === 0);

export const useOhlcv = (): Polled<OhlcvData> =>
  usePolled<OhlcvData>(ENDPOINTS.ohlcv, (d) => d.bars.length === 0);

export const useMetrics = (): Polled<Record<string, string>> =>
  usePolled<Record<string, string>>(ENDPOINTS.metrics, (d) => Object.keys(d).length === 0);

export const useTrades = (): Polled<TradeRow[]> =>
  usePolled<TradeRow[]>(ENDPOINTS.trades, (d) => d.length === 0);

export const useNews = (): Polled<NewsData> =>
  usePolled<NewsData>(ENDPOINTS.news, (d) => d.headlines.length === 0);

export const usePositions = (): Polled<Position[]> =>
  usePolled<Position[]>(ENDPOINTS.positions, (d) => d.length === 0);

export const useDecisions = (): Polled<DecisionRow[]> =>
  usePolled<DecisionRow[]>(ENDPOINTS.decisions, (d) => d.length === 0);

export const useSourceHealth = (): Polled<SourceHealthRow[]> =>
  usePolled<SourceHealthRow[]>(ENDPOINTS.sourceHealth, (d) => d.length === 0);

export const useAgentPipeline = (snapshot: string | null): Polled<AgentPipeline> =>
  usePolled<AgentPipeline>(
    snapshot ? ENDPOINTS.agents(encodeURIComponent(snapshot)) : null,
    (d) => d.pipeline.length === 0,
  );

export const useStrategies = (): Polled<Strategy[]> =>
  usePolled<Strategy[]>(ENDPOINTS.strategies, (d) => d.length === 0);

export const useArbitrage = (): Polled<ArbOpportunity[]> =>
  usePolled<ArbOpportunity[]>(ENDPOINTS.arbitrage, (d) => d.length === 0);

export const useMistakes = (): Polled<Record<string, CategoryStat>> =>
  usePolled<Record<string, CategoryStat>>(ENDPOINTS.mistakes, (d) => Object.keys(d).length === 0);

export const useImprovements = (): Polled<Improvement[]> =>
  usePolled<Improvement[]>(ENDPOINTS.improvements, (d) => d.length === 0);

export const useRiskLimits = (): Polled<Record<string, string>> =>
  usePolled<Record<string, string>>(ENDPOINTS.riskLimits, (d) => Object.keys(d).length === 0);

export const useSettings = (): Polled<Record<string, unknown>> =>
  usePolled<Record<string, unknown>>(ENDPOINTS.settings, (d) => Object.keys(d).length === 0);

export const useJournal = (kind: string, q: string): Polled<AgentRecord[]> => {
  const params = new URLSearchParams();
  if (kind) params.set("kind", kind);
  if (q) params.set("q", q);
  const suffix = params.toString();
  return usePolled<AgentRecord[]>(
    `${ENDPOINTS.journal}${suffix ? `?${suffix}` : ""}`,
    (d) => d.length === 0,
  );
};
