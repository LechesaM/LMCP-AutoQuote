import LoginForm from "../components/auth/LoginForm.tsx";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.22),_transparent_38%),linear-gradient(180deg,_#081018_0%,_#0b1220_55%,_#050816_100%)] px-6 py-10 text-slate-100">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-10 lg:grid-cols-[1.2fr_.8fr]">
        <section className="space-y-6">
          <div className="text-sm font-black uppercase tracking-[.32em] text-command-green">LMCP Command Centre</div>
          <h1 className="max-w-2xl text-5xl font-black tracking-tight text-white">Governed operator access for live procurement control.</h1>
          <p className="max-w-2xl text-base leading-7 text-slate-300">
            Sign in to view telemetry, review queues, operator actions, and governance evidence. Final submission remains manual-only.
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="text-xs font-black uppercase tracking-[.22em] text-slate-400">Governance</div>
              <div className="mt-2 text-sm text-slate-200">Manual approval, review_ready and proof capture stay mandatory.</div>
            </div>
            <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="text-xs font-black uppercase tracking-[.22em] text-slate-400">Access</div>
              <div className="mt-2 text-sm text-slate-200">Role-based access controls protect operator and governance functions.</div>
            </div>
            <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="text-xs font-black uppercase tracking-[.22em] text-slate-400">Security</div>
              <div className="mt-2 text-sm text-slate-200">Tokens are attached to API requests and validated by the backend.</div>
            </div>
          </div>
        </section>
        <section className="lg:justify-self-end lg:w-full lg:max-w-md">
          <LoginForm />
        </section>
      </div>
    </div>
  );
}

