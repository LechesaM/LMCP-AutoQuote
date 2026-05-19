import { useState } from "react";
import OperatorTimeline from "../components/operator/OperatorTimeline.tsx";
import OperatorAuditDrawer from "../components/operator/OperatorAuditDrawer.tsx";
import OperatorNotificationsPanel from "../components/operator/OperatorNotificationsPanel.tsx";
import OperatorCapacityPanel from "../components/operator/OperatorCapacityPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import useOperatorCapacity from "../hooks/useOperatorCapacity";
import useOperatorNotifications from "../hooks/useOperatorNotifications";
import useOperatorTimeline from "../hooks/useOperatorTimeline";

export default function ActivityTimelinePage() {
  const timeline = useOperatorTimeline();
  const notifications = useOperatorNotifications();
  const capacity = useOperatorCapacity();
  const [selectedEvent, setSelectedEvent] = useState(null);

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Activity Timeline</h2>
        <p className="mt-2 text-sm text-slate-400">Append-only event history for operator actions, alerts, queue changes and governance acknowledgements.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Events" value={timeline.total} tone="cyan" />
        <TelemetryStat label="Data Source" value={timeline.dataSource || "runtime_fallback"} tone="green" />
        <TelemetryStat label="Loaded" value={timeline.loading ? "Yes" : "No"} tone="amber" />
        <TelemetryStat label="Refreshing" value={timeline.refreshing ? "Yes" : "No"} tone="red" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
        <OperatorTimeline snapshot={timeline} onSelectEvent={setSelectedEvent} />
        <div className="space-y-6">
          <OperatorCapacityPanel
            snapshot={{
              ...capacity,
            }}
          />
          <OperatorNotificationsPanel snapshot={notifications} />
        </div>
      </div>

      <OperatorAuditDrawer open={Boolean(selectedEvent)} event={selectedEvent || null} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
