import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import ProfitabilityTrendPanel from "../components/business/ProfitabilityTrendPanel.tsx";
import SourceROIHeatmap from "../components/business/SourceROIHeatmap.tsx";
import StrategicInsightsPanel from "../components/business/StrategicInsightsPanel.tsx";
import { useProfitabilityAnalytics } from "../hooks/useProfitabilityAnalytics";

export default function ProfitabilityAnalyticsPage() {
  const analytics = useProfitabilityAnalytics();
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
      <ProfitabilityTrendPanel data={analytics} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} onRetry={analytics.refresh} />
      <SourceROIHeatmap data={{ topValueSources: analytics.highValueRfqs, lowValueSources: analytics.lowConfidenceProfitability, noisySources: analytics.stalePricingImpact }} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      <StrategicInsightsPanel data={{ strategicHighlights: ["Profitability analytics are estimated and advisory only.", "Stale evidence reduces pricing defensibility."] }} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
    </div>
  );
}

