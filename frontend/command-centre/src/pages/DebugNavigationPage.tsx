import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useAuthStore from "../auth/authStore";
import { decodeTokenExpiry, isTokenExpired } from "../auth/sessionLifecycle";

const TARGETS = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "RFQ Operations", path: "/operations" },
  { label: "Review Queue", path: "/review" },
  { label: "RFQ Intelligence", path: "/qualification-insights" },
  { label: "Governance / Compliance Review", path: "/governance-compliance" },
];

declare global {
  interface Window {
    __LMCP_LAST_NAV_CLICK__?: {
      label: string;
      path: string;
      timestamp: string;
    } | null;
  }
}

function formatTokenExpiry(token) {
  if (!token) {
    return {
      expiryAt: "",
      expired: false,
    };
  }

  const expiryAtMs = decodeTokenExpiry(token);
  return {
    expiryAt: expiryAtMs ? new Date(expiryAtMs).toISOString() : "",
    expired: isTokenExpired(token),
  };
}

export default function DebugNavigationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const hydrated = useAuthStore((state) => state.hydrated);
  const loading = useAuthStore((state) => state.loading);
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);

  const authState = {
    isAuthenticated: Boolean(token && user),
    userRole: user?.role || "",
    tokenExpiry: formatTokenExpiry(token),
    hydrated,
    loading,
  };

  useEffect(() => {
    console.log("[DebugNavigationPage] render", {
      href: window.location.href,
      browserPathname: window.location.pathname,
      routerPathname: location.pathname,
      lastNavClick: window.__LMCP_LAST_NAV_CLICK__ || null,
      authState,
    });
  }, [authState, location.pathname]);

  const handleNavigate = (label, path) => () => {
    window.__LMCP_LAST_NAV_CLICK__ = {
      label,
      path,
      timestamp: new Date().toISOString(),
    };
    console.log("[DebugNavigationPage] test navigate click", {
      label,
      path,
      before: {
        browserPathname: window.location.pathname,
        routerPathname: location.pathname,
      },
    });
    navigate(path);
    window.setTimeout(() => {
      console.log("[DebugNavigationPage] test navigate result", {
        label,
        target: path,
        after: {
          href: window.location.href,
          browserPathname: window.location.pathname,
        },
      });
    }, 75);
  };

  return (
    <div className="space-y-6 px-6 py-8 text-slate-100">
      <div className="glass-card rounded-3xl p-6">
        <div className="text-xs font-black uppercase tracking-[.28em] text-command-cyan">Debug Navigation</div>
        <h1 className="mt-2 text-3xl font-black text-white">Command Centre navigation probe</h1>
        <p className="mt-2 text-sm text-slate-400">
          This page reports the browser URL, React Router location, last sidebar click, and direct navigation results.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Browser location</div>
          <div className="mt-3 space-y-2 text-sm text-slate-200">
            <div><span className="text-slate-400">window.location.href:</span> {window.location.href}</div>
            <div><span className="text-slate-400">window.location.pathname:</span> {window.location.pathname}</div>
            <div><span className="text-slate-400">React Router pathname:</span> {location.pathname}</div>
            <div><span className="text-slate-400">Paths match:</span> {window.location.pathname === location.pathname ? "yes" : "no"}</div>
          </div>
        </div>

        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Last navigation click</div>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(window.__LMCP_LAST_NAV_CLICK__ || null, null, 2)}</pre>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Auth state</div>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(authState, null, 2)}</pre>
        </div>

        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Direct navigate buttons</div>
          <div className="mt-3 flex flex-wrap gap-3">
            {TARGETS.map(({ label, path }) => (
              <button
                key={path}
                type="button"
                className="rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-black uppercase tracking-[.18em] text-command-cyan transition hover:border-command-green/50 hover:bg-command-green/10 hover:text-command-green"
                onClick={handleNavigate(label, path)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
