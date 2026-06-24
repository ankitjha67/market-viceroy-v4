"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  type AreaData,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { HistoryPoint } from "@/lib/types";
import styles from "./EquityChart.module.css";

/** The live equity curve, fed by the continuous loop's per-tick history. The
 * chart only initializes in the browser (a useEffect); SSR renders the bare
 * container. lightweight-charts is mocked in tests (jsdom has no canvas). */
export function EquityChart({ points }: { points: HistoryPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      height: 240,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#5a564e",
        attributionLogo: false,
      },
      grid: { horzLines: { color: "#e7e2d8" }, vertLines: { visible: false } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      handleScale: false,
      handleScroll: false,
    });
    const series = chart.addAreaSeries({
      lineColor: "#7a2d1f",
      topColor: "rgba(122, 45, 31, 0.18)",
      bottomColor: "rgba(122, 45, 31, 0.02)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const resize = () => chart.applyOptions({ width: el.clientWidth });
    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const seen = new Set<number>();
    const data: AreaData[] = [];
    for (const point of points) {
      const time = Math.floor(new Date(point.ts).getTime() / 1000);
      const value = Number(point.equity);
      if (!Number.isFinite(time) || !Number.isFinite(value) || seen.has(time)) continue;
      seen.add(time);
      data.push({ time: time as UTCTimestamp, value });
    }
    series.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [points]);

  return <div ref={containerRef} className={styles.chart} role="img" aria-label="Equity curve" />;
}
