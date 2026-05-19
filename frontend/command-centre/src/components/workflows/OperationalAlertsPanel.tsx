import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import { useOperationalHealth } from "../../hooks/useOperationalHealth";

const severityIcons = {
  info: Info,
  warning: AlertTriangle,
  critical: ShieldAlert,
};

function buildAlerts(health) {
  const alerts = [];
  if (health.sourceFailures > 0) {
    alerts.push({ severity: "critical", title: `${health.sourceFailures} source failures`, detail: "One or more harvesting sources are not healthy." });
  }
  if (health.parserFailures > 0) {
    alerts.push({ severity: "warning", title: `${health.parserFailures} parser failures`, detail: "Parser failure rate is elevated for one or more sources." });
  }
  if (health.queueLag > 0) {
    alerts.push({ severity: health.queueLag > 20 ? "critical" : "warning", title: `Queue lag ${health.queueLag}`, detail: "Review queue lag is present." });
  }
  if (health.staleEvidence > 0) {
    alerts.push({ severity: "warning", title: `${health.staleEvidence} stale evidence signals`, detail: "Some evidence or alerts have not been refreshed recently." });
  }
  if ((health.workflowFailures || 0) > 0 || (health.persistenceFailures || 0) > 0 || (health.auditFailures || 0) > 0) {
    alerts.push({ severity: "critical", title: "Workflow, persistence or audit failure", detail: "Critical backend telemetry has reported failures." });
  }
  if (!alerts.length) {
    alerts.push({ severity: "info", title: "No active operational alerts", detail: "Telemetry is stable and no critical warnings are pending." });
  }
  return alerts;
}

export default function OperationalAlertsPanel() {
  const health = useOperationalHealth();
  const alerts = buildAlerts(health);

  return (
    <SectionPanel
      title="Operational Alerts"
      description="Parser failures, stale evidence, queue lag and backend health warnings."
      state={health.loading ? "loading" : health.error ? "error" : health.stale ? "stale" : "ready"}
      actions={<StateBadge state={health.dataSource === "runtime" ? "ready" : "stale"} />}
    >
      <div className="space-y-3">
        {alerts.map((alert) => {
          const Icon = severityIcons[alert.severity] || Info;
          const palette =
            alert.severity === "critical"
              ? "border-command-red/30 bg-command-red/10 text-command-red"
              : alert.severity === "warning"
                ? "border-command-amber/30 bg-command-amber/10 text-command-amber"
                : "border-command-cyan/30 bg-command-cyan/10 text-command-cyan";

          return (
            <div key={alert.title} className={`rounded-2xl border p-4 ${palette}`}>
              <div className="flex items-start gap-3">
                <Icon size={18} className="mt-0.5" />
                <div>
                  <div className="text-sm font-black uppercase tracking-[.22em] text-white">{alert.title}</div>
                  <div className="mt-1 text-sm text-slate-200">{alert.detail}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </SectionPanel>
  );
}
