import { OrderPanel } from "@/components/OrderPanel";
import { FuturesDashboard } from "@/components/FuturesDashboard";

export default function TradingPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Trading</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <OrderPanel />
        <FuturesDashboard />
      </div>
    </div>
  );
}
