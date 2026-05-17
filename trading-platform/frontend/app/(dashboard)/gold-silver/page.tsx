import { getGoldSilver, getMCX, type GoldSilverSnapshot, type MCXContract } from "@/lib/api";

function sentimentBadge(s: string) {
  if (s === "bullish") return "bg-emerald-500/20 text-emerald-400";
  if (s === "bearish") return "bg-red-500/20 text-red-400";
  return "bg-slate-700 text-slate-400";
}

function changeColor(v: number) {
  return v >= 0 ? "text-emerald-400" : "text-red-400";
}

function ScoreBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-300">{pct}%</span>
      </div>
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-amber-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default async function GoldSilverPage() {
  const [gsResult, mcxResult] = await Promise.allSettled([getGoldSilver(), getMCX()]);

  const gs: GoldSilverSnapshot | null = gsResult.status === "fulfilled" ? gsResult.value : null;
  const mcx: MCXContract[] = mcxResult.status === "fulfilled" ? mcxResult.value : [];
  const metals = mcx.filter((c) => ["GOLD", "SILVER"].includes(c.symbol));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Gold & Silver Intelligence</h1>
        {gs && (
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${sentimentBadge(gs.ai_sentiment)}`}>
            AI: {gs.ai_sentiment.toUpperCase()} ({(gs.ai_confidence * 100).toFixed(0)}%)
          </span>
        )}
      </div>

      {/* Price Grid */}
      {gs && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Gold MCX (₹/10g)", value: `₹${gs.gold_mcx_per10g.toLocaleString("en-IN")}` },
            { label: "Gold COMEX ($/oz)", value: `$${gs.gold_comex_usd_oz.toLocaleString()}` },
            { label: "Silver MCX (₹/kg)", value: `₹${gs.silver_mcx_per_kg.toLocaleString("en-IN")}` },
            { label: "Silver COMEX ($/oz)", value: `$${gs.silver_comex_usd_oz.toFixed(2)}` },
          ].map(({ label, value }) => (
            <div key={label} className="bg-slate-900 rounded-xl p-4 border border-slate-800">
              <p className="text-xs text-slate-500 mb-1">{label}</p>
              <p className="text-xl font-bold text-amber-400">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Spread & Macro */}
      {gs && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-900 rounded-xl p-5 border border-slate-800 space-y-3">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">India vs Global Spread</h2>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">MCX Fair Value</span>
              <span className="text-sm font-mono text-slate-100">₹{gs.gold_mcx_fair_value.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">MCX Premium</span>
              <span className={`text-sm font-mono font-bold ${changeColor(gs.gold_premium_pct)}`}>
                {(gs.gold_premium_pct * 100).toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">USD/INR</span>
              <span className="text-sm font-mono text-slate-100">₹{gs.usd_inr}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">DXY</span>
              <span className="text-sm font-mono text-slate-100">{gs.dxy}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">US Real Yield 10Y</span>
              <span className="text-sm font-mono text-slate-100">{gs.us_real_yield_10y}%</span>
            </div>
          </div>

          <div className="bg-slate-900 rounded-xl p-5 border border-slate-800 space-y-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Intelligence Scores</h2>
            <ScoreBar value={gs.inflation_hedge_score} label="Inflation Hedge Score" />
            <ScoreBar value={gs.geopolitical_risk_score} label="Geopolitical Risk" />
            <div className="flex justify-between pt-2">
              <span className="text-sm text-slate-400">Central Bank Buying</span>
              <span className={`text-sm font-medium ${gs.central_bank_buying ? "text-emerald-400" : "text-slate-500"}`}>
                {gs.central_bank_buying ? "✓ Active" : "Not detected"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* MCX Metals */}
      {metals.length > 0 && (
        <section className="bg-slate-900 rounded-xl p-5 border border-slate-800">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">MCX Contracts</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {metals.map((c) => (
              <div key={c.symbol} className="bg-slate-800 rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-bold text-slate-100">{c.symbol}</span>
                  <span className={`text-sm font-mono ${changeColor(c.change_pct)}`}>
                    {c.change_pct >= 0 ? "+" : ""}{c.change_pct.toFixed(2)}%
                  </span>
                </div>
                <p className="text-2xl font-bold text-amber-400 mb-2">
                  ₹{c.price.toLocaleString("en-IN")}
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
                  <span>OI: {c.open_interest.toLocaleString()}</span>
                  <span className={changeColor(c.oi_change_pct)}>OI Δ: {c.oi_change_pct >= 0 ? "+" : ""}{c.oi_change_pct.toFixed(1)}%</span>
                  <span>Vol: {c.volume.toLocaleString()}</span>
                  <span>Exp: {c.expiry}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {!gs && (
        <div className="bg-slate-900 rounded-xl p-8 border border-slate-800 text-center text-slate-500">
          Gold & Silver data unavailable — backend may be offline
        </div>
      )}
    </div>
  );
}
