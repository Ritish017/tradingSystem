"use client";
import { useState } from "react";
import { TradingViewChart } from "@/components/TradingViewChart";
import { MarketDepth } from "@/components/MarketDepth";
import { LiveQuoteBar } from "@/components/LiveQuoteBar";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "1d"];

export default function MarketPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [exchange, setExchange] = useState("NSE");
  const [tf, setTf] = useState("5m");

  return (
    <div className="space-y-4">
      <LiveQuoteBar />
      <div className="flex flex-wrap items-center gap-3">
        <input
          className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 uppercase w-36"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          placeholder="Symbol"
        />
        <select
          className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-200"
          value={exchange}
          onChange={(e) => setExchange(e.target.value)}
        >
          {["NSE", "BSE", "NFO", "MCX"].map((x) => <option key={x}>{x}</option>)}
        </select>
        <div className="flex gap-1">
          {TIMEFRAMES.map((t) => (
            <button
              key={t}
              onClick={() => setTf(t)}
              className={`rounded px-2.5 py-1 text-xs ${tf === t ? "bg-amber-500/20 text-amber-400 border border-amber-500/40" : "bg-slate-800 text-slate-400 border border-slate-700"}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <TradingViewChart symbol={symbol} exchange={exchange} timeframe={tf} height={450} />

      <div className="grid gap-4 md:grid-cols-2">
        <MarketDepth symbol={symbol} exchange={exchange} />
        <div className="rounded border border-slate-700 bg-slate-900 p-3">
          <h3 className="mb-3 text-sm font-medium text-slate-300">Quick Quote — {symbol}</h3>
          <QuoteDetails symbol={symbol} exchange={exchange} />
        </div>
      </div>
    </div>
  );
}

function QuoteDetails({ symbol, exchange }: { symbol: string; exchange: string }) {
  const [quote, setQuote] = useState<Record<string, number> | null>(null);

  useState(() => {
    const load = async () => {
      try {
        const r = await fetch(`/api/v1/market/quote?symbol=${symbol}&exchange=${exchange}`);
        setQuote(await r.json());
      } catch {}
    };
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  });

  if (!quote) return <p className="text-slate-500 text-sm">Loading…</p>;

  const fields = [
    ["LTP", quote.ltp], ["Open", quote.open], ["High", quote.high],
    ["Low", quote.low], ["Close", quote.close], ["Volume", quote.volume],
    ["OI", quote.oi], ["Upper Circuit", quote.upper_circuit], ["Lower Circuit", quote.lower_circuit],
  ];

  return (
    <div className="grid grid-cols-3 gap-2 text-xs font-mono">
      {fields.map(([label, val]) => (
        <div key={String(label)}>
          <div className="text-slate-500">{label}</div>
          <div className="text-slate-200">{val != null ? Number(val).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}</div>
        </div>
      ))}
    </div>
  );
}
