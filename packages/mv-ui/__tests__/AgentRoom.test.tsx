import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AgentRoom } from "@/components/AgentRoom";
import type { Polled } from "@/lib/hooks";

const searchParams = { get: vi.fn() };
vi.mock("next/navigation", () => ({ useSearchParams: () => searchParams }));
vi.mock("@/lib/hooks", () => ({ useAgentPipeline: vi.fn(), useDecisions: vi.fn() }));

import * as hooks from "@/lib/hooks";

function polled<T>(state: Polled<T>["state"], data?: T): Polled<T> {
  return { state, data, error: state === "error" ? new Error("x") : undefined };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AgentRoom", () => {
  it("lists decisions when no snapshot is selected", () => {
    searchParams.get.mockReturnValue(null);
    vi.mocked(hooks.useDecisions).mockReturnValue(
      polled("loaded", [
        { seq: 1, ts: "t", payload: { action: "BUY", instrument: "BTC/USDT", snapshot_id: "snap-1", rationale: "r" } },
      ]) as ReturnType<typeof hooks.useDecisions>,
    );
    vi.mocked(hooks.useAgentPipeline).mockReturnValue(polled("loading") as ReturnType<typeof hooks.useAgentPipeline>);
    render(<AgentRoom />);
    expect(screen.getByText(/Select a decision/)).toBeInTheDocument();
    expect(screen.getByText("BTC/USDT")).toBeInTheDocument();
  });

  it("renders the pipeline flow with expandable nodes for a snapshot", () => {
    searchParams.get.mockReturnValue("snap-1");
    vi.mocked(hooks.useDecisions).mockReturnValue(polled("loaded", []) as ReturnType<typeof hooks.useDecisions>);
    vi.mocked(hooks.useAgentPipeline).mockReturnValue(
      polled("loaded", {
        snapshot_id: "snap-1",
        pipeline: [
          { seq: 1, kind: "analyst_view", ts: "t", payload: { agent: "technical_analyst", stance: "bullish", score: 0.6 } },
          { seq: 2, kind: "risk_assessment", ts: "t", payload: { agent: "risk_manager", approved: false, breached_limits: ["kill_switch"] } },
          { seq: 3, kind: "decision", ts: "t", payload: { agent: "portfolio_manager", action: "HOLD", conviction: 0.2 } },
        ],
      }) as ReturnType<typeof hooks.useAgentPipeline>,
    );
    render(<AgentRoom />);
    expect(screen.getByText("technical_analyst")).toBeInTheDocument();
    expect(screen.getByText(/VETO/)).toBeInTheDocument();
    // Expanding a node reveals its raw journaled payload.
    fireEvent.click(screen.getByText("technical_analyst"));
    expect(screen.getByText("stance")).toBeInTheDocument();
  });

  it("shows an error banner when the pipeline fails", () => {
    searchParams.get.mockReturnValue("snap-1");
    vi.mocked(hooks.useDecisions).mockReturnValue(polled("loaded", []) as ReturnType<typeof hooks.useDecisions>);
    vi.mocked(hooks.useAgentPipeline).mockReturnValue(polled("error") as ReturnType<typeof hooks.useAgentPipeline>);
    render(<AgentRoom />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Degraded/);
  });
});
