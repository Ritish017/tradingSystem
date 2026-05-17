export default function ExecutionPage() {
  const orders = [
    { id: "ORD-001", symbol: "NIFTY25JUNFUT", side: "BUY", qty: 50, filled: 50, price: 24850, status: "filled", strategy: "supertrend_rsi", slippage: 0.8 },
    { id: "ORD-002", symbol: "GOLDM25JUNFUT", side: "BUY", qty: 1, filled: 1, price: 73480, status: "filled", strategy: "commodity_momentum", slippage: 1.2 },
    { id: "ORD-003", symbol: "BTCUSDT", side: "SELL", qty: 0.01, filled: 0.01, price: 65400, status: "filled", strategy: "crypto_trend", slippage: 0.3 },
    { id: "ORD-004", symbol: "RELIANCE", side: "BUY", qty: 10, filled: 0, price: 2940, status: "pending", strategy: "ml_alpha", slippage: 0 },
  ];

  const statusColor: Record<string, string> = {
    filled: "text-emerald-400",
    pending: "text-yellow-400",
    rejected: "text-red-400",
    cancelled: "text-slate-500",
  };

  const metrics = [
    { label: "Orders Today", value: "24" },
    { label: "Fill Rate", value: "96.2%" },
    { label: "Avg Slippage", value: "0.9 bps" },
    { label: "Rejected", value: "1" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Execution Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {metrics.map(({ label, value }) => (
          <div key={label} className="bg-slate-900 rounded-xl p-4 border border-slate-800">
            <p className="text-xs text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-bold text-slate-100">{value}</p>
          </div>
        ))}
      </div>

      <section className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Order Blotter</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-slate-800">
                <th className="text-left px-5 py-3">Order ID</th>
                <th className="text-left px-4 py-3">Symbol</th>
                <th className="text-left px-4 py-3">Side</th>
                <th className="text-right px-4 py-3">Qty / Filled</th>
                <th className="text-right px-4 py-3">Price</th>
                <th className="text-right px-4 py-3">Slippage (bps)</th>
                <th className="text-left px-4 py-3">Strategy</th>
                <th className="text-right px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="px-5 py-3 font-mono text-xs text-slate-500">{o.id}</td>
                  <td className="px-4 py-3 font-medium text-slate-100">{o.symbol}</td>
                  <td className={`px-4 py-3 font-medium ${o.side === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                    {o.side}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-300">
                    {o.filled}/{o.qty}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-amber-400">
                    {o.price.toLocaleString("en-IN")}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-400">{o.slippage}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{o.strategy}</td>
                  <td className={`px-5 py-3 text-right font-medium ${statusColor[o.status]}`}>
                    {o.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
