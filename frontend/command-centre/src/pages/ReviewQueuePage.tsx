import { useEffect, useState } from "react";
import ReviewQueueTable from "../components/workflows/ReviewQueueTable.tsx";
import QueueHealthPanel from "../components/health/QueueHealthPanel.tsx";
import OperationalAlertsPanel from "../components/workflows/OperationalAlertsPanel.tsx";
import SourceHealthTable from "../components/health/SourceHealthTable.tsx";
import ShareLinkControl from "../components/ui/ShareLinkControl.tsx";
import useSelectedTenderQueryState from "../hooks/useSelectedTenderQueryState";

export default function ReviewQueuePage() {
  const [selectedItemId, setSelectedItemId] = useState("");
  const { selectedTenderIdParam, shareableUrl, setSelectedTenderIdParam } = useSelectedTenderQueryState(selectedItemId);

  useEffect(() => {
    if (selectedTenderIdParam) {
      setSelectedItemId(selectedTenderIdParam);
    }
  }, [selectedTenderIdParam]);

  const syncSelectedItem = (row) => {
    setSelectedItemId(row?.id || "");
    setSelectedTenderIdParam(row?.id || "");
  };

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-black text-white">Review Queue</h2>
            <p className="mt-2 text-sm text-slate-400">Review workflow visibility remains advisory and governed by operator capacity.</p>
          </div>
          <ShareLinkControl shareableUrl={shareableUrl} ariaLabel="Copy selected queue item link" tooltipLabel="Queue deep link ready" compact />
        </div>
      </div>
      {selectedItemId ? (
        <div className="rounded-3xl border border-command-cyan/30 bg-command-cyan/10 px-5 py-4 text-sm text-slate-200">
          Deep link active for queue item <span className="font-black text-white">{selectedItemId}</span>.
        </div>
      ) : null}
      <div className="grid gap-6 xl:grid-cols-[1.4fr_.8fr]">
        <div className="min-w-0">
          <ReviewQueueTable onSelectItem={syncSelectedItem} selectedItemId={selectedItemId} />
        </div>
        <div className="min-w-0 space-y-6">
          <QueueHealthPanel />
          <OperationalAlertsPanel />
          <SourceHealthTable />
        </div>
      </div>
    </div>
  );
}
