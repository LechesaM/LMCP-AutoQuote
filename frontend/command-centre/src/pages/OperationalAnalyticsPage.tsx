import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import OperatorPerformancePanel from "../components/runtime/OperatorPerformancePanel.tsx";
import ReviewQueueAnalyticsPanel from "../components/runtime/ReviewQueueAnalyticsPanel.tsx";
import SourceReliabilityPanel from "../components/runtime/SourceReliabilityPanel.tsx";
import { useOperationalAnalytics } from "../hooks/useOperationalAnalytics";

export default function OperationalAnalyticsPage() {
  const analytics = useOperationalAnalytics();

  return (
    <div className="space-y-6">
      <OperationalStatusBanner
        state={analytics.stale ? "stale" : analytics.refreshing ? "refreshing" : "ready"}
        dataSource={analytics.dataSource}
        lastUpdated={analytics.lastUpdated}
        loading={analytics.loading}
        refreshing={analytics.refreshing}
        error={analytics.error}
      />
      <OperatorPerformancePanel />
      <ReviewQueueAnalyticsPanel />
      <SourceReliabilityPanel />
    </div>
  );
}
