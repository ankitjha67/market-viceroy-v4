/** Response types mirroring the mv-api endpoints (PRD §7). Money arrives as
 * strings (Decimal on the backend) and is formatted, never re-computed as float. */

export interface Health {
  status: string;
  kill_switch_tripped: boolean;
  journal_length: number;
}

export interface Portfolio {
  equity: string;
  day_pnl: string;
  drawdown: string;
  peak_equity: string;
}

export interface Position {
  instrument: string;
  size: string;
  entry: string;
  mark: string;
  pnl: string;
}

export interface DecisionRow {
  seq: number;
  ts: string;
  payload: {
    action?: "BUY" | "SELL" | "HOLD";
    instrument?: string;
    conviction?: number;
    rationale?: string;
    snapshot_id?: string;
    [key: string]: unknown;
  };
}

export interface AgentRecord {
  seq: number;
  kind: string;
  ts: string;
  payload: Record<string, unknown>;
}

export interface AgentPipeline {
  snapshot_id: string;
  pipeline: AgentRecord[];
}

export type SourceStatus = "green" | "amber" | "red";

export interface SourceHealthRow {
  source: string;
  domain: string;
  status: SourceStatus;
  quota_burn_pct: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  last_failover: string | null;
  reconcile_flag: boolean;
}
