import TelemetrySummary from "../components/telemetry/TelemetrySummary.tsx";
import AnalyticsPanel from "../components/charts/AnalyticsPanel.tsx";
import { useTelemetry } from "../hooks/useTelemetry";
import { formatPercent } from "../utils/formatters";

export default function RFQOperationsPage() {
  const telemetry = useTelemetry();
  const metrics = telemetry.commandMetrics;

  return (
    <div className="space-y-6">
      <TelemetrySummary />
      <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
        <div className="glass-card rounded-3xl p-5">
          <h2 className="text-xl font-black text-white">RFQ Operations Overview</h2>
          <p className="mt-2 text-sm text-slate-400">A modular workbench for source harvest, qualification, and governed progression.</p>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-command-green/30 bg-command-green/10 p-4">
              <div className="text-xs font-bold uppercase tracking-[.24em] text-command-green">Eligible Rate</div>
              <div className="mt-2 text-3xl font-black text-white">{formatPercent(metrics.eligibleRate)}</div>
            </div>
            <div className="rounded-2xl border border-command-cyan/30 bg-command-cyan/10 p-4">
              <div className="text-xs font-bold uppercase tracking-[.24em] text-command-cyan">Avg Margin</div>
              <div className="mt-2 text-3xl font-black text-white">{formatPercent(metrics.avgMargin)}</div>
            </div>
          </div>
        </div>
        <AnalyticsPanel />
      </div>
    </div>
  );
}
