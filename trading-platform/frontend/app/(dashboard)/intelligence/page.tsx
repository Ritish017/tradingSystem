import { getRegime, getCrossMarket, getAgents, type CorrelationPair } from "@/lib/api";

const REGIME_COLOR: Record<string, string> = {
  trending_up: "text-emerald-400",
  trending_down: "text-red-400",
  mean_reverting: "text-yellow-400",
  crash: "text-red-600",
  low_liquidity: "text-slate-400",
};

const VOL_COLOR: Record<string, string> = {
  low: "text-emerald-400",
  normal: "text-slate-300",
  high: "text-yellow-400",
  extreme: "text-red-500",
};

function corrColor(v: number) {
  if (v > 0.6) return "text-emerald-400";
  if (v > 0.3) return "text-yellow-400";
  if (v < -0.6) return "text-red-400";
  if (v < -0.3) return "text-orange-400";
  return "text-slate-400";
}

export default async function IntelligencePage() {
  const [regime, correlations, agents] = await Promise.allSettled([
    getRegime(),
    getCrossMarket(),
    getAgents(),
  ]);

  const r = regime.status === "fulfilled" ? regime.value : null;
  const corrs: CorrelationPair[] = correlations.status === "fulfilled" ? correlations.value : [];
  const agentList = agents.status === "fulfilled" ? agents.value : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">AI Intelligence</h1>

      <section className="bg-slate-900 rounded-xl p-5 border border-slate-800">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Market Regime</h2>
        {r ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-slate-500">Regime</p>
              <p className={`text-lg font-bold ${REGIME_COLOR[r.regime] ?? "text-slate-300"}`}>
                {r.regime.replace(/_/g, " ").toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Probability</p>
              <p className="text-lg font-bold text-slate-100">{(r.probability * 100).toFixed(0)}%</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Volatility</p>
              <p className={`text-lg font-bold ${VOL_COLOR[r.volatility_regime] ?? "text-slate-300"}`}>
                {r.volatility_regime.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">India VIX / VIX</p>
              <p className="text-lg font-bold text-slate-100">{r.india_vix} / {r.vix}</p>
            </div>
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Regime data unavailable — backend may be offline</p>
        )}
      </section>

      <section className="bg-slate-900 rounded-xl p-5 border border-slate-800">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Cross-Market Correlations</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-slate-800">
                <th className="text-left py-2 pr-4">Asset A</th>
                <th className="text-left py-2 pr-4">Asset B</th>
                <th className="text-right py-2 pr-4">Pearson</th>
                <th className="text-right py-2 pr-4">Spearman</th>
                <th className="text-right py-2">Window</th>
              </tr>
            </thead>
            <tbody>
              {corrs.map((c, i) => (
                <tr key={i} className="border-b border-slate-800/50">
                  <td className="py-2 pr-4 font-medium">{c.asset_a}</td>
                  <td className="py-2 pr-4 text-slate-400">{c.asset_b}</td>
                  <td className={`py-2 pr-4 text-right font-mono ${corrColor(c.pearson)}`}>{c.pearson.toFixed(3)}</td>
                  <td className={`py-2 pr-4 text-right font-mono ${corrColor(c.spearman)}`}>{c.spearman.toFixed(3)}</td>
                  <td className="py-2 text-right text-slate-500">{c.window_days}d</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-slate-900 rounded-xl p-5 border border-slate-800">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Active Agents ({agentList.length})
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {agentList.map((a) => (
            <div key={a.name} className="bg-slate-800 rounded-lg p-3">
              <p className="text-xs text-slate-500">{a.type}</p>
              <p className="text-sm font-medium text-slate-100">{a.name.replace(/_/g, " ")}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
