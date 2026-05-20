import OperatorFatiguePanel from "../components/stabilization/OperatorFatiguePanel.tsx";
import OperatorUXFeedbackPanel from "../components/stabilization/OperatorUXFeedbackPanel.tsx";
import RuntimeCleanupPanel from "../components/stabilization/RuntimeCleanupPanel.tsx";
import { useOperatorFeedback } from "../hooks/useOperatorFeedback";

export default function OperatorFeedbackPage() {
  const feedback = useOperatorFeedback();

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-command-green/20 bg-gradient-to-br from-command-green/10 via-slate-950 to-slate-950 p-5">
        <div className="text-xs font-black uppercase tracking-[.28em] text-command-green">Operator Feedback</div>
        <h2 className="mt-2 text-2xl font-black text-white">Operational ergonomics and fatigue visibility</h2>
        <p className="mt-2 max-w-4xl text-sm text-slate-300">
          Queue friction, focus exhaustion and cleanup friction are summarized to refine the operator experience without changing governance.
        </p>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <OperatorFatiguePanel snapshot={feedback.fatigue} loading={feedback.loading} />
        <OperatorUXFeedbackPanel snapshot={feedback.feedback} loading={feedback.loading} />
      </div>
      <RuntimeCleanupPanel snapshot={feedback.cleanup} loading={feedback.loading} />
    </div>
  );
}
