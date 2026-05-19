import ReviewQueueTable from "../components/workflows/ReviewQueueTable.tsx";
import QueueHealthPanel from "../components/health/QueueHealthPanel.tsx";
import OperationalAlertsPanel from "../components/workflows/OperationalAlertsPanel.tsx";
import SourceHealthTable from "../components/health/SourceHealthTable.tsx";

export default function ReviewQueuePage() {
  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Review Queue</h2>
        <p className="mt-2 text-sm text-slate-400">Review workflow visibility remains advisory and governed by operator capacity.</p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.4fr_.8fr]">
        <ReviewQueueTable />
        <div className="space-y-6">
          <QueueHealthPanel />
          <OperationalAlertsPanel />
          <SourceHealthTable />
        </div>
      </div>
    </div>
  );
}
