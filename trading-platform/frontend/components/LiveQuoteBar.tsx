"use client";
import { useEffect, useRef } from "react";
import { useMarketStore } from "@/store/marketSlice";
import { connectLiveWs } from "@/lib/ws";

const INDICES = ["NIFTY 50", "NIFTY BANK", "INDIA VIX"];

export function LiveQuoteBar() {
  const { ticks, watchlist, setTick } = useMarketStore();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const symbols = [...watchlist, ...INDICES].join(",");
    const ws = connectLiveWs(`/api/v1/ws/ticks?symbols=${encodeURIComponent(symbols)}`);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.symbol && data.price !== undefined) {
          setTick({ symbol: data.symbol, price: Number(data.price), ts: data.ts ?? new Date().toISOString() });
        }
      } catch {}
    };

    ws.onerror = () => ws.close();

    return () => ws.close();
  }, [watchlist, setTick]);

  const symbols = watchlist.slice(0, 8);

  return (
    <div className="flex items-center gap-0 overflow-x-auto border-b border-slate-800 bg-slate-900 text-xs">
      {symbols.map((sym) => {
        const tick = ticks[sym];
        return (
          <div
            key={sym}
            className="flex shrink-0 items-center gap-2 border-r border-slate-800 px-4 py-2"
          >
            <span className="font-medium text-slate-300">{sym}</span>
            {tick ? (
              <span className="font-mono text-emerald-400">
                ₹{tick.price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            ) : (
              <span className="text-slate-600">—</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
