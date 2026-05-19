import SourceHealthTable from "../components/health/SourceHealthTable.tsx";
import ParserFailurePanel from "../components/health/ParserFailurePanel.tsx";
import QueueHealthPanel from "../components/health/QueueHealthPanel.tsx";

export default function SourceHealthPage() {
  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Source Health</h2>
        <p className="mt-2 text-sm text-slate-400">Read-only source status, parser failure trends and queue pressure remain visible for operators.</p>
      </div>
      <SourceHealthTable />
      <div className="grid gap-6 xl:grid-cols-2">
        <ParserFailurePanel />
        <QueueHealthPanel />
      </div>
    </div>
  );
}
