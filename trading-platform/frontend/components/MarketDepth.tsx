"use client";
import { useEffect, useState } from "react";
import { apiBaseUrl } from "@/lib/api";

type DepthLevel = { price: number; quantity: number; orders: number };
type DepthData = { buy: DepthLevel[]; sell: DepthLevel[] };

type Props = { symbol: string; exchange?: string; token?: string };

export function MarketDepth({ symbol, exchange = "NSE", token }: Props) {
  const [depth, setDepth] = useState<DepthData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ symbol, exchange });
        if (token) params.set("token", token);
        const r = await fetch(`${apiBaseUrl}/api/v1/market/depth?${params}`);
        const data = await r.json();
        if (!cancelled) setDepth(data);
      } catch {}
      if (!cancelled) setLoading(false);
    };
    load();
    const id = setInterval(load, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, [symbol, exchange, token]);

  const maxQty = Math.max(
    ...(depth?.buy ?? []).map((l) => l.quantity),
    ...(depth?.sell ?? []).map((l) => l.quantity),
    1,
  );

  return (
    <div className="rounded border border-slate-700 bg-slate-900 p-3 text-xs font-mono">
      <h3 className="mb-2 text-sm font-semibold text-slate-300">Market Depth — {symbol}</h3>
      {loading && !depth && <p className="text-slate-500">Loading…</p>}
      {depth && (
        <div className="grid grid-cols-2 gap-2">
          {/* Bids */}
          <div>
            <div className="mb-1 grid grid-cols-3 text-slate-500">
              <span>Orders</span><span className="text-center">Qty</span><span className="text-right">Bid</span>
            </div>
            {(depth.buy ?? []).slice(0, 5).map((l, i) => (
              <div key={i} className="relative grid grid-cols-3 py-0.5">
                <div
                  className="absolute inset-y-0 right-0 bg-emerald-900/30"
                  style={{ width: `${(l.quantity / maxQty) * 100}%` }}
                />
                <span className="relative text-slate-400">{l.orders}</span>
                <span className="relative text-center text-slate-300">{l.quantity.toLocaleString()}</span>
                <span className="relative text-right text-emerald-400">{l.price.toFixed(2)}</span>
              </div>
            ))}
          </div>
          {/* Asks */}
          <div>
            <div className="mb-1 grid grid-cols-3 text-slate-500">
              <span>Ask</span><span className="text-center">Qty</span><span className="text-right">Orders</span>
            </div>
            {(depth.sell ?? []).slice(0, 5).map((l, i) => (
              <div key={i} className="relative grid grid-cols-3 py-0.5">
                <div
                  className="absolute inset-y-0 left-0 bg-rose-900/30"
                  style={{ width: `${(l.quantity / maxQty) * 100}%` }}
                />
                <span className="relative text-rose-400">{l.price.toFixed(2)}</span>
                <span className="relative text-center text-slate-300">{l.quantity.toLocaleString()}</span>
                <span className="relative text-right text-slate-400">{l.orders}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
