import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// lightweight-charts needs canvas (jsdom has none) — mock the series API used.
const setData = vi.fn();
const setMarkers = vi.fn();
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData, setMarkers, applyOptions: vi.fn() });
  return {
    ColorType: { Solid: "solid" },
    createChart: vi.fn(() => ({
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

import { PriceChart } from "@/components/PriceChart";

describe("PriceChart", () => {
  it("renders the chart container and pushes candles + markers", () => {
    render(
      <PriceChart
        data={{
          bars: [
            { time: 1704067200, open: 100, high: 101, low: 99, close: 100.5, volume: 10 },
            { time: 1704070800, open: 100.5, high: 102, low: 100, close: 101.5, volume: 12 },
          ],
          markers: [{ time: 1704070800, side: "BUY", price: "101.5" }],
        }}
      />,
    );
    expect(screen.getByRole("img", { name: "Price chart" })).toBeInTheDocument();
    expect(setData).toHaveBeenCalled(); // candles/volume/EMA pushed
    expect(setMarkers).toHaveBeenCalled(); // BUY/SELL markers placed
  });
});
