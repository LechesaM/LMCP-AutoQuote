import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import WorkloadForecastPanel from "../components/business/WorkloadForecastPanel.tsx";
import OpportunityForecastPanel from "../components/business/OpportunityForecastPanel.tsx";
import RevenueProjectionPanel from "../components/business/RevenueProjectionPanel.tsx";
import HistoricalTrendPanel from "../components/business/HistoricalTrendPanel.tsx";
import { useForecasting } from "../hooks/useForecasting";

export default function OperationalForecastingPage() {
  const analytics = useForecasting();
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
      <WorkloadForecastPanel data={{ summary: { queueGrowth: analytics.summary.queueGrowth, operatorWorkload: analytics.summary.operatorWorkload, estimatedReviewDemand: analytics.summary.estimatedReviewDemand } }} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      <OpportunityForecastPanel data={{ summary: { rfqGrowth: analytics.summary.rfqGrowth, reviewDemand: analytics.summary.reviewDemand, sourceGrowth: analytics.summary.sourceGrowth, opportunityValueProjection: analytics.summary.opportunityValueProjection } }} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      <RevenueProjectionPanel data={{ summary: { projectedRfqOpportunityValue: analytics.summary.opportunityValueProjection, projectedMarginOpportunity: analytics.summary.opportunityValueProjection ? 25 : 0, sourceBasedOpportunityProjection: analytics.summary.sourceGrowth } }} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
      <HistoricalTrendPanel data={analytics.forecast} loading={analytics.loading} refreshing={analytics.refreshing} stale={analytics.stale} error={analytics.error} />
    </div>
  );
}

