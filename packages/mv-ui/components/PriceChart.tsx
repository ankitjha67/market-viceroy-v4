"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { OhlcvData } from "@/lib/types";
import { ema } from "@/lib/indicators";
import styles from "./PriceChart.module.css";

const UP = "#2ea043";
const DOWN = "#e5534b";

/**
 * The live price candles with the strategies' EMAs, a volume pane, and BUY/SELL
 * markers on the bars where orders filled — the "what the market did + where we
 * traded" view a real desk stares at. Browser-only (a useEffect; SSR renders the
 * bare container); lightweight-charts is mocked in tests (jsdom has no canvas).
 * Times render in the viewer's local zone (e.g. IST), not UTC.
 */
export function PriceChart({ data }: { data: OhlcvData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const fastRef = useRef<ISeriesApi<"Line"> | null>(null);
  const slowRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b949e",
        attributionLogo: false,
      },
      grid: { horzLines: { color: "#1c2230" }, vertLines: { color: "#161b24" } },
      rightPriceScale: { borderVisible: false },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (t: Time) =>
          new Date(Number(t) * 1000).toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23",
          }),
      },
      localization: {
        timeFormatter: (t: Time) =>
          new Date(Number(t) * 1000).toLocaleString(undefined, {
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23",
          }),
      },
      handleScale: false,
      handleScroll: false,
    });
    const candles = chart.addCandlestickSeries({
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
      priceLineVisible: false,
    });
    const volume = chart.addHistogramSeries({
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      color: "#3a4453",
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const fast = chart.addLineSeries({
      color: "#d9a441",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const slow = chart.addLineSeries({
      color: "#6ea8e0",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    candleRef.current = candles;
    volumeRef.current = volume;
    fastRef.current = fast;
    slowRef.current = slow;

    const resize = () => chart.applyOptions({ width: el.clientWidth });
    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const candles = candleRef.current;
    const volume = volumeRef.current;
    const fast = fastRef.current;
    const slow = slowRef.current;
    if (!candles || !volume || !fast || !slow) return;

    const bars = data.bars;
    candles.setData(
      bars.map(
        (b): CandlestickData => ({
          time: b.time as UTCTimestamp,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        }),
      ),
    );
    volume.setData(
      bars.map(
        (b): HistogramData => ({
          time: b.time as UTCTimestamp,
          value: b.volume,
          color: b.close >= b.open ? "rgba(46,160,67,0.42)" : "rgba(229,83,75,0.42)",
        }),
      ),
    );
    const closes = bars.map((b) => b.close);
    const line = (vals: (number | null)[]): LineData[] => {
      const out: LineData[] = [];
      bars.forEach((b, i) => {
        const v = vals[i];
        if (v != null) out.push({ time: b.time as UTCTimestamp, value: v });
      });
      return out;
    };
    fast.setData(line(ema(closes, 12)));
    slow.setData(line(ema(closes, 26)));

    const markers: SeriesMarker<Time>[] = data.markers
      .map((m) => ({
        time: m.time as UTCTimestamp,
        position: (m.side === "BUY" ? "belowBar" : "aboveBar") as SeriesMarker<Time>["position"],
        color: m.side === "BUY" ? UP : DOWN,
        shape: (m.side === "BUY" ? "arrowUp" : "arrowDown") as SeriesMarker<Time>["shape"],
        text: m.side,
      }))
      .sort((a, b) => Number(a.time) - Number(b.time)); // markers must be time-ascending
    candles.setMarkers(markers);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={containerRef} className={styles.chart} role="img" aria-label="Price chart" />;
}
