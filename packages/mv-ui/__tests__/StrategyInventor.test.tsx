import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Polled } from "@/lib/hooks";

vi.mock("@/lib/hooks", () => ({ useCandidates: vi.fn() }));
vi.mock("@/lib/api", () => ({ adoptCandidate: vi.fn() }));

import * as hooks from "@/lib/hooks";
import { StrategyInventor } from "@/components/StrategyInventor";

function polled<T>(state: Polled<T>["state"], data?: T): Polled<T> {
  return { state, data, error: undefined };
}

/* eslint-disable @typescript-eslint/no-explicit-any */
describe("Strategy Inventor", () => {
  it("renders graded candidates with the tested/survived summary + an Adopt button", () => {
    vi.mocked(hooks.useCandidates).mockReturnValue(
      polled("loaded", [
        {
          name: "ema_cross(fast=8,slow=21)",
          strategy: "ema_cross",
          family: "trend",
          provenance: "param_search",
          status: "active",
          adoptable: true,
          reasons: ["cleared all gate stages on real-feed data"],
          metrics: { deflated_sharpe: 1.2, oos_sharpe: 1.5 },
        },
        {
          name: "rsi_reversion(period=2)",
          strategy: "rsi_reversion",
          family: "meanrev",
          provenance: "genetic",
          status: "observe",
          adoptable: false,
          reasons: ["deflated Sharpe 0.30 < 0.95"],
          metrics: { deflated_sharpe: 0.3 },
        },
      ]) as any,
    );
    render(<StrategyInventor />);
    expect(screen.getByRole("heading", { name: "Strategy Inventor" })).toBeInTheDocument();
    expect(screen.getByText(/2 tested, 1 survived/)).toBeInTheDocument();
    expect(screen.getByText("ema_cross(fast=8,slow=21)")).toBeInTheDocument();
    expect(screen.getAllByText("Adopt")).toHaveLength(1); // only the adoptable candidate
  });

  it("shows the empty state before the first run", () => {
    vi.mocked(hooks.useCandidates).mockReturnValue(polled("empty", []) as any);
    render(<StrategyInventor />);
    expect(screen.getByText(/No inventor run yet/)).toBeInTheDocument();
  });
});
