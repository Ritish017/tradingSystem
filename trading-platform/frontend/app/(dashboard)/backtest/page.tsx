export default function BacktestPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-4 p-8">
      <h1 className="text-2xl font-semibold">Backtest</h1>
      <p className="text-slate-300">
        Use <code>POST /api/backtest/run</code> to run a backtest and surface metrics in this page.
      </p>
      <pre className="overflow-auto rounded border border-slate-700 p-4 text-xs">
{`{
  "strategy_name": "supertrend_rsi",
  "symbols": ["RELIANCE", "TCS"],
  "start": "2020-01-01",
  "end": "2024-12-31"
}`}
      </pre>
    </main>
  );
}

