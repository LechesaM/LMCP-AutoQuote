import { useEffect } from "react";
import { ShieldCheck, Gauge, Layers3, MapPinned, Route } from "lucide-react";
import CommandCentreSidebar from "../components/layout/CommandCentreSidebar.tsx";
import UserMenu from "../components/auth/UserMenu.tsx";
import RuntimeSafetyLayer from "../components/runtime/RuntimeSafetyLayer.tsx";
import { applyCommandCentreThemeVars, commandCentreTheme } from "../styles/theme";

export default function CommandCentreLayout({ routeTelemetry, children }) {
  useEffect(() => {
    applyCommandCentreThemeVars();
  }, []);

  return (
    <div className="relative isolate min-h-screen command-grid">
      <CommandCentreSidebar />
      <main className="relative z-0 ml-[290px] min-h-screen p-6">
        <RuntimeSafetyLayer />
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <div className="text-sm font-black uppercase tracking-[.32em] text-command-green">{commandCentreTheme.brand.position}</div>
            <h1 className="mt-2 text-4xl font-black tracking-tight text-white">{commandCentreTheme.brand.name} AutoQuote {commandCentreTheme.brand.title}</h1>
            <p className="mt-2 max-w-4xl text-sm text-slate-400">Harvest intelligence, RFQ qualification, operator review queues, pricing evidence, quote-pack readiness and manual-governed submission oversight.</p>
          </div>
          <div className="flex flex-col gap-3 text-right">
            <div className="rounded-2xl border border-command-green/30 bg-command-green/10 px-5 py-3">
              <div className="text-xs font-black uppercase tracking-[.22em] text-command-green">Production Mode</div>
              <div className="mt-1 text-lg font-black text-white">Supervised Live</div>
            </div>
            <UserMenu />
          </div>
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-4">
          <div className="glass-card rounded-3xl px-5 py-4">
            <div className="flex items-center gap-3 text-command-green">
              <ShieldCheck size={18} />
              <span className="text-xs font-black uppercase tracking-[.22em]">Governance</span>
            </div>
            <div className="mt-2 text-sm text-slate-300">Manual approval, review, proof capture and final submission remain human-governed.</div>
          </div>
          <div className="glass-card rounded-3xl px-5 py-4">
            <div className="flex items-center gap-3 text-command-cyan">
              <Gauge size={18} />
              <span className="text-xs font-black uppercase tracking-[.22em]">Capacity</span>
            </div>
            <div className="mt-2 text-sm text-slate-300">Review promotion is constrained by operator capacity and priority rules.</div>
          </div>
          <div className="glass-card rounded-3xl px-5 py-4">
            <div className="flex items-center gap-3 text-command-amber">
              <Layers3 size={18} />
              <span className="text-xs font-black uppercase tracking-[.22em]">Modular</span>
            </div>
            <div className="mt-2 text-sm text-slate-300">Telemetry, harvest, qualification, and review concerns are split into dedicated modules.</div>
          </div>
          <div className="glass-card rounded-3xl px-5 py-4">
            <div className="flex items-center gap-3 text-command-cyan">
              <Route size={18} />
              <span className="text-xs font-black uppercase tracking-[.22em]">Route Telemetry</span>
            </div>
            <div className="mt-2 text-sm text-slate-300">
              {routeTelemetry?.currentRouteLabel ?? "Dashboard"} · views {routeTelemetry?.routeViewCount ?? 0}
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
              <MapPinned size={13} />
              <span>{routeTelemetry?.currentRoute ?? "/dashboard"}</span>
            </div>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
