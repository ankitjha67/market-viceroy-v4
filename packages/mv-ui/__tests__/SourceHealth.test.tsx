import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SourceHealth } from "@/components/SourceHealth";
import type { Polled } from "@/lib/hooks";
import type { SourceHealthRow } from "@/lib/types";

vi.mock("@/lib/hooks", () => ({ useSourceHealth: vi.fn() }));
import * as hooks from "@/lib/hooks";

function polled(state: Polled<SourceHealthRow[]>["state"], data?: SourceHealthRow[]): Polled<SourceHealthRow[]> {
  return { state, data, error: state === "error" ? new Error("x") : undefined };
}

const ROW: SourceHealthRow = {
  source: "ccxt:binance",
  domain: "crypto.prices",
  status: "green",
  quota_burn_pct: 18,
  latency_p50_ms: 42,
  latency_p95_ms: 110,
  last_failover: null,
  reconcile_flag: false,
};

afterEach(cleanup);

describe("SourceHealth", () => {
  it("renders source cards with metrics", () => {
    vi.mocked(hooks.useSourceHealth).mockReturnValue(polled("loaded", [ROW]));
    render(<SourceHealth />);
    expect(screen.getByText("ccxt:binance")).toBeInTheDocument();
    expect(screen.getByText("42 ms")).toBeInTheDocument();
    expect(screen.getByText(/No cross-source discrepancies/)).toBeInTheDocument();
  });

  it("flags reconciliation discrepancies", () => {
    vi.mocked(hooks.useSourceHealth).mockReturnValue(
      polled("loaded", [{ ...ROW, status: "red", reconcile_flag: true }]),
    );
    render(<SourceHealth />);
    expect(screen.queryByText(/No cross-source discrepancies/)).not.toBeInTheDocument();
    // The domain shows on the card and again in the reconciliation strip.
    expect(screen.getAllByText(/crypto\.prices/).length).toBeGreaterThanOrEqual(2);
  });

  it("shows empty + error states", () => {
    vi.mocked(hooks.useSourceHealth).mockReturnValue(polled("empty", []));
    const { rerender } = render(<SourceHealth />);
    expect(screen.getByText(/No sources reporting/)).toBeInTheDocument();
    vi.mocked(hooks.useSourceHealth).mockReturnValue(polled("error"));
    rerender(<SourceHealth />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Degraded/);
  });
});
