import { getHealthz, getPnl, getPositions, getStrategies } from "@/lib/api";
import { KillSwitch } from "@/components/charts/kill-switch";

export default async function DashboardPage() {
  const [health, pnl, positions, strategies] = await Promise.all([
    getHealthz().catch(() => null),
    getPnl().catch(() => null),
    getPositions().catch(() => []),
    getStrategies().catch(() => [])
  ]);

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-8">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-semibold">Trading Platform Dashboard</h1>
        <KillSwitch />
      </div>

      <section className="rounded border border-amber-500/50 bg-amber-500/10 p-4">
        <h2 className="mb-2 text-xl font-medium">⚠️ Reality Check</h2>
        <ul className="list-disc space-y-1 pl-6 text-sm text-amber-100">
          <li>Most retail algo traders lose money; strategy edge determines survivability.</li>
          <li>Run at least 3 months of paper trading before risking real money.</li>
          <li>Do not scrape NSE/BSE HTML for live trading data; use broker APIs.</li>
          <li>Do not hard-code secrets. Use environment vars in dev, vault in prod.</li>
          <li>SEBI registration required for managing third-party funds.</li>
        </ul>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
          <h3 className="text-sm text-slate-400">Daily PnL</h3>
          <p className={`text-2xl font-semibold ${pnl?.daily && pnl.daily >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {pnl?.daily !== undefined ? `₹${pnl.daily.toFixed(2)}` : "-"}
          </p>
        </div>
        <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
          <h3 className="text-sm text-slate-400">Total PnL</h3>
          <p className={`text-2xl font-semibold ${pnl?.total && pnl.total >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {pnl?.total !== undefined ? `₹${pnl.total.toFixed(2)}` : "-"}
          </p>
        </div>
        <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
          <h3 className="text-sm text-slate-400">Open Positions</h3>
          <p className="text-2xl font-semibold">{positions.length}</p>
        </div>
        <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
          <h3 className="text-sm text-slate-400">Active Strategies</h3>
          <p className="text-2xl font-semibold">{strategies.filter((s: any) => s.status === 'paper' || s.status === 'live').length} / {strategies.length}</p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
          <h2 className="mb-4 text-xl font-medium">Recent Positions</h2>
          {positions.length > 0 ? (
            <div className="space-y-2">
              {positions.slice(0, 5).map((pos: any) => (
                <div key={pos.symbol} className="flex justify-between items-center p-2 rounded bg-slate-700/50">
                  <span className="font-medium">{pos.symbol}</span>
                  <span className={pos.quantity >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {pos.quantity > 0 ? 'LONG' : 'SHORT'} {Math.abs(pos.quantity)}
                  </span>
                  <span className="text-slate-400">@{pos.avg_price?.toFixed(2)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-sm">No open positions</p>
          )}
        </div>

        <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
          <h2 className="mb-4 text-xl font-medium">Strategy Health</h2>
          {strategies.length > 0 ? (
            <div className="space-y-2">
              {strategies.slice(0, 5).map((strat: any) => (
                <div key={strat.name} className="flex justify-between items-center p-2 rounded bg-slate-700/50">
                  <span className="font-medium">{strat.name}</span>
                  <span className={`px-2 py-1 rounded text-xs ${
                    strat.status === 'live' ? 'bg-green-600' :
                    strat.status === 'paper' ? 'bg-blue-600' :
                    'bg-yellow-600'
                  }`}>
                    {strat.status}
                  </span>
                  <span className="text-slate-400 text-sm">Weight: {(strat.current_weight * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-sm">No strategies registered</p>
          )}
        </div>
      </section>

      <section className="rounded border border-slate-700 p-4 bg-slate-800/50">
        <h2 className="mb-2 text-xl font-medium">System Health</h2>
        {health ? (
          <div className="space-y-2">
            <p>
              Overall:{" "}
              <span className={health.overall === "ok" ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                {health.overall.toUpperCase()}
              </span>
            </p>
            <div className="grid gap-2 md:grid-cols-3">
              {Object.entries(health.services).map(([name, service]: [string, any]) => (
                <div key={name} className="rounded border border-slate-700 p-3 text-sm bg-slate-700/30">
                  <div className="font-medium">{name}</div>
                  <div className={service.status === "ok" ? "text-emerald-400" : "text-rose-400"}>
                    {service.status}
                  </div>
                  {service.latency_ms && (
                    <div className="text-xs text-slate-400">{service.latency_ms}ms</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-rose-400">Unable to load health status.</p>
        )}
      </section>
    </main>
  );
}

