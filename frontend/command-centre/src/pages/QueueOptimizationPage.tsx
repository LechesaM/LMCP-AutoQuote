import BulkReviewPanel from "../components/productivity/BulkReviewPanel.tsx";
import QueueBalancePanel from "../components/productivity/QueueBalancePanel.tsx";
import ReviewPriorityPanel from "../components/productivity/ReviewPriorityPanel.tsx";
import ReviewQueueHeatmap from "../components/productivity/ReviewQueueHeatmap.tsx";
import useQueueOptimization from "../hooks/useQueueOptimization";

export default function QueueOptimizationPage() {
  const queue = useQueueOptimization();
  return (
    <div className="space-y-6">
      <header className="glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-[.26em] text-command-cyan">Queue Optimization</div>
            <h1 className="mt-2 text-3xl font-black text-white">Balance queue pressure and priority ordering</h1>
            <p className="mt-2 text-sm text-slate-400">Urgency, closing dates, stale evidence and governance blockers stay visible and ordered.</p>
          </div>
          <Badge label={queue.dataSource} />
        </div>
      </header>

      <QueueBalancePanel queueOptimization={queue.queueOptimization} workload={{ remainingCapacity: queue.queueOptimization?.summary?.total ? Math.max(0, 1000 - queue.queueOptimization.summary.total) : 1000 }} />
      <ReviewQueueHeatmap
        heatmap={queue.queueHeatmap.heatmap}
        operatorDistribution={queue.queueHeatmap.operatorDistribution}
        sourceDistribution={queue.queueHeatmap.sourceDistribution}
        escalationDensity={queue.queueHeatmap.escalationDensity}
        provinceDensity={queue.queueHeatmap.provinceDensity}
      />
      <ReviewPriorityPanel priorities={queue.reviewPriorities} />
      <BulkReviewPanel preview={{ confirmed_required: true, target_operator_id: "", items: queue.queueOptimization.optimizedQueue.slice(0, 5) }} summary={queue.queueOptimization.summary} />
    </div>
  );
}

function Badge({ label }) {
  return <span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{label}</span>;
}

