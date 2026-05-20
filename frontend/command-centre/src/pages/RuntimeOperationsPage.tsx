import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import RuntimeMetricsPanel from "../components/runtime/RuntimeMetricsPanel.tsx";
import SystemHealthTimeline from "../components/runtime/SystemHealthTimeline.tsx";
import RuntimeAlertPanel from "../components/runtime/RuntimeAlertPanel.tsx";
import BackupValidationPanel from "../components/runtime/BackupValidationPanel.tsx";
import { useRuntimeMetrics } from "../hooks/useRuntimeMetrics";

export default function RuntimeOperationsPage() {
  const runtime = useRuntimeMetrics();

  return (
    <div className="space-y-6">
      <OperationalStatusBanner
        state={runtime.stale ? "stale" : runtime.refreshing ? "refreshing" : "ready"}
        dataSource={runtime.dataSource}
        lastUpdated={runtime.lastUpdated}
        loading={runtime.loading}
        refreshing={runtime.refreshing}
        error={runtime.error}
      />
      <RuntimeMetricsPanel />
      <SystemHealthTimeline />
      <RuntimeAlertPanel />
      <BackupValidationPanel />
    </div>
  );
}
