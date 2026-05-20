import {
  Activity,
  BarChart3,
  BadgeDollarSign,
  ClipboardCheck,
  Clock3,
  FileSearch,
  Gauge,
  GitBranch,
  HeartPulse,
  Keyboard,
  LayoutDashboard,
  ListChecks,
  Radar,
  Radar as RadarOrbit,
  ServerCog,
  ServerCog as ServerCheck,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  TimerReset,
  Users2,
  Workflow,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { commandCentreRoutes } from "../routes/commandCentreRoutes";
import { secondarySidebarNavigationItems } from "../routes/sidebarNavigation.js";

const navIcons = {
  "/dashboard": LayoutDashboard,
  "/executive-dashboard": BarChart3,
  "/profitability-analytics": BadgeDollarSign,
  "/operational-forecasting": Gauge,
  "/operations": FileSearch,
  "/source-health": ServerCog,
  "/qualification-insights": Radar,
  "/pricing-evidence": BadgeDollarSign,
  "/review": ListChecks,
  "/operator-productivity": SlidersHorizontal,
  "/queue-optimization": Workflow,
  "/review-efficiency": TimerReset,
  "/governance": ShieldCheck,
  "/governance-compliance": ShieldCheck,
  "/audit-defensibility": FileSearch,
  "/compliance-reporting": ClipboardCheck,
  "/operator-operations": Users2,
  "/operator-assignments": ClipboardCheck,
  "/runtime-operations": Gauge,
  "/operational-analytics": BarChart3,
  "/incident-management": Activity,
  "/observability": RadarOrbit,
  "/sla-monitoring": Gauge,
  "/runtime-anomalies": Activity,
  "/stabilization-operations": ShieldAlert,
  "/operator-feedback": HeartPulse,
  "/runtime-reliability": ServerCheck,
  "/activity-timeline": Clock3,
};

const secondaryItemIcons = {
  "Source Health": ServerCog,
  "Executive Dashboard": BarChart3,
  "Profitability Analytics": BadgeDollarSign,
  "Operational Forecasting": Gauge,
  "RFQ Intelligence": Radar,
  "Pricing Evidence": BadgeDollarSign,
  "Review Workflow": ClipboardCheck,
  "Queue Monitor": GitBranch,
  "Operational Health": Gauge,
  "Operator Operations": Users2,
  "Operator Productivity": SlidersHorizontal,
  "Queue Optimization": Workflow,
  "Review Efficiency": TimerReset,
  "Operator Shortcuts": Keyboard,
  "Governance / Compliance Review": ShieldCheck,
  "Audit Defensibility": FileSearch,
  "Compliance Reporting": ClipboardCheck,
  "Runtime Operations": Gauge,
  "Operational Analytics": BarChart3,
  "Incident Management": Activity,
  "Observability": RadarOrbit,
  "SLA Monitoring": Gauge,
  "Runtime Anomalies": Activity,
  "Stabilization Operations": ShieldAlert,
  "Operator Feedback": HeartPulse,
  "Runtime Reliability": ServerCheck,
  "Activity Timeline": Clock3,
};

function isActivePath(currentPath, path) {
  return currentPath === path || (path !== "/dashboard" && currentPath.startsWith(`${path}/`));
}

export default function CommandCentreSidebar() {
  const navigate = useNavigate();
  const location = useLocation();

  const handleNavigate = (label, path) => () => {
    window.__LMCP_LAST_NAV_CLICK__ = {
      label,
      path,
      timestamp: new Date().toISOString(),
    };
    console.log("[CommandCentreSidebar] navigating", { label, path });
    navigate(path);
  };

  return (
    <aside className="fixed left-0 top-0 z-50 h-screen w-[290px] overflow-y-auto border-r border-slate-700/40 bg-gradient-to-b from-[#020817] via-[#06111f] to-black px-5 py-6 shadow-[20px_0_80px_rgba(0,0,0,.45)] pointer-events-auto">
      <div className="mb-8">
        <div className="text-3xl font-black tracking-tight text-command-green drop-shadow-[0_0_20px_rgba(34,197,94,.45)]">LMCP</div>
        <div className="mt-1 text-sm font-semibold uppercase tracking-[.34em] text-slate-400">Command Centre</div>
      </div>

      <nav className="relative z-10 space-y-2">
        {commandCentreRoutes.map((route) => {
          const Icon = navIcons[route.path] ?? LayoutDashboard;
          const active = isActivePath(location.pathname, route.path);
          return (
            <button
              key={route.path}
              type="button"
              onClick={handleNavigate(route.label, route.path)}
              className={[
                "group relative z-10 flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition-all pointer-events-auto",
                active
                  ? "border border-command-green/70 bg-command-green text-slate-950 shadow-glow"
                  : "border border-transparent text-slate-500 hover:border-slate-600/50 hover:bg-slate-800/40 hover:text-slate-200",
              ].join(" ")}
            >
              <Icon size={19} className={active ? "text-slate-950" : "text-slate-500 group-hover:text-command-cyan"} />
              <span>
                <div>{route.label}</div>
                <div className="mt-0.5 text-[11px] font-medium uppercase tracking-[.2em] opacity-70">{route.description}</div>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="mt-6 rounded-3xl border border-slate-700/60 bg-slate-950/50 p-4">
        <div className="text-xs font-semibold uppercase tracking-[.26em] text-command-cyan">Command Centre Signals</div>
        <div className="relative z-10 mt-3 space-y-2">
          {secondarySidebarNavigationItems.map(({ label, path }) => {
            const Icon = secondaryItemIcons[label] ?? LayoutDashboard;
            const active = isActivePath(location.pathname, path);
            return (
              <button
                key={`${label}-${path}`}
                type="button"
                onClick={handleNavigate(label, path)}
                className={[
                  "group relative z-10 flex w-full items-center gap-3 rounded-2xl border px-3 py-2 text-sm transition-all pointer-events-auto",
                  active
                    ? "border-command-green/70 bg-command-green text-slate-950 shadow-glow"
                    : "border-slate-800/70 bg-slate-950/40 text-slate-400 hover:border-slate-600/50 hover:bg-slate-800/40 hover:text-slate-200",
                ].join(" ")}
              >
                <Icon size={15} className={active ? "text-slate-950" : "text-command-green"} />
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="absolute bottom-5 left-5 right-5 rounded-2xl border border-command-green/20 bg-command-green/5 p-4">
        <div className="text-xs font-semibold uppercase tracking-[.26em] text-command-green">Governance</div>
        <div className="mt-2 text-sm text-slate-300">Manual approval, review, proof capture and final submission remain human-governed.</div>
      </div>
    </aside>
  );
}
