import { getMCX, type MCXContract } from "@/lib/api";

function changeColor(v: number) {
  return v >= 0 ? "text-emerald-400" : "text-red-400";
}

export default async function CommoditiesPage() {
  const mcxResult = await getMCX().catch(() => [] as MCXContract[]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Commodities</h1>

      <section className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">MCX Contracts</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-slate-800 bg-slate-900/50">
                <th className="text-left px-5 py-3">Symbol</th>
                <th className="text-right px-4 py-3">Price</th>
                <th className="text-right px-4 py-3">Change %</th>
                <th className="text-right px-4 py-3">Open Interest</th>
                <th className="text-right px-4 py-3">OI Change %</th>
                <th className="text-right px-4 py-3">Volume</th>
                <th className="text-right px-5 py-3">Expiry</th>
              </tr>
            </thead>
            <tbody>
              {mcxResult.map((c) => (
                <tr key={c.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="px-5 py-3 font-bold text-slate-100">{c.symbol}</td>
                  <td className="px-4 py-3 text-right font-mono text-amber-400">
                    ₹{c.price.toLocaleString("en-IN")}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${changeColor(c.change_pct)}`}>
                    {c.change_pct >= 0 ? "+" : ""}{c.change_pct.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-right text-slate-300">{c.open_interest.toLocaleString()}</td>
                  <td className={`px-4 py-3 text-right font-mono ${changeColor(c.oi_change_pct)}`}>
                    {c.oi_change_pct >= 0 ? "+" : ""}{c.oi_change_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">{c.volume.toLocaleString()}</td>
                  <td className="px-5 py-3 text-right text-slate-500 text-xs">{c.expiry}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
