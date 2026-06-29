import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Polled } from "@/lib/hooks";

vi.mock("@/lib/hooks", () => ({
  useHealth: vi.fn(),
  usePortfolio: vi.fn(),
  useHistory: vi.fn(),
  useOhlcv: vi.fn(),
  usePositions: vi.fn(),
  useDecisions: vi.fn(),
  useSourceHealth: vi.fn(),
  useStrategies: vi.fn(),
  useRiskLimits: vi.fn(),
  useMistakes: vi.fn(),
  useImprovements: vi.fn(),
  useSettings: vi.fn(),
}));

// EquityChart + PriceChart pull in lightweight-charts (needs canvas) — mock it.
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), setMarkers: vi.fn(), applyOptions: vi.fn() });
  return {
    ColorType: { Solid: "solid" },
    createChart: vi.fn(() => ({
      addAreaSeries: series,
      addCandlestickSeries: series,
      addHistogramSeries: series,
      addLineSeries: series,
      priceScale: () => ({ applyOptions: vi.fn() }),
      applyOptions: vi.fn(),
      timeScale: () => ({ fitContent: vi.fn() }),
      remove: vi.fn(),
    })),
  };
});

import * as hooks from "@/lib/hooks";
import { LiveDashboard } from "@/components/LiveDashboard";

function polled<T>(state: Polled<T>["state"], data?: T): Polled<T> {
  return { state, data, error: state === "error" ? new Error("x") : undefined };
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function setup(over: Partial<Record<string, Polled<unknown>>> = {}) {
  vi.mocked(hooks.useHealth).mockReturnValue(
    (over.useHealth ?? polled("loaded", { kill_switch_tripped: false })) as any,
  );
  vi.mocked(hooks.usePortfolio).mockReturnValue(
    (over.usePortfolio ??
      polled("loaded", { equity: "5000", day_pnl: "12", drawdown: "0.04", peak_equity: "5012" })) as any,
  );
  vi.mocked(hooks.useHistory).mockReturnValue(
    (over.useHistory ??
      polled("loaded", [
        { ts: "2026-01-01T00:00:00Z", equity: "5000", day_pnl: "0", decisions: 1, fills: 0, open_positions: 0 },
      ])) as any,
  );
  vi.mocked(hooks.useOhlcv).mockReturnValue(
    (over.useOhlcv ??
      polled("loaded", {
        bars: [
          { time: 1704067200, open: 100, high: 101, low: 99, close: 100.5, volume: 10 },
          { time: 1704070800, open: 100.5, high: 102, low: 100, close: 101.5, volume: 12 },
        ],
        markers: [{ time: 1704070800, side: "BUY", price: "101.5" }],
      })) as any,
  );
  vi.mocked(hooks.usePositions).mockReturnValue(
    (over.usePositions ??
      polled("loaded", [
        { instrument: "BTC/USDT", size: "0.0001", entry: "5300000", mark: "5310000", pnl: "1" },
      ])) as any,
  );
  vi.mocked(hooks.useDecisions).mockReturnValue(
    (over.useDecisions ??
      polled("loaded", [
        {
          seq: 1,
          ts: "2026-01-01T00:00:00Z",
          payload: { action: "BUY", instrument: "BTC/USDT", rationale: "trend up", snapshot_id: "snap-1" },
        },
      ])) as any,
  );
  vi.mocked(hooks.useSourceHealth).mockReturnValue(
    (over.useSourceHealth ??
      polled("loaded", [
        {
          source: "ccxt:binance",
          domain: "crypto.prices",
          status: "green",
          quota_burn_pct: 12,
          latency_p50_ms: 40,
          latency_p95_ms: 90,
          last_failover: null,
          reconcile_flag: false,
        },
      ])) as any,
  );
  vi.mocked(hooks.useStrategies).mockReturnValue(
    (over.useStrategies ??
      polled("loaded", [
        { slug: "ema_cross_12_26", family: "trend", gate_status: "active", data_source: "ccxt" },
      ])) as any,
  );
  vi.mocked(hooks.useRiskLimits).mockReturnValue(
    (over.useRiskLimits ?? polled("loaded", { max_position_pct: "0.2", daily_loss_pct: "0.03" })) as any,
  );
  vi.mocked(hooks.useMistakes).mockReturnValue(
    (over.useMistakes ?? polled("loaded", { false_signal: { count: 2, cost: "10" } })) as any,
  );
  vi.mocked(hooks.useImprovements).mockReturnValue(
    (over.useImprovements ??
      polled("loaded", [
        {
          change_kind: "strategy_weight",
          change_desc: "nudge",
          mistake_category: "false_signal",
          before_metric: 0.1,
          after_metric: 0.2,
          adopted: false,
        },
      ])) as any,
  );
  vi.mocked(hooks.useSettings).mockReturnValue(
    (over.useSettings ??
      polled("loaded", {
        mode: "paper",
        decision_engine: "ensemble",
        symbol: "BTC/USDT",
        timeframe: "1m",
        fx_usd_inr: "83",
      })) as any,
  );
}

afterEach(cleanup);

describe("LiveDashboard", () => {
  it("renders the loaded dashboard in INR with the equity curve", () => {
    setup();
    render(<LiveDashboard />);
    expect(screen.getByRole("heading", { name: "Command Deck" })).toBeInTheDocument();
    expect(screen.getByText(/5,000/)).toBeInTheDocument(); // ₹5,000 equity (en-IN)
    expect(screen.getByRole("img", { name: "Equity curve" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Price chart" })).toBeInTheDocument();
    expect(screen.getAllByText("BTC/USDT").length).toBeGreaterThan(0);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("ccxt:binance")).toBeInTheDocument();
    expect(screen.getByText("ema_cross_12_26")).toBeInTheDocument();
  });

  it("shows the empty positions message", () => {
    setup({ usePositions: polled("empty", []) });
    render(<LiveDashboard />);
    expect(screen.getByText(/No positions/)).toBeInTheDocument();
  });

  it("surfaces the live market regime when adaptive weighting is on", () => {
    setup({
      useSettings: polled("loaded", {
        mode: "paper",
        decision_engine: "ensemble",
        symbol: "BTC/USDT",
        timeframe: "1m",
        fx_usd_inr: "83",
        weighting: "regime-adaptive",
        regime: { label: "trending", trend_score: "0.78", trend_weight: "0.72", meanrev_weight: "0.28" },
      }),
    });
    render(<LiveDashboard />);
    expect(screen.getAllByText(/trending/i).length).toBeGreaterThan(0); // strip chip + Models tile
    expect(screen.getByText(/72%/)).toBeInTheDocument(); // live trend weighting
  });

  it("shows a degraded banner on a portfolio error", () => {
    setup({ usePortfolio: polled("error") });
    render(<LiveDashboard />);
    expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
  });

  it("shows a loading skeleton while the equity history loads", () => {
    setup({ useHistory: polled("loading") });
    render(<LiveDashboard />);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });
});
