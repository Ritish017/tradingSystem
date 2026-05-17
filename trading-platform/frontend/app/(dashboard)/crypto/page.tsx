export default function CryptoPage() {
  const prices = [
    { symbol: "BTC/USDT", price: "65,420", change: "+1.24%", positive: true, funding: "0.012%", oi: "18.2B" },
    { symbol: "ETH/USDT", price: "3,180", change: "-0.45%", positive: false, funding: "0.008%", oi: "8.4B" },
    { symbol: "SOL/USDT", price: "172.4", change: "+2.10%", positive: true, funding: "0.021%", oi: "2.1B" },
    { symbol: "BNB/USDT", price: "598.2", change: "+0.32%", positive: true, funding: "0.005%", oi: "0.9B" },
  ];

  const metrics = [
    { label: "Fear & Greed Index", value: "62", note: "Greed", color: "text-yellow-400" },
    { label: "BTC Dominance", value: "52.4%", note: "Stable", color: "text-slate-300" },
    { label: "Total Market Cap", value: "$2.41T", note: "+1.1% 24h", color: "text-emerald-400" },
    { label: "24h Liquidations", value: "$142M", note: "Longs: $89M", color: "text-yellow-400" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Crypto Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {metrics.map(({ label, value, note, color }) => (
          <div key={label} className="bg-slate-900 rounded-xl p-4 border border-slate-800">
            <p className="text-xs text-slate-500 mb-1">{label}</p>
            <p className={`text-xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-slate-600 mt-1">{note}</p>
          </div>
        ))}
      </div>

      <section className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Perpetual Futures</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-500 text-xs border-b border-slate-800">
              <th className="text-left px-5 py-3">Symbol</th>
              <th className="text-right px-4 py-3">Price (USDT)</th>
              <th className="text-right px-4 py-3">24h Change</th>
              <th className="text-right px-4 py-3">Funding Rate</th>
              <th className="text-right px-5 py-3">Open Interest</th>
            </tr>
          </thead>
          <tbody>
            {prices.map((p) => (
              <tr key={p.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                <td className="px-5 py-3 font-bold text-slate-100">{p.symbol}</td>
                <td className="px-4 py-3 text-right font-mono text-amber-400">${p.price}</td>
                <td className={`px-4 py-3 text-right font-mono ${p.positive ? "text-emerald-400" : "text-red-400"}`}>
                  {p.change}
                </td>
                <td className="px-4 py-3 text-right font-mono text-slate-400">{p.funding}</td>
                <td className="px-5 py-3 text-right text-slate-400">{p.oi}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
