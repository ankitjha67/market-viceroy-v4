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

/** One tick on the live equity curve (the continuous --watch loop appends these). */
export interface HistoryPoint {
  ts: string;
  equity: string;
  day_pnl: string;
  decisions: number;
  fills: number;
  open_positions: number;
}

export interface Position {
  instrument: string;
  size: string;
  entry: string;
  mark: string;
  pnl: string;
}

/** One candle on the price chart (epoch-second time, INR prices). */
export interface OhlcvBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** A BUY/SELL marker placed on the candle where an order filled. */
export interface ChartMarker {
  time: number;
  side: "BUY" | "SELL";
  price: string;
}

export interface OhlcvData {
  bars: OhlcvBar[];
  markers: ChartMarker[];
}

/** One scored news headline + the watchlist symbols it names. */
export interface NewsHeadline {
  title: string;
  score: number;
  ts: string;
  symbols: string[];
}

export interface NewsData {
  sentiment: Record<string, number>;
  headlines: NewsHeadline[];
}

/** One closed round trip on the trade blotter (money as strings). */
export interface TradeRow {
  id: string;
  instrument: string;
  side: "LONG" | "SHORT";
  qty: string;
  entry: string;
  exit: string;
  pnl: string;
  fees: string;
  return_pct: string;
  opened_at: string;
  closed_at: string;
  duration_s: string;
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

export interface Strategy {
  slug: string;
  family: string;
  gate_status: "active" | "observe" | "failed";
  data_source: string;
  live_status?: string;
  metrics?: Record<string, number>;
}

export type Executability = "green" | "amber" | "red";

export interface ArbOpportunity {
  kind: string;
  legs: string;
  gross_edge_bps: string;
  after_cost_edge_bps: string;
  executability: Executability;
  detail: string;
}

export interface CategoryStat {
  count: number;
  cost: string;
}

export interface Improvement {
  change_kind: string;
  change_desc: string;
  mistake_category: string | null;
  before_metric: number | null;
  after_metric: number | null;
  adopted: boolean;
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
