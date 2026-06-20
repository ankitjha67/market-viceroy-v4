import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Polled } from "@/lib/hooks";

vi.mock("@/lib/hooks", () => ({
  useStrategies: vi.fn(),
  useArbitrage: vi.fn(),
  useMistakes: vi.fn(),
  useImprovements: vi.fn(),
  useRiskLimits: vi.fn(),
  useSettings: vi.fn(),
  useJournal: vi.fn(),
  useHealth: vi.fn(),
}));
import * as hooks from "@/lib/hooks";
import { StrategyLab } from "@/components/StrategyLab";
import { ArbitrageMonitor } from "@/components/ArbitrageMonitor";
import { PostMortemRoom } from "@/components/PostMortemRoom";
import { RiskConsole } from "@/components/RiskConsole";
import { JournalExplorer } from "@/components/JournalExplorer";
import { Settings } from "@/components/Settings";

function p<T>(state: Polled<T>["state"], data?: T): Polled<T> {
  return { state, data, error: state === "error" ? new Error("x") : undefined };
}
const mock = (fn: unknown, value: unknown) =>
  (fn as { mockReturnValue: (v: unknown) => void }).mockReturnValue(value);

afterEach(cleanup);

describe("Strategy Lab", () => {
  it("renders the catalog with gate badges", () => {
    mock(hooks.useStrategies, p("loaded", [{ slug: "ema_cross", family: "trend", gate_status: "active", data_source: "real" }]));
    render(<StrategyLab />);
    expect(screen.getByText("ema_cross")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });
});

describe("Arbitrage Monitor", () => {
  it("renders opportunities with executability", () => {
    mock(hooks.useArbitrage, p("loaded", [{ kind: "cross_exchange", legs: "a->b", gross_edge_bps: "100", after_cost_edge_bps: "58", executability: "green", detail: "" }]));
    render(<ArbitrageMonitor />);
    expect(screen.getByText("cross_exchange")).toBeInTheDocument();
    expect(screen.getByText("green")).toBeInTheDocument();
  });

  it("shows an error banner", () => {
    mock(hooks.useArbitrage, p("error"));
    render(<ArbitrageMonitor />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Degraded/);
  });
});

describe("Post-Mortem Room", () => {
  it("renders mistakes + improvements", () => {
    mock(hooks.useMistakes, p("loaded", { false_signal: { count: 2, cost: "40" } }));
    mock(hooks.useImprovements, p("loaded", [{ change_kind: "strategy_weight", change_desc: "cut rsi", mistake_category: "false_signal", before_metric: 0.8, after_metric: 1.1, adopted: false }]));
    render(<PostMortemRoom />);
    expect(screen.getAllByText("false_signal").length).toBeGreaterThan(0);
    expect(screen.getByText(/cut rsi/)).toBeInTheDocument();
    expect(screen.getByText("proposed")).toBeInTheDocument();
  });
});

describe("Risk Console", () => {
  it("renders limits + kill state", () => {
    mock(hooks.useRiskLimits, p("loaded", { max_position_pct: "0.20" }));
    mock(hooks.useHealth, p("loaded", { kill_switch_tripped: true }));
    render(<RiskConsole />);
    expect(screen.getByText(/max position pct/)).toBeInTheDocument();
    expect(screen.getByText(/kill-switch tripped/)).toBeInTheDocument();
  });
});

describe("Journal Explorer", () => {
  it("renders entries and the filter toolbar", () => {
    mock(hooks.useJournal, p("loaded", [{ seq: 1, ts: "2026-01-01T00:00:00Z", kind: "decision", payload: { action: "BUY" } }]));
    render(<JournalExplorer />);
    expect(screen.getByLabelText("Filter by kind")).toBeInTheDocument();
    expect(screen.getAllByText("decision").length).toBeGreaterThan(0);
  });
});

describe("Settings", () => {
  it("renders read-only config", () => {
    mock(hooks.useSettings, p("loaded", { mode: "paper" }));
    render(<Settings />);
    expect(screen.getByText("mode")).toBeInTheDocument();
    expect(screen.getByText("paper")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    mock(hooks.useSettings, p("empty", {}));
    render(<Settings />);
    expect(screen.getByText(/No configuration/)).toBeInTheDocument();
  });
});
