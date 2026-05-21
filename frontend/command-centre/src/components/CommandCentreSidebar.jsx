import {
  Activity,
  BarChart3,
  BadgeDollarSign,
  ClipboardCheck,
  Clock3,
  FileSearch,
  Gauge,
  HeartPulse,
  LayoutDashboard,
  ListChecks,
  Radar as RadarOrbit,
  ServerCog,
  ServerCog as ServerCheck,
  ShieldAlert,
  ShieldCheck,
  TimerReset,
  Users2,
  Workflow,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import useAuthStore from "../auth/authStore";
import {
  adminRuntimeSidebarNavigationItems,
  getSidebarNavigationSections,
  operatorPrimarySidebarNavigationItems,
  operatorSupportSidebarNavigationItems,
} from "../routes/sidebarNavigation.js";

const navIcons = {
  "/dashboard": LayoutDashboard,
  "/operations": FileSearch,
  "/pricing-evidence": BadgeDollarSign,
  "/review": ListChecks,
  "/review-efficiency": TimerReset,
  "/governance": ShieldCheck,
  "/governance-compliance": ShieldCheck,
  "/audit-defensibility": FileSearch,
  "/compliance-reporting": ClipboardCheck,
  "/operator-operations": Users2,
  "/operator-assignments": ClipboardCheck,
  "/source-health": ServerCog,
  "/runtime-operations": Gauge,
  "/operational-analytics": BarChart3,
  "/incident-management": Activity,
  "/observability": RadarOrbit,
  "/sla-monitoring": Gauge,
  "/runtime-anomalies": Activity,
  "/stabilization-operations": ShieldAlert,
  "/runtime-reliability": ServerCheck,
  "/operator-productivity": HeartPulse,
  "/queue-optimization": Workflow,
  "/review-efficiency": TimerReset,
  "/executive-dashboard": BarChart3,
  "/profitability-analytics": BadgeDollarSign,
  "/operational-forecasting": Gauge,
  "/qualification-insights": FileSearch,
  "/operator-feedback": HeartPulse,
  "/activity-timeline": Clock3,
};

function isActivePath(currentPath, path) {
  return currentPath === path || (path !== "/dashboard" && currentPath.startsWith(`${path}/`));
}

function NavigationButton({ label, path, description = "", active, onClick }) {
  const Icon = navIcons[path] ?? LayoutDashboard;
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "group relative z-10 flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition-all pointer-events-auto",
        active
          ? "border border-command-green/70 bg-command-green text-slate-950 shadow-glow"
          : "border border-transparent text-slate-500 hover:border-slate-600/50 hover:bg-slate-800/40 hover:text-slate-200",
      ].join(" ")}
    >
      <Icon size={19} className={active ? "text-slate-950" : "text-slate-500 group-hover:text-command-cyan"} />
      <span>
        <div>{label}</div>
        {description ? <div className="mt-0.5 text-[11px] font-medium uppercase tracking-[.2em] opacity-70">{description}</div> : null}
      </span>
    </button>
  );
}

export default function CommandCentreSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const userRole = useAuthStore((state) => state.user?.role || "");

  const handleNavigate = (label, path) => () => {
    window.__LMCP_LAST_NAV_CLICK__ = {
      label,
      path,
      timestamp: new Date().toISOString(),
    };
    console.log("[CommandCentreSidebar] navigating", { label, path });
    navigate(path);
  };

  const sections = getSidebarNavigationSections(userRole);
  const visibleAdminRuntime = sections.find((section) => section.label === "Admin Runtime");

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-[290px] flex-col overflow-y-auto border-r border-slate-700/40 bg-gradient-to-b from-[#020817] via-[#06111f] to-black px-5 py-6 shadow-[20px_0_80px_rgba(0,0,0,.45)] pointer-events-auto">
      <div className="mb-8 shrink-0">
        <div className="text-3xl font-black tracking-tight text-command-green drop-shadow-[0_0_20px_rgba(34,197,94,.45)]">LMCP</div>
        <div className="mt-1 text-sm font-semibold uppercase tracking-[.34em] text-slate-400">Command Centre</div>
      </div>

      <nav className="relative z-10 flex-1 space-y-2">
        <div className="space-y-2">
          {operatorPrimarySidebarNavigationItems.map(({ label, path }) => {
            const active = isActivePath(location.pathname, path);
            return (
              <NavigationButton
                key={path}
                label={label}
                path={path}
                active={active}
                onClick={handleNavigate(label, path)}
              />
            );
          })}
        </div>

        <div className="my-4 h-px bg-slate-700/50" />

        <div className="space-y-2">
          {operatorSupportSidebarNavigationItems.map(({ label, path }) => {
            const active = isActivePath(location.pathname, path);
            return (
              <NavigationButton
                key={path}
                label={label}
                path={path}
                active={active}
                onClick={handleNavigate(label, path)}
              />
            );
          })}
        </div>
      </nav>

      <div className="mt-6 shrink-0 rounded-3xl border border-slate-700/60 bg-slate-950/50 p-4">
        <div className="text-xs font-semibold uppercase tracking-[.26em] text-command-cyan">Admin Runtime</div>
        <div className="mt-1 text-[11px] uppercase tracking-[.22em] text-slate-500">
          {visibleAdminRuntime ? "Visible to supervisors and admins" : "Hidden from operators"}
        </div>
        {visibleAdminRuntime ? (
          <div className="relative z-10 mt-3 space-y-2">
            {adminRuntimeSidebarNavigationItems.map(({ label, path }) => {
              const active = isActivePath(location.pathname, path);
              return (
                <NavigationButton
                  key={path}
                  label={label}
                  path={path}
                  active={active}
                  onClick={handleNavigate(label, path)}
                />
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="mt-6 shrink-0 rounded-2xl border border-command-green/20 bg-command-green/5 p-4">
        <div className="text-xs font-semibold uppercase tracking-[.26em] text-command-green">Governance</div>
        <div className="mt-2 text-sm text-slate-300">Manual approval, review, proof capture and final submission remain human-governed.</div>
      </div>
    </aside>
  );
}
