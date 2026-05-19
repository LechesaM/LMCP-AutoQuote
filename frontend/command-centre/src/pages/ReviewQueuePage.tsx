import ReviewQueueSummary from "../components/review/ReviewQueueSummary.tsx";
import { useHarvestHealth } from "../hooks/useHarvestHealth";

export default function ReviewQueuePage() {
  const harvestHealth = useHarvestHealth();

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <ReviewQueueSummary />
      <div className="glass-card rounded-3xl p-5">
        <h3 className="text-lg font-black text-white">Harvest Health</h3>
        <p className="mt-2 text-sm text-slate-400">Source status is exposed here as advisory operational telemetry.</p>
        <div className="mt-4 space-y-3">
          {harvestHealth.sources.slice(0, 6).map((source) => (
            <div key={source.id} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <div className="text-sm font-bold text-white">{source.name}</div>
              <div className="mt-1 text-xs text-slate-400">{source.tier} · {source.active ? "active" : "inactive"}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
