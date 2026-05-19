import {
  BadgeDollarSign,
  ClipboardCheck,
  FileSearch,
  GitBranch,
  Gauge,
  LayoutDashboard,
  ListChecks,
  PackageCheck,
  Scale,
  ShieldCheck,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { commandCentreRoutes } from "../routes/commandCentreRoutes";

const navIcons = {
  "/dashboard": LayoutDashboard,
  "/operations": FileSearch,
  "/review": ListChecks,
  "/governance": ShieldCheck,
};

const secondaryItems = [
  { label: "Pricing Review", Icon: BadgeDollarSign },
  { label: "Quote Pack Engine", Icon: PackageCheck },
  { label: "Review Workflow", Icon: ClipboardCheck },
  { label: "Queue Monitor", Icon: GitBranch },
  { label: "Compliance Review", Icon: Scale },
  { label: "Operational Health", Icon: Gauge },
];

export default function CommandCentreSidebar() {
  return (
    <aside className="fixed left-0 top-0 z-30 h-screen w-[290px] overflow-y-auto border-r border-slate-700/40 bg-gradient-to-b from-[#020817] via-[#06111f] to-black px-5 py-6 shadow-[20px_0_80px_rgba(0,0,0,.45)]">
      <div className="mb-8">
        <div className="text-3xl font-black tracking-tight text-command-green drop-shadow-[0_0_20px_rgba(34,197,94,.45)]">LMCP</div>
        <div className="mt-1 text-sm font-semibold uppercase tracking-[.34em] text-slate-400">Command Centre</div>
      </div>

      <nav className="space-y-2">
        {commandCentreRoutes.map((route) => {
          const Icon = navIcons[route.path] ?? LayoutDashboard;
          return (
            <NavLink
              key={route.path}
              to={route.path}
              end
              className={({ isActive }) =>
                [
                  "group flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition-all",
                  isActive
                    ? "border border-command-green/70 bg-command-green text-slate-950 shadow-glow"
                    : "border border-transparent text-slate-500 hover:border-slate-600/50 hover:bg-slate-800/40 hover:text-slate-200",
                ].join(" ")
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={19} className={isActive ? "text-slate-950" : "text-slate-500 group-hover:text-command-cyan"} />
                  <span>
                    <div>{route.label}</div>
                    <div className="mt-0.5 text-[11px] font-medium uppercase tracking-[.2em] opacity-70">{route.description}</div>
                  </span>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-6 rounded-3xl border border-slate-700/60 bg-slate-950/50 p-4">
        <div className="text-xs font-semibold uppercase tracking-[.26em] text-command-cyan">Command Centre Signals</div>
        <div className="mt-3 space-y-2">
          {secondaryItems.map(({ label, Icon }) => (
            <div key={label} className="flex items-center gap-3 rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-sm text-slate-400">
              <Icon size={15} className="text-command-green" />
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="absolute bottom-5 left-5 right-5 rounded-2xl border border-command-green/20 bg-command-green/5 p-4">
        <div className="text-xs font-semibold uppercase tracking-[.26em] text-command-green">Governance</div>
        <div className="mt-2 text-sm text-slate-300">Manual approval, review, proof capture and final submission remain human-governed.</div>
      </div>
    </aside>
  );
}
