import { getRisk } from "@/lib/api";
import { KillSwitch } from "@/components/charts/kill-switch";

export default async function RiskPage() {
  const risk = await getRisk().catch(() => null);
  
  const maxDailyLoss = risk ? risk.capital * 0.02 : 0;
  const dailyLossUsage = risk ? Math.abs(Math.min(risk.daily_realized_pnl, 0)) / maxDailyLoss * 100 : 0;
  const exposureUsage = risk ? (risk.gross_exposure / risk.capital) * 100 : 0;
  const foMarginUsage = risk ? risk.fo_margin_utilisation * 100 : 0;
  
  return (
    <main className="mx-auto max-w-6xl p-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-semibold">Risk Management & Limits</h1>
        <KillSwitch />
      </div>

      {risk && risk.halted && (
        <div className="rounded border-2 border-red-500 bg-red-500/20 p-6">
          <h2 className="text-2xl font-bold text-red-400 mb-2">⚠️ TRADING HALTED</h2>
          <p className="text-lg">Reason: {risk.halted_reason || "Unknown"}</p>
          <p className="text-sm text-slate-300 mt-2">All new orders are blocked. Review the issue before resuming.</p>
        </div>
      )}

      <section>
        <h2 className="text-xl font-semibold mb-4">Current Risk Metrics</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="text-sm text-slate-400 mb-1">Daily Realized PnL</div>
            <div className={`text-3xl font-bold ${
              risk && risk.daily_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {risk ? `₹${risk.daily_realized_pnl.toFixed(2)}` : "-"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Max daily loss limit: ₹{maxDailyLoss.toFixed(2)}
            </div>
          </div>
          
          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="text-sm text-slate-400 mb-1">Capital</div>
            <div className="text-3xl font-bold">
              {risk ? `₹${risk.capital.toFixed(2)}` : "-"}
            </div>
          </div>
          
          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="text-sm text-slate-400 mb-1">Gross Exposure</div>
            <div className="text-3xl font-bold">
              {risk ? `₹${risk.gross_exposure.toFixed(2)}` : "-"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              {exposureUsage.toFixed(1)}% of capital
            </div>
          </div>
          
          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="text-sm text-slate-400 mb-1">F&O Margin Utilization</div>
            <div className="text-3xl font-bold">
              {risk ? `${foMarginUsage.toFixed(1)}%` : "-"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Max allowed: 60%
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4">Risk Limits & Usage</h2>
        <div className="space-y-4">
          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="flex justify-between mb-2">
              <span className="font-medium">Daily Loss Limit (2% of capital)</span>
              <span className={dailyLossUsage > 80 ? 'text-red-400 font-bold' : 'text-slate-300'}>
                {dailyLossUsage.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-3">
              <div 
                className={`h-3 rounded-full transition-all ${
                  dailyLossUsage > 80 ? 'bg-red-500' : dailyLossUsage > 50 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${Math.min(dailyLossUsage, 100)}%` }}
              />
            </div>
          </div>

          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="flex justify-between mb-2">
              <span className="font-medium">Gross Exposure (Max 100%)</span>
              <span className={exposureUsage > 80 ? 'text-red-400 font-bold' : 'text-slate-300'}>
                {exposureUsage.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-3">
              <div 
                className={`h-3 rounded-full transition-all ${
                  exposureUsage > 80 ? 'bg-red-500' : exposureUsage > 50 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${Math.min(exposureUsage, 100)}%` }}
              />
            </div>
          </div>

          <div className="rounded border border-slate-700 p-4 bg-slate-800/50">
            <div className="flex justify-between mb-2">
              <span className="font-medium">F&O Margin Utilization (Max 60%)</span>
              <span className={foMarginUsage > 50 ? 'text-red-400 font-bold' : 'text-slate-300'}>
                {foMarginUsage.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-3">
              <div 
                className={`h-3 rounded-full transition-all ${
                  foMarginUsage > 50 ? 'bg-red-500' : foMarginUsage > 30 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${Math.min(foMarginUsage / 0.6 * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>
      </section>

      <section className="rounded border border-slate-700 p-4 bg-slate-800/50">
        <h2 className="text-xl font-semibold mb-4">Hard Risk Rules</h2>
        <ul className="space-y-2 text-sm">
          <li className="flex items-start">
            <span className="text-green-400 mr-2">✓</span>
            <span>Max daily loss: 2% of capital → automatic halt</span>
          </li>
          <li className="flex items-start">
            <span className="text-green-400 mr-2">✓</span>
            <span>Max position concentration: 20% per instrument</span>
          </li>
          <li className="flex items-start">
            <span className="text-green-400 mr-2">✓</span>
            <span>Max gross exposure: 100% (no leverage in paper mode)</span>
          </li>
          <li className="flex items-start">
            <span className="text-green-400 mr-2">✓</span>
            <span>Max F&O margin: 60% of available margin</span>
          </li>
          <li className="flex items-start">
            <span className="text-green-400 mr-2">✓</span>
            <span>Circuit breaker: 3 consecutive losses → strategy goes to review status</span>
          </li>
        </ul>
      </section>
    </main>
  );
}

