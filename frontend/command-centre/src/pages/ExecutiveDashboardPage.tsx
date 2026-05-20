import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import ExecutiveSummaryPanel from "../components/business/ExecutiveSummaryPanel.tsx";
import ProfitabilityTrendPanel from "../components/business/ProfitabilityTrendPanel.tsx";
import RFQConversionPanel from "../components/business/RFQConversionPanel.tsx";
import SourceROIHeatmap from "../components/business/SourceROIHeatmap.tsx";
import OperatorTrendPanel from "../components/business/OperatorTrendPanel.tsx";
import GovernanceTrendPanel from "../components/business/GovernanceTrendPanel.tsx";
import WorkloadForecastPanel from "../components/business/WorkloadForecastPanel.tsx";
import StrategicInsightsPanel from "../components/business/StrategicInsightsPanel.tsx";
import { useExecutiveAnalytics } from "../hooks/useExecutiveAnalytics";

export default function ExecutiveDashboardPage() {
  const analytics = useExecutiveAnalytics();
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
      <ExecutiveSummaryPanel data={analytics} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} onRetry={analytics.refresh} />
      <StrategicInsightsPanel data={analytics} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      <ProfitabilityTrendPanel data={analytics.profitability} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} onRetry={analytics.refresh} />
      <div className="grid gap-6 xl:grid-cols-2">
        <RFQConversionPanel data={analytics.rfqConversion} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
        <SourceROIHeatmap data={analytics.sourceROI} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <OperatorTrendPanel data={analytics.operatorTrends} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
        <GovernanceTrendPanel data={analytics.governanceTrends} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      </div>
      <WorkloadForecastPanel data={analytics.workloadForecast} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
    </div>
  );
}

