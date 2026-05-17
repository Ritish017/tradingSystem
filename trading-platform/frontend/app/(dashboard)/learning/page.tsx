import { getLearningRuns } from "@/lib/api";

export default async function LearningPage() {
  const runs = await getLearningRuns().catch(() => []);
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-4 text-2xl font-semibold">Learning & Retraining</h1>
      <div className="grid gap-3">
        {runs.length === 0 ? <div>No retraining runs yet.</div> : null}
        {runs.map((run, idx) => (
          <div key={`${run.model_name}-${idx}`} className="rounded border border-slate-700 p-4">
            <div className="font-semibold">{run.model_name}</div>
            <div className="text-sm text-slate-300">
              {run.old_sharpe.toFixed(3)} → {run.new_sharpe.toFixed(3)} |{" "}
              {run.accepted === "true" ? "ACCEPTED" : "REJECTED"} | {run.reason}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

