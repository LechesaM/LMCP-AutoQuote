import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import IncidentTrackerPanel from "../components/runtime/IncidentTrackerPanel.tsx";
import RuntimeAlertPanel from "../components/runtime/RuntimeAlertPanel.tsx";
import { useIncidentTracker } from "../hooks/useIncidentTracker";

export default function IncidentManagementPage() {
  const tracker = useIncidentTracker();

  return (
    <div className="space-y-6">
      <OperationalStatusBanner
        state={tracker.stale ? "stale" : tracker.refreshing ? "refreshing" : "ready"}
        dataSource={tracker.dataSource}
        lastUpdated={tracker.lastUpdated}
        loading={tracker.loading}
        refreshing={tracker.refreshing}
        error={tracker.error}
      />
      <IncidentTrackerPanel />
      <RuntimeAlertPanel />
    </div>
  );
}
