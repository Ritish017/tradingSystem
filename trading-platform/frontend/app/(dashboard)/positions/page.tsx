import { getPositions } from "@/lib/api";

export default async function PositionsPage() {
  const positions = await getPositions().catch(() => []);
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-4 text-2xl font-semibold">Positions</h1>
      <div className="grid gap-3">
        {positions.length === 0 ? <div>No open positions</div> : null}
        {positions.map((position) => (
          <div key={position.symbol} className="rounded border border-slate-700 p-4">
            <div className="font-semibold">{position.symbol}</div>
            <div className="text-sm text-slate-300">
              Qty: {position.quantity} | Avg: {position.avg_price.toFixed(2)} | U-PnL:{" "}
              {position.unrealized_pnl.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

