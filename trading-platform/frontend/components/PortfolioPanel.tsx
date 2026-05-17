"use client";
import { useEffect } from "react";
import { usePortfolioStore } from "@/store/portfolioSlice";
import { apiBaseUrl } from "@/lib/api";

function pnlColor(v: number) {
  return v >= 0 ? "text-emerald-400" : "text-rose-400";
}
function fmt(v: number, dec = 2) {
  return v.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export function PortfolioPanel() {
  const { holdings, positions, pnl, setHoldings, setPositions, setPnL, markUpdated } = usePortfolioStore();

  const refresh = async () => {
    try {
      const [h, p, pnlData] = await Promise.all([
        fetch(`${apiBaseUrl}/api/v1/portfolio/holdings`).then((r) => r.json()),
        fetch(`${apiBaseUrl}/api/v1/portfolio/positions`).then((r) => r.json()),
        fetch(`${apiBaseUrl}/api/v1/portfolio/pnl`).then((r) => r.json()),
      ]);
      setHoldings(h);
      setPositions(p);
      setPnL(pnlData);
      markUpdated();
    } catch {}
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-4">
      {/* PnL Summary */}
      {pnl && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: "Realized P&L", value: pnl.realized },
            { label: "Unrealized P&L", value: pnl.unrealized },
            { label: "Total P&L", value: pnl.total },
            { label: "Available Cash", value: pnl.available_cash },
          ].map(({ label, value }) => (
            <div key={label} className="rounded border border-slate-700 bg-slate-800/50 p-3">
              <p className="text-xs text-slate-400">{label}</p>
              <p className={`text-lg font-semibold ${pnlColor(value)}`}>₹{fmt(value)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Holdings */}
      {holdings.length > 0 && (
        <div className="rounded border border-slate-700">
          <div className="border-b border-slate-700 bg-slate-800/50 px-3 py-2 text-sm font-medium text-slate-300">
            Holdings ({holdings.length})
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2 text-right">Avg Price</th>
                  <th className="px-3 py-2 text-right">LTP</th>
                  <th className="px-3 py-2 text-right">Value</th>
                  <th className="px-3 py-2 text-right">P&L</th>
                  <th className="px-3 py-2 text-right">P&L %</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h) => (
                  <tr key={h.tradingsymbol} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                    <td className="px-3 py-2 font-medium text-slate-200">{h.tradingsymbol}</td>
                    <td className="px-3 py-2 text-right text-slate-300">{h.quantity}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-400">₹{fmt(h.averageprice)}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-200">₹{fmt(h.live_ltp ?? h.ltp)}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-300">₹{fmt(h.current_value ?? 0, 0)}</td>
                    <td className={`px-3 py-2 text-right font-mono font-semibold ${pnlColor(h.unrealized_pnl ?? 0)}`}>
                      ₹{fmt(h.unrealized_pnl ?? 0)}
                    </td>
                    <td className={`px-3 py-2 text-right ${pnlColor(h.pnl_pct ?? 0)}`}>
                      {fmt(h.pnl_pct ?? 0, 2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Intraday Positions */}
      {positions.length > 0 && (
        <div className="rounded border border-slate-700">
          <div className="border-b border-slate-700 bg-slate-800/50 px-3 py-2 text-sm font-medium text-slate-300">
            Positions ({positions.length})
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-right">Net Qty</th>
                  <th className="px-3 py-2 text-right">Avg Price</th>
                  <th className="px-3 py-2 text-right">LTP</th>
                  <th className="px-3 py-2 text-right">Unrealized</th>
                  <th className="px-3 py-2 text-right">Realized</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p, i) => (
                  <tr key={i} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                    <td className="px-3 py-2 font-medium text-slate-200">{p.tradingsymbol}</td>
                    <td className={`px-3 py-2 text-right font-mono font-semibold ${p.netqty >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {p.netqty > 0 ? "+" : ""}{p.netqty}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-slate-400">₹{fmt(p.averageprice)}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-200">₹{fmt(p.ltp)}</td>
                    <td className={`px-3 py-2 text-right font-mono font-semibold ${pnlColor(p.unrealisedprofitloss)}`}>
                      ₹{fmt(p.unrealisedprofitloss)}
                    </td>
                    <td className={`px-3 py-2 text-right font-mono ${pnlColor(p.realisedprofitloss)}`}>
                      ₹{fmt(p.realisedprofitloss)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {holdings.length === 0 && positions.length === 0 && (
        <p className="text-slate-500 text-sm">No holdings or positions. Angel One may not be connected.</p>
      )}
    </div>
  );
}
