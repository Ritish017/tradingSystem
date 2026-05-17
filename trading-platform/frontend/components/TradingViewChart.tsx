"use client";
import { useEffect, useRef, useState } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  UTCTimestamp,
} from "lightweight-charts";
import { apiBaseUrl } from "@/lib/api";

type Props = {
  symbol: string;
  exchange?: string;
  timeframe?: string;
  height?: number;
};

function toUTCTimestamp(ts: string): UTCTimestamp {
  return (new Date(ts).getTime() / 1000) as UTCTimestamp;
}

export function TradingViewChart({ symbol, exchange = "NSE", timeframe = "5m", height = 400 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [error, setError] = useState<string | null>(null);

  // init chart
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      height,
      layout: { background: { color: "#0f172a" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { borderColor: "#334155", timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;
    candleSeriesRef.current = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [height]);

  // load candles when symbol/tf changes
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    setError(null);

    fetch(`${apiBaseUrl}/api/v1/market/candles?symbol=${symbol}&exchange=${exchange}&timeframe=${timeframe}&limit=500`)
      .then((r) => r.json())
      .then((data: Array<{ ts: string; open: number; high: number; low: number; close: number }>) => {
        if (!Array.isArray(data)) throw new Error("bad response");
        const bars: CandlestickData[] = data
          .map((c) => ({
            time: toUTCTimestamp(c.ts),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
          .sort((a, b) => (a.time as number) - (b.time as number));
        candleSeriesRef.current!.setData(bars);
        chartRef.current?.timeScale().fitContent();
      })
      .catch((e) => setError(String(e)));
  }, [symbol, exchange, timeframe]);

  return (
    <div className="rounded border border-slate-700 bg-slate-900 p-2">
      <div className="mb-2 flex items-center gap-3 text-sm">
        <span className="font-semibold text-slate-200">{symbol}</span>
        <span className="text-slate-500">{exchange}</span>
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-amber-400">{timeframe}</span>
        {error && <span className="text-rose-400 text-xs">{error}</span>}
      </div>
      <div ref={containerRef} style={{ width: "100%" }} />
    </div>
  );
}
