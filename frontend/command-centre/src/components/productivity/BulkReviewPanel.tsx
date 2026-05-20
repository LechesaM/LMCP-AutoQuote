import SectionPanel from "../ui/SectionPanel.tsx";

export default function BulkReviewPanel({ preview, summary }) {
  const items = preview?.items || [];
  return (
    <SectionPanel title="Bulk Review Governance" description="Confirmation-gated bulk actions only." state="ready">
      <div className="rounded-2xl border border-command-amber/30 bg-command-amber/10 p-4 text-sm text-slate-200">
        Bulk actions are limited to assign, acknowledge alert and archive-reviewed. Every affected RFQ is audited individually.
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Metric label="Target Operator" value={preview?.target_operator_id || "n/a"} />
        <Metric label="Items Selected" value={items.length} />
        <Metric label="Confirmation Required" value={preview?.confirmed_required ? "Yes" : "No"} />
        <Metric label="Total Queue" value={summary?.total || 0} />
      </div>
    </SectionPanel>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
      <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">{label}</div>
      <div className="mt-2 text-lg font-black text-white">{value}</div>
    </div>
  );
}

