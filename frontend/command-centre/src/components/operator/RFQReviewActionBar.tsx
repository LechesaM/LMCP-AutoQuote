import { useMemo, useState } from "react";
import { AlertTriangle, Archive, CheckCircle2, CircleHelp, ClipboardCheck, FileWarning, HandCoins, MessageSquareWarning, RotateCcw, SendToBack } from "lucide-react";
import useAuthStore from "../../auth/authStore";
import ActionBadge from "../ui/ActionBadge.tsx";
import ConfirmationModal from "../ui/ConfirmationModal.tsx";

const ACTIONS = [
  { action: "assign_operator", label: "Assign", icon: HandCoins, tone: "cyan" },
  { action: "mark_reviewed", label: "Mark Reviewed", icon: ClipboardCheck, tone: "green" },
  { action: "request_clarification", label: "Request Clarification", icon: MessageSquareWarning, tone: "amber" },
  { action: "archive_rfq", label: "Archive", icon: Archive, tone: "red" },
  { action: "mark_evidence_incomplete", label: "Evidence Incomplete", icon: FileWarning, tone: "amber" },
  { action: "mark_supplier_quote_received", label: "Quote Received", icon: CheckCircle2, tone: "green" },
  { action: "mark_waiting_pricing", label: "Waiting Pricing", icon: CircleHelp, tone: "amber" },
  { action: "escalate_review", label: "Escalate", icon: AlertTriangle, tone: "red" },
  { action: "reopen_review", label: "Reopen Review", icon: RotateCcw, tone: "cyan" },
  { action: "acknowledge_alert", label: "Acknowledge Alert", icon: SendToBack, tone: "cyan" },
];

export default function RFQReviewActionBar({ rfq = {}, onAction, loading = false, disabled = false }) {
  const can = useAuthStore((state) => state.can);
  const [operatorId, setOperatorId] = useState("operator-1");
  const [note, setNote] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [error, setError] = useState("");

  const title = rfq?.title || rfq?.tenderId || "Selected RFQ";
  const notePreview = useMemo(
    () => [
      `Operator: ${operatorId || "unassigned"}`,
      `Target RFQ: ${rfq?.tenderId || "unknown"}`,
      `Note: ${note || "No additional note provided."}`,
      "Manual approval, review_ready and proof capture remain mandatory.",
    ].join("\n"),
    [note, operatorId, rfq?.tenderId],
  );

  const commitAction = async () => {
    if (!pendingAction) {
      return;
    }
    try {
      setError("");
      await onAction?.(pendingAction.action, {
        operatorId,
        tenderId: rfq?.tenderId || "",
        note,
        targetType: "rfq",
        details: {
          title,
          buyer: rfq?.buyer || "",
          province: rfq?.province || "",
          workflowStage: rfq?.workflowStage || "",
          reviewStatus: rfq?.reviewStatus || "",
        },
      });
      setPendingAction(null);
      setNote("");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to submit operator action");
    }
  };

  return (
    <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Operator Action Bar</div>
          <div className="mt-1 text-lg font-black text-white">{title}</div>
          <div className="mt-1 text-sm text-slate-400">Controlled actions only. Every action is confirmed, audited and reviewable.</div>
        </div>
        <ActionBadge action={disabled ? "Disabled" : loading ? "Loading" : "Manual Control"} tone={disabled ? "red" : "cyan"} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Operator ID</div>
          <input
            className="mt-2 w-full rounded-2xl border border-slate-700/60 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-500"
            onChange={(event) => setOperatorId(event.target.value)}
            placeholder="operator-1"
            value={operatorId}
          />
        </label>
        <label className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Audit Note</div>
          <textarea
            className="mt-2 min-h-[92px] w-full rounded-2xl border border-slate-700/60 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-500"
            onChange={(event) => setNote(event.target.value)}
            placeholder="Add operator intent and context..."
            value={note}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {ACTIONS.map(({ action, label, icon: Icon, tone }) => {
          const permission = action === "assign_operator"
            ? "assign_operator"
            : action === "mark_reviewed" || action === "request_clarification" || action === "mark_evidence_incomplete" || action === "mark_supplier_quote_received" || action === "mark_waiting_pricing" || action === "reopen_review"
              ? "mark_reviewed"
              : action === "escalate_review"
                ? "escalate_review"
                : action === "archive_rfq"
                  ? "archive_rfq"
                  : action === "acknowledge_alert"
                    ? "acknowledge_alert"
                    : "";
          const permitted = permission ? can(permission) : true;
          return (
          <button
            key={action}
            className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-2 text-sm font-bold transition ${
              tone === "green"
                ? "border-command-green/40 bg-command-green/10 text-command-green"
                : tone === "red"
                  ? "border-command-red/40 bg-command-red/10 text-command-red"
                  : tone === "amber"
                    ? "border-command-amber/40 bg-command-amber/10 text-command-amber"
                    : "border-command-cyan/40 bg-command-cyan/10 text-command-cyan"
            }`}
            disabled={disabled || loading || !permitted}
            onClick={() => setPendingAction({ action, label })}
            type="button"
            title={!permitted ? "Your role does not permit this action" : ""}
          >
            <Icon size={14} />
            {label}
          </button>
          );
        })}
      </div>

      {error ? <div className="mt-4 rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}

      <div className="mt-4 rounded-2xl border border-command-green/30 bg-command-green/10 px-4 py-3 text-sm text-slate-200">
        Manual approval, review_ready and proof capture remain mandatory. No autonomous actions are triggered here.
      </div>

      <ConfirmationModal
        confirmLabel={pendingAction ? `Confirm ${pendingAction.label}` : "Confirm"}
        message={pendingAction ? `You are about to execute a controlled operator action: ${pendingAction.label}. This will create an audit record and timeline event only.` : ""}
        notePreview={notePreview}
        open={Boolean(pendingAction)}
        onCancel={() => setPendingAction(null)}
        onConfirm={commitAction}
        title={pendingAction ? pendingAction.label : "Confirm action"}
        tone={pendingAction?.action === "archive_rfq" || pendingAction?.action === "escalate_review" ? "red" : "amber"}
      />
    </div>
  );
}
