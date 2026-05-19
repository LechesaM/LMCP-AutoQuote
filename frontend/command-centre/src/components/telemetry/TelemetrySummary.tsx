import { BarChart3, ShieldCheck, Radar, Activity } from "lucide-react";
import MetricCard from "../dashboard/MetricCard.tsx";
import { useTelemetry } from "../../hooks/useTelemetry";
import { formatCurrency, formatPercent, formatInteger } from "../../utils/formatters";

export default function TelemetrySummary() {
  const telemetry = useTelemetry();
  const metrics = telemetry.commandMetrics;

  return (
    <section className="grid grid-cols-1 gap-4 xl:grid-cols-4">
      <MetricCard title="Total Harvested RFQs" value={formatInteger(metrics.totalHarvested)} subtitle="Last 30 days" icon={BarChart3} accent="cyan" />
      <MetricCard title="Eligible RFQs" value={formatInteger(metrics.eligibleRfqs)} subtitle="Supply & delivery qualified" icon={ShieldCheck} />
      <MetricCard title="Total Estimated Value" value={formatCurrency(metrics.estimatedValue * 1000000)} subtitle="Qualified province value" icon={Radar} accent="cyan" />
      <MetricCard title="Avg Margin" value={formatPercent(metrics.avgMargin)} subtitle="Target minimum 25%" icon={Activity} accent="amber" />
    </section>
  );
}
