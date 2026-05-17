import { getStrategies } from "@/lib/api";

export default async function StrategiesPage() {
  const strategies = await getStrategies().catch(() => []);
  return (
    <main className="mx-auto max-w-6xl p-8">
      <h1 className="mb-4 text-2xl font-semibold">Strategies</h1>
      <div className="overflow-x-auto rounded border border-slate-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900">
            <tr>
              <th className="p-3">Name</th>
              <th className="p-3">Type</th>
              <th className="p-3">Asset</th>
              <th className="p-3">Status</th>
              <th className="p-3">Weight</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((strategy) => (
              <tr key={strategy.name} className="border-t border-slate-800">
                <td className="p-3">{strategy.name}</td>
                <td className="p-3">{strategy.strategy_type}</td>
                <td className="p-3">{strategy.asset_class}</td>
                <td className="p-3">{strategy.status}</td>
                <td className="p-3">{strategy.current_weight.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

