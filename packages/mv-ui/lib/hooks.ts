"use client";

import useSWR from "swr";
import { ENDPOINTS, getJson } from "./api";
import type {
  AgentPipeline,
  DecisionRow,
  Health,
  Portfolio,
  Position,
  SourceHealthRow,
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
