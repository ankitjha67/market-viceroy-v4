import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// lightweight-charts needs a real canvas (absent in jsdom) — mock it.
const setData = vi.fn();
const addAreaSeries = vi.fn(() => ({ setData }));
const fitContent = vi.fn();
const applyOptions = vi.fn();
const remove = vi.fn();
vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "solid" },
  createChart: vi.fn(() => ({
    addAreaSeries,
    applyOptions,
    timeScale: () => ({ fitContent }),
    remove,
  })),
}));

import { EquityChart } from "@/components/EquityChart";

afterEach(cleanup);

describe("EquityChart", () => {
  it("renders the chart container and pushes the points", () => {
    const points = [
      { ts: "2026-01-01T00:00:00Z", equity: "5000", day_pnl: "0", decisions: 1, fills: 0, open_positions: 0 },
      { ts: "2026-01-01T00:01:00Z", equity: "5010", day_pnl: "10", decisions: 2, fills: 1, open_positions: 1 },
    ];
    render(<EquityChart points={points} />);
    expect(screen.getByRole("img", { name: "Equity curve" })).toBeInTheDocument();
    expect(addAreaSeries).toHaveBeenCalled();
    expect(setData).toHaveBeenCalled();
  });
});
