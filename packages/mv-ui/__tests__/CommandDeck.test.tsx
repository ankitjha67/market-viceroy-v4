import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CommandDeck } from "@/components/CommandDeck";
import type { Polled } from "@/lib/hooks";

vi.mock("@/lib/hooks", () => ({
  useHealth: vi.fn(),
  usePortfolio: vi.fn(),
  usePositions: vi.fn(),
  useDecisions: vi.fn(),
  useSourceHealth: vi.fn(),
}));

import * as hooks from "@/lib/hooks";

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
      polled("loaded", { equity: "1000000", day_pnl: "1250", drawdown: "0.04", peak_equity: "1010000" })) as any,
  );
  vi.mocked(hooks.usePositions).mockReturnValue(
    (over.usePositions ??
      polled("loaded", [{ instrument: "BTC/USDT", size: "0.5", entry: "60000", mark: "61000", pnl: "500" }])) as any,
  );
  vi.mocked(hooks.useDecisions).mockReturnValue(
    (over.useDecisions ??
      polled("loaded", [
        { seq: 1, ts: "2026-01-01T00:00:00Z", payload: { action: "BUY", instrument: "BTC/USDT", rationale: "trend up", snapshot_id: "snap-1" } },
      ])) as any,
  );
  vi.mocked(hooks.useSourceHealth).mockReturnValue(
    (over.useSourceHealth ??
      polled("loaded", [{ source: "ccxt:binance", domain: "crypto.prices", status: "green", quota_burn_pct: 12, latency_p50_ms: 40, latency_p95_ms: 90, last_failover: null, reconcile_flag: false }])) as any,
  );
}

afterEach(cleanup);

describe("CommandDeck", () => {
  it("renders the loaded deck", () => {
    setup();
    render(<CommandDeck />);
    expect(screen.getByRole("heading", { name: "Command Deck" })).toBeInTheDocument();
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument();
    expect(screen.getAllByText("BTC/USDT").length).toBeGreaterThan(0);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("ccxt:binance")).toBeInTheDocument();
  });

  it("shows the empty positions message", () => {
    setup({ usePositions: polled("empty", []) });
    render(<CommandDeck />);
    expect(screen.getByText(/No positions/)).toBeInTheDocument();
  });

  it("shows a degraded banner on a portfolio error", () => {
    setup({ usePortfolio: polled("error") });
    render(<CommandDeck />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Degraded/);
  });

  it("shows a loading skeleton", () => {
    setup({ useDecisions: polled("loading") });
    render(<CommandDeck />);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });
});
