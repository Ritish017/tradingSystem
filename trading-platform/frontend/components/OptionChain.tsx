"use client";
import { useEffect } from "react";
import { useOptionsStore, OptionStrike } from "@/store/optionsSlice";
import { apiBaseUrl } from "@/lib/api";

function fmt(v: number | undefined | null, dec = 2) {
  if (v == null || isNaN(Number(v))) return "—";
  return Number(v).toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function OIBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="relative h-full w-full">
      <div className={`absolute inset-y-0 ${color === "green" ? "right-0 bg-emerald-900/50" : "left-0 bg-rose-900/50"}`}
        style={{ width: `${pct}%` }} />
    </div>
  );
}

export function OptionChain() {
  const { symbol, expiry, expiries, chain, pcr, maxPain, spot, loading, error,
    setSymbol, setExpiry, setChainData, setExpiries, setLoading, setError } = useOptionsStore();

  // load expiries when symbol changes
  useEffect(() => {
    if (!symbol) return;
    fetch(`${apiBaseUrl}/api/v1/options/expiries?symbol=${symbol}`)
      .then((r) => r.json())
      .then((data: string[]) => {
        setExpiries(data);
        if (data.length > 0 && !expiry) setExpiry(data[0]);
      })
      .catch(() => {});
  }, [symbol]);

  // load chain when symbol/expiry changes
  useEffect(() => {
    if (!symbol || !expiry) return;
    setLoading(true);
    setError(null);
    fetch(`${apiBaseUrl}/api/v1/options/chain?symbol=${symbol}&expiry=${expiry}`)
      .then((r) => r.json())
      .then((data) => {
        setChainData({
          spot: data.spot ?? 0,
          chain: data.chain ?? [],
          pcr: data.pcr ?? null,
          maxPain: data.max_pain ?? null,
        });
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [symbol, expiry]);

  const maxCallOI = Math.max(...chain.map((r) => r.CE?.openInterest ?? 0), 1);
  const maxPutOI = Math.max(...chain.map((r) => r.PE?.openInterest ?? 0), 1);
  const atm = chain.reduce((best, row) =>
    Math.abs(row.strikePrice - spot) < Math.abs(best.strikePrice - spot) ? row : best,
    chain[0] ?? { strikePrice: 0 }
  );

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-slate-200 border border-slate-700"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
        >
          {["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-slate-200 border border-slate-700"
          value={expiry}
          onChange={(e) => setExpiry(e.target.value)}
        >
          {expiries.map((e) => <option key={e}>{e}</option>)}
        </select>
        <span className="text-sm text-slate-400">Spot: <strong className="text-amber-400">₹{fmt(spot)}</strong></span>
        {pcr && (
          <span className={`text-xs rounded px-2 py-1 ${pcr.sentiment === "bullish" ? "bg-emerald-900 text-emerald-300" : pcr.sentiment === "bearish" ? "bg-rose-900 text-rose-300" : "bg-slate-800 text-slate-300"}`}>
            PCR OI: {pcr.pcr_oi.toFixed(2)} ({pcr.sentiment})
          </span>
        )}
        {maxPain && (
          <span className="text-xs text-slate-400">
            Max Pain: <strong className="text-amber-400">₹{fmt(maxPain.max_pain_strike, 0)}</strong>
          </span>
        )}
        {loading && <span className="text-xs text-slate-500">Loading…</span>}
        {error && <span className="text-xs text-rose-400">{error}</span>}
      </div>

      {/* Chain table */}
      <div className="overflow-x-auto rounded border border-slate-700">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-800 text-slate-400">
              <th className="px-2 py-1.5 text-right">OI</th>
              <th className="px-2 py-1.5 text-right">IV%</th>
              <th className="px-2 py-1.5 text-right">Delta</th>
              <th className="px-2 py-1.5 text-right">LTP</th>
              <th className="px-2 py-1.5 text-center bg-slate-700 text-amber-400 font-bold">STRIKE</th>
              <th className="px-2 py-1.5 text-left">LTP</th>
              <th className="px-2 py-1.5 text-left">Delta</th>
              <th className="px-2 py-1.5 text-left">IV%</th>
              <th className="px-2 py-1.5 text-left">OI</th>
            </tr>
          </thead>
          <tbody>
            {chain.map((row: OptionStrike) => {
              const isATM = row.strikePrice === atm?.strikePrice;
              const isMaxPain = row.strikePrice === maxPain?.max_pain_strike;
              return (
                <tr
                  key={row.strikePrice}
                  className={`border-b border-slate-800 font-mono ${isATM ? "bg-amber-950/30" : "hover:bg-slate-800/40"} ${isMaxPain ? "ring-1 ring-inset ring-amber-500/30" : ""}`}
                >
                  {/* CALL side */}
                  <td className="relative px-2 py-1 text-right">
                    <div className="absolute inset-0 flex items-center justify-end">
                      <OIBar value={row.CE?.openInterest ?? 0} max={maxCallOI} color="green" />
                    </div>
                    <span className="relative text-emerald-400">{((row.CE?.openInterest ?? 0) / 1000).toFixed(0)}K</span>
                  </td>
                  <td className="px-2 py-1 text-right text-slate-300">{fmt(row.CE?.iv, 1)}</td>
                  <td className="px-2 py-1 text-right text-slate-400">{fmt(row.CE?.delta, 3)}</td>
                  <td className="px-2 py-1 text-right font-semibold text-emerald-300">{fmt(row.CE?.ltp)}</td>

                  {/* Strike */}
                  <td className={`px-3 py-1 text-center font-bold bg-slate-800 ${isATM ? "text-amber-400" : "text-slate-200"}`}>
                    {row.strikePrice}
                    {isMaxPain && <span className="ml-1 text-xs text-amber-500">⚡</span>}
                  </td>

                  {/* PUT side */}
                  <td className="px-2 py-1 text-left font-semibold text-rose-300">{fmt(row.PE?.ltp)}</td>
                  <td className="px-2 py-1 text-left text-slate-400">{fmt(row.PE?.delta, 3)}</td>
                  <td className="px-2 py-1 text-left text-slate-300">{fmt(row.PE?.iv, 1)}</td>
                  <td className="relative px-2 py-1 text-left">
                    <div className="absolute inset-0 flex items-center">
                      <OIBar value={row.PE?.openInterest ?? 0} max={maxPutOI} color="red" />
                    </div>
                    <span className="relative text-rose-400">{((row.PE?.openInterest ?? 0) / 1000).toFixed(0)}K</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
