"use client";
import { useEffect, useState } from "react";
import { apiBaseUrl } from "@/lib/api";

type FuturesRow = {
  symbol: string;
  token: string;
  exchange: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  oi: number;
  volume: number;
};

const FUTURES_WATCHLIST = [
  { symbol: "NIFTY25JULFUT", token: "58662", exchange: "NFO" },
  { symbol: "BANKNIFTY25JULFUT", token: "53732", exchange: "NFO" },
  { symbol: "RELIANCE25JULFUT", token: "46109", exchange: "NFO" },
];

export function FuturesDashboard() {
  const [rows, setRows] = useState<FuturesRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const results = await Promise.allSettled(
        FUTURES_WATCHLIST.map((f) =>
          fetch(`${apiBaseUrl}/api/v1/market/quote?symbol=${f.symbol}&exchange=${f.exchange}&token=${f.token}`)
            .then((r) => r.json())
            .then((d) => ({ ...d, symbol: f.symbol, token: f.token, exchange: f.exchange } as FuturesRow))
        )
      );
      const valid: FuturesRow[] = results
        .filter((r): r is PromiseFulfilledResult<FuturesRow> => r.status === "fulfilled")
        .map((r) => r.value);
      setRows(valid);
      setLoading(false);
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const pct = (ltp: number, close: number) => close > 0 ? ((ltp - close) / close) * 100 : 0;

  return (
    <div className="rounded border border-slate-700 bg-slate-900">
      <div className="border-b border-slate-700 px-4 py-2">
        <h2 className="text-sm font-semibold text-slate-300">Futures Dashboard</h2>
      </div>
      {loading ? (
        <p className="p-4 text-sm text-slate-500">Loading futures quotes…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-500">
                <th className="px-3 py-2 text-left">Contract</th>
                <th className="px-3 py-2 text-right">LTP</th>
                <th className="px-3 py-2 text-right">Change%</th>
                <th className="px-3 py-2 text-right">Open</th>
                <th className="px-3 py-2 text-right">High</th>
                <th className="px-3 py-2 text-right">Low</th>
                <th className="px-3 py-2 text-right">OI (K)</th>
                <th className="px-3 py-2 text-right">Volume (K)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const chg = pct(r.ltp, r.close);
                return (
                  <tr key={r.symbol} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                    <td className="px-3 py-2 font-medium text-slate-200">{r.symbol}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-100">
                      ₹{r.ltp?.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </td>
                    <td className={`px-3 py-2 text-right font-semibold ${chg >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {chg >= 0 ? "+" : ""}{chg.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-slate-400">{r.open?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right font-mono text-emerald-400/80">{r.high?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right font-mono text-rose-400/80">{r.low?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-400">{((r.oi ?? 0) / 1000).toFixed(0)}</td>
                    <td className="px-3 py-2 text-right text-slate-400">{((r.volume ?? 0) / 1000).toFixed(0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
