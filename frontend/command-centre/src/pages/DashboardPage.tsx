import TopFilterBar from "../components/ui/TopFilterBar.tsx";
import MetricCard from "../components/dashboard/MetricCard.tsx";
import ProvinceHeatMap from "../components/heatmap/ProvinceHeatMap.tsx";
import OpportunityRadar from "../components/radar/OpportunityRadar.tsx";
import AnalyticsPanel from "../components/charts/AnalyticsPanel.tsx";
import GovernanceRulesGrid from "../components/governance/GovernanceRulesGrid.tsx";
import OperationalHealthPanel from "../components/health/OperationalHealthPanel.tsx";
import { commandMetrics } from "../data/harvestedRfqs";
import { BadgeDollarSign, FileText, Gauge, LineChart, PackageCheck, Percent } from "lucide-react";

export default function DashboardPage() {
  return (
    <>
      <TopFilterBar />
      <div className="mt-6">
        <OperationalHealthPanel />
      </div>
      <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-6">
        <MetricCard title="Total Harvested RFQs" value={commandMetrics.totalHarvested} subtitle="Last 30 days" icon={FileText} accent="cyan" />
        <MetricCard title="Eligible RFQs" value={commandMetrics.eligibleRfqs} subtitle="Supply & delivery qualified" icon={PackageCheck} />
        <MetricCard title="Total Estimated Value" value={`R${commandMetrics.estimatedValue}M`} subtitle="Qualified province value" icon={LineChart} accent="cyan" />
        <MetricCard title="High Profit RFQs" value={commandMetrics.highProfitRfqs} subtitle="Above target threshold" icon={BadgeDollarSign} accent="amber" />
        <MetricCard title="Avg Estimated Profit" value="R38,920" subtitle="Per eligible RFQ" icon={Gauge} />
        <MetricCard title="Avg Margin" value={`${commandMetrics.avgMargin}%`} subtitle="Target minimum 25%" icon={Percent} />
      </section>
      <section className="mt-6 grid gap-6 2xl:grid-cols-[1fr_420px]">
        <div className="space-y-6">
          <ProvinceHeatMap />
          <OpportunityRadar />
        </div>
        <AnalyticsPanel />
      </section>
      <div className="mt-6">
        <GovernanceRulesGrid />
      </div>
    </>
  );
}
