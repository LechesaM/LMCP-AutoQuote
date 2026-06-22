"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";
const APP_ENV = process.env.NEXT_PUBLIC_APP_ENV || "development";

type Dashboard = {
  generated_at: string;
  rfq_status: {
    rfqs_created: number;
    dispatch_ready: number;
    rfqs_sent: number;
    rfqs_blocked_dry_run: number;
  };
  response_status: {
    mailbox_messages_checked: number;
    matched_supplier_responses: number;
    quotes_ingested: number;
  };
  commercial_position: {
    total_target_value: number;
    total_quoted_value: number;
    total_variance: number;
    total_variance_pct: number;
  };
  adjudication_status: {
    total_decisions: number;
    recommended_awards: number;
    recommended_negotiations: number;
    held_for_review: number;
  };
  action_status: {
    actions_ready: number;
    actions_sent: number;
    actions_blocked_dry_run: number;
  };
  supplier_decisions: Array<{
    supplier_name: string;
    decision: string;
    final_score: number;
    target_total: number;
    quoted_total: number;
    variance: number;
    variance_pct: number;
    reason: string;
  }>;
};

type HealthPayload = {
  status?: string;
  environment?: string;
  timestamp?: string;
};

function money(value: number) {
  return `R${Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function buildErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Unknown error";
}

export default function Home() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [backendHealth, setBackendHealth] = useState<HealthPayload | null>(null);
  const [backendReachable, setBackendReachable] = useState(false);
  const [backendMessage, setBackendMessage] = useState("Checking backend");

  async function loadDashboard() {
    try {
      const res = await fetch(`${API_BASE}/dashboard`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Dashboard request failed with ${res.status}`);
      }
      const data = (await res.json()) as Dashboard;
      setDashboard(data);
      setError("");
    } catch (err) {
      setError(buildErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function refreshAll() {
    setRefreshing(true);
    try {
      const res = await fetch(`${API_BASE}/refresh/all`, { method: "POST" });
      if (!res.ok) {
        throw new Error(`Refresh request failed with ${res.status}`);
      }
      await loadDashboard();
    } catch (err) {
      setError(buildErrorMessage(err));
    } finally {
      setRefreshing(false);
    }
  }

  async function loadBackendHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Health request failed with ${res.status}`);
      }
      const data = (await res.json()) as HealthPayload;
      setBackendHealth(data);
      setBackendReachable(true);
      setBackendMessage(data.status || "reachable");
    } catch (err) {
      setBackendHealth(null);
      setBackendReachable(false);
      setBackendMessage(buildErrorMessage(err));
    }
  }

  useEffect(() => {
    loadDashboard();
    loadBackendHealth();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        Loading LMCP AutoQuote dashboard...
      </main>
    );
  }

  const cp = dashboard?.commercial_position;

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <div className="mx-auto max-w-7xl space-y-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">LMCP AutoQuote</h1>
            <p className="text-slate-400">
              Enterprise Procurement Workflow Dashboard
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-300">
              <StatusBadge
                label={`Backend ${backendReachable ? "connected" : "unreachable"}`}
                tone={backendReachable ? "ok" : "error"}
              />
              <StatusBadge label={`Backend URL ${API_BASE}`} tone="neutral" />
              <StatusBadge
                label={`Frontend env ${backendHealth?.environment || APP_ENV}`}
                tone="neutral"
              />
            </div>
          </div>

          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="rounded-xl bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh Workflow"}
          </button>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge
              label={backendReachable ? "API reachable" : "API not reachable"}
              tone={backendReachable ? "ok" : "error"}
            />
            <span className="text-sm text-slate-400">{backendMessage}</span>
            {backendHealth?.timestamp ? (
              <span className="text-sm text-slate-500">
                Health timestamp: {backendHealth.timestamp}
              </span>
            ) : null}
          </div>
        </section>

        {error ? (
          <section className="rounded-2xl border border-amber-700 bg-amber-950/50 p-5 text-amber-100">
            <h2 className="font-semibold">Dashboard data unavailable</h2>
            <p className="mt-2 text-sm text-amber-200">{error}</p>
          </section>
        ) : null}

        {dashboard && cp ? (
          <>
            <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <Card title="Target Value" value={money(cp.total_target_value)} />
              <Card title="Quoted Value" value={money(cp.total_quoted_value)} />
              <Card title="Improvement" value={money(Math.abs(cp.total_variance))} />
              <Card title="Variance" value={`${cp.total_variance_pct.toFixed(2)}%`} />
            </section>

            <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <StatusPanel
                title="RFQ Workflow"
                rows={[
                  ["RFQs created", dashboard.rfq_status.rfqs_created],
                  ["Dispatch ready", dashboard.rfq_status.dispatch_ready],
                  ["RFQs sent", dashboard.rfq_status.rfqs_sent],
                  ["Dry-run blocked", dashboard.rfq_status.rfqs_blocked_dry_run],
                ]}
              />

              <StatusPanel
                title="Supplier Responses"
                rows={[
                  ["Mailbox checked", dashboard.response_status.mailbox_messages_checked],
                  ["Matched responses", dashboard.response_status.matched_supplier_responses],
                  ["Quotes ingested", dashboard.response_status.quotes_ingested],
                ]}
              />

              <StatusPanel
                title="Adjudication"
                rows={[
                  ["Decisions", dashboard.adjudication_status.total_decisions],
                  ["Awards", dashboard.adjudication_status.recommended_awards],
                  ["Negotiations", dashboard.adjudication_status.recommended_negotiations],
                  ["Held for review", dashboard.adjudication_status.held_for_review],
                ]}
              />
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 p-5">
                <h2 className="text-xl font-bold">Supplier Decisions</h2>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-4 text-left">Supplier</th>
                      <th className="p-4 text-left">Decision</th>
                      <th className="p-4 text-right">Score</th>
                      <th className="p-4 text-right">Target</th>
                      <th className="p-4 text-right">Quoted</th>
                      <th className="p-4 text-right">Variance</th>
                      <th className="p-4 text-right">Variance %</th>
                    </tr>
                  </thead>

                  <tbody>
                    {dashboard.supplier_decisions.map((d) => (
                      <tr
                        key={d.supplier_name}
                        className="border-t border-slate-800"
                      >
                        <td className="p-4 font-medium">{d.supplier_name}</td>
                        <td className="p-4">
                          <span className="rounded-full bg-slate-700 px-3 py-1 text-xs">
                            {d.decision}
                          </span>
                        </td>
                        <td className="p-4 text-right">{d.final_score}</td>
                        <td className="p-4 text-right">{money(d.target_total)}</td>
                        <td className="p-4 text-right">{money(d.quoted_total)}</td>
                        <td className="p-4 text-right">{money(d.variance)}</td>
                        <td className="p-4 text-right">
                          {d.variance_pct.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <footer className="text-xs text-slate-500">
              Last refreshed: {dashboard.generated_at}
            </footer>
          </>
        ) : null}
      </div>
    </main>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: "ok" | "error" | "neutral";
}) {
  const className =
    tone === "ok"
      ? "border-emerald-800 bg-emerald-950 text-emerald-300"
      : tone === "error"
        ? "border-rose-800 bg-rose-950 text-rose-300"
        : "border-slate-700 bg-slate-800 text-slate-200";

  return (
    <span className={`rounded-full border px-3 py-1 ${className}`}>
      {label}
    </span>
  );
}

function StatusPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, number]>;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <h2 className="mb-4 font-bold">{title}</h2>

      <div className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between">
            <span className="text-slate-400">{label}</span>
            <span className="font-semibold">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
