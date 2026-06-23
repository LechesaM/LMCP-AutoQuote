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

type VisibilitySnapshot = {
  dryRun: Record<string, any> | null;
  lifecycleStatus: Record<string, any> | null;
  lifecycleTelemetry: Record<string, any> | null;
  recentRfqs: Array<Record<string, any>>;
  guardSummary: Record<string, any> | null;
  operationalHealth: Record<string, any> | null;
  reviewQueue: Record<string, any> | null;
  warnings: string[];
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

function getNumber(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function getString(value: unknown, fallback = "-") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function getBooleanBadge(value: unknown) {
  if (value === true) return { label: "Yes", tone: "ok" as const };
  if (value === false) return { label: "No", tone: "error" as const };
  return { label: "Unknown", tone: "neutral" as const };
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

function sumRecordValues(value: unknown): number {
  if (!value || typeof value !== "object") return 0;
  return Object.values(value as Record<string, unknown>).reduce<number>(
    (total, entry) => total + getNumber(entry, 0),
    0,
  );
}

export default function Home() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [visibilityError, setVisibilityError] = useState("");
  const [backendHealth, setBackendHealth] = useState<HealthPayload | null>(null);
  const [backendReachable, setBackendReachable] = useState(false);
  const [backendMessage, setBackendMessage] = useState("Checking backend");
  const [visibility, setVisibility] = useState<VisibilitySnapshot>({
    dryRun: null,
    lifecycleStatus: null,
    lifecycleTelemetry: null,
    recentRfqs: [],
    guardSummary: null,
    operationalHealth: null,
    reviewQueue: null,
    warnings: [],
  });

  async function loadDashboard() {
    const data = await fetchJson<Dashboard>("/dashboard");
    setDashboard(data);
  }

  async function loadBackendHealth() {
    try {
      const data = await fetchJson<HealthPayload>("/health");
      setBackendHealth(data);
      setBackendReachable(true);
      setBackendMessage(data.status || "reachable");
    } catch (err) {
      setBackendHealth(null);
      setBackendReachable(false);
      setBackendMessage(buildErrorMessage(err));
    }
  }

  async function loadVisibility() {
    const requests = [
      { key: "dryRun", path: "/rfq-lifecycle/upload-dry-run/status" },
      { key: "lifecycleStatus", path: "/rfq-lifecycle/status" },
      { key: "lifecycleTelemetry", path: "/rfq-lifecycle/telemetry" },
      { key: "recentRfqs", path: "/rfq-lifecycle/items?limit=8" },
      { key: "guardSummary", path: "/go-live-guards/summary?limit=8" },
      { key: "operationalHealth", path: "/telemetry/operational-health" },
      { key: "reviewQueue", path: "/telemetry/review-queue" },
    ] as const;

    const settled = await Promise.allSettled(
      requests.map(async (request) => ({ key: request.key, data: await fetchJson<Record<string, any>>(request.path) })),
    );

    const next: VisibilitySnapshot = {
      dryRun: null,
      lifecycleStatus: null,
      lifecycleTelemetry: null,
      recentRfqs: [],
      guardSummary: null,
      operationalHealth: null,
      reviewQueue: null,
      warnings: [],
    };

    const warnings: string[] = [];
    for (const result of settled) {
      if (result.status === "rejected") {
        warnings.push(buildErrorMessage(result.reason));
        continue;
      }
      const { key, data } = result.value;
      if (key === "recentRfqs") {
        const items = data.items;
        next.recentRfqs = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "dryRun") {
        next.dryRun = data;
      } else if (key === "lifecycleStatus") {
        next.lifecycleStatus = data;
      } else if (key === "lifecycleTelemetry") {
        next.lifecycleTelemetry = data;
      } else if (key === "guardSummary") {
        next.guardSummary = data;
      } else if (key === "operationalHealth") {
        next.operationalHealth = data;
      } else if (key === "reviewQueue") {
        next.reviewQueue = data;
      }
    }

    next.warnings = warnings;
    setVisibility(next);
    setVisibilityError(
      warnings.length ? `Some operational visibility endpoints were unavailable: ${warnings.join("; ")}` : "",
    );
  }

  async function loadAll() {
    await Promise.all([loadDashboard(), loadBackendHealth(), loadVisibility()]);
  }

  async function refreshAll() {
    setRefreshing(true);
    try {
      await loadAll();
    } catch (err) {
      setError(buildErrorMessage(err));
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshAll();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        Loading LMCP AutoQuote dashboard...
      </main>
    );
  }

  const cp = dashboard?.commercial_position;
  const lifecycleCounts = visibility.lifecycleStatus?.queue_by_lifecycle_state || {};
  const lifecycleTelemetry = visibility.lifecycleTelemetry || {};
  const workerHeartbeat = lifecycleTelemetry.worker_heartbeat || {};
  const queueBacklog = lifecycleTelemetry.queue_backlog || {};
  const guardSummary = visibility.guardSummary?.summary || {};
  const dryRunStatus = visibility.dryRun || {};
  const operationalHealth = visibility.operationalHealth || {};
  const reviewQueue = visibility.reviewQueue || {};
  const taskTimeouts = lifecycleTelemetry.task_timeout_detection || {};
  const autoRecoveryHooks = lifecycleTelemetry.auto_recovery_hooks || {};
  const retryCount = getNumber(visibility.lifecycleStatus?.throughput?.retried, 0);
  const queuedForRetry = getNumber(lifecycleCounts.READY_FOR_RETRY, 0);
  const deadQueues = Array.isArray(queueBacklog.isolated_dead_queues) ? queueBacklog.isolated_dead_queues : [];
  const warnings = [
    ...(Array.isArray(lifecycleTelemetry.warnings) ? lifecycleTelemetry.warnings : []),
    ...(visibility.warnings || []),
  ];

  const systemResilienceScore = getNumber(lifecycleTelemetry.system_resilience_score, 0);
  const dryRunLockStatus = getBooleanBadge(dryRunStatus.dry_run);
  const queueBacklogDetected = getBooleanBadge(queueBacklog.backlog_detected);
  const backendStatusTone = backendReachable ? "ok" : "error";

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <div className="mx-auto max-w-7xl space-y-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">LMCP AutoQuote</h1>
              <StatusBadge label={APP_ENV === "staging" ? "Staging Command Centre" : "Command Centre"} tone="neutral" />
            </div>
            <p className="text-slate-400">Enterprise Procurement Workflow Dashboard</p>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
              <StatusBadge
                label={`Backend ${backendReachable ? "connected" : "unreachable"}`}
                tone={backendStatusTone}
              />
              <StatusBadge label={`Backend URL ${API_BASE}`} tone="neutral" />
              <StatusBadge
                label={`Frontend env ${backendHealth?.environment || APP_ENV}`}
                tone="neutral"
              />
              <StatusBadge
                label={`Telemetry ${systemResilienceScore >= 70 ? "healthy" : "watch"}`}
                tone={systemResilienceScore >= 70 ? "ok" : "error"}
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

        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card title="Target Value" value={money(cp?.total_target_value || 0)} />
          <Card title="Quoted Value" value={money(cp?.total_quoted_value || 0)} />
          <Card title="Improvement" value={money(Math.abs(cp?.total_variance || 0))} />
          <Card title="Variance" value={`${Number(cp?.total_variance_pct || 0).toFixed(2)}%`} />
        </section>

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
            <StatusBadge
              label={`Dry-run ${dryRunStatus.status || "unknown"}`}
              tone={dryRunStatus.status === "ok" ? "ok" : dryRunStatus.status === "not_run" ? "neutral" : "error"}
            />
            <StatusBadge
              label={`Submission locks ${getNumber(guardSummary.submission_locks, 0)}`}
              tone={getNumber(guardSummary.submission_locks, 0) > 0 ? "neutral" : "ok"}
            />
          </div>
        </section>

        {(error || visibilityError) ? (
          <section className="space-y-3 rounded-2xl border border-amber-700 bg-amber-950/50 p-5 text-amber-100">
            {error ? (
              <div>
                <h2 className="font-semibold">Workflow dashboard data unavailable</h2>
                <p className="mt-2 text-sm text-amber-200">{error}</p>
              </div>
            ) : null}
            {visibilityError ? (
              <div>
                <h2 className="font-semibold">Operational visibility partial</h2>
                <p className="mt-2 text-sm text-amber-200">{visibilityError}</p>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Staging Operational Visibility</h2>
              <p className="text-sm text-slate-400">
                Read-only dry-run and lifecycle telemetry. No submission controls are exposed.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only panel" : "Read-only panel"}
              tone="neutral"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MetricPanel
              title="Dry-Run Execution Status"
              tone={dryRunStatus.status === "ok" ? "ok" : "neutral"}
              summary={dryRunStatus.mode || "No dry-run status recorded"}
              items={[
                ["Status", getString(dryRunStatus.status)],
                ["Dry-run enabled", dryRunLockStatus.label],
                ["Selected RFQs", String(getNumber(dryRunStatus.selected_count, 0))],
                ["Ready count", String(getNumber(dryRunStatus.ready_count, 0))],
                ["Missing docs", String(getNumber(dryRunStatus.missing_documents_count, 0))],
                ["Operator action required", getBooleanBadge(dryRunStatus.operator_action_required).label],
              ]}
            />

            <MetricPanel
              title="RFQ Lifecycle State"
              tone="neutral"
              summary={`Total RFQs: ${getNumber(visibility.lifecycleStatus?.total_rfqs, 0)}`}
              items={[
                ["DISCOVERED", String(getNumber(lifecycleCounts.DISCOVERED, 0))],
                ["DOCUMENTS_PARSED", String(getNumber(lifecycleCounts.DOCUMENTS_PARSED, 0))],
                ["PRICED", String(getNumber(lifecycleCounts.PRICED, 0))],
                ["QUOTE_PACK_READY", String(getNumber(lifecycleCounts.QUOTE_PACK_READY, 0))],
                ["SUBMISSION_READY", String(getNumber(lifecycleCounts.SUBMISSION_READY, 0))],
                ["READY_FOR_RETRY", String(queuedForRetry)],
              ]}
            />

            <MetricPanel
              title="Queue Health"
              tone={queueBacklogDetected.tone}
              summary={`Backlog ${queueBacklog.total_backlog || 0}`}
              items={[
                ["Backlog detected", queueBacklogDetected.label],
                ["Broker queue depth", String(sumRecordValues(queueBacklog.broker_queue_depth))],
                ["Lifecycle queue depth", String(sumRecordValues(queueBacklog.lifecycle_queue_depth))],
                ["Stalled tasks", String(Array.isArray(lifecycleTelemetry.stalled_lifecycle_tasks) ? lifecycleTelemetry.stalled_lifecycle_tasks.length : 0)],
                ["Retry count", String(retryCount)],
                ["Dead queues", String(deadQueues.length)],
              ]}
            />

            <MetricPanel
              title="Worker Heartbeats"
              tone={getBooleanBadge(lifecycleTelemetry.worker_online).tone}
              summary={`${Array.isArray(workerHeartbeat.online_workers) ? workerHeartbeat.online_workers.length : 0} online worker(s)`}
              items={[
                ["Worker online", getBooleanBadge(lifecycleTelemetry.worker_online).label],
                ["Crash count", String(getNumber(lifecycleTelemetry.worker_crash_count, 0))],
                ["Restart count", String(getNumber(lifecycleTelemetry.worker_restart_count, 0))],
                ["Active workers", String(Array.isArray(workerHeartbeat.online_workers) ? workerHeartbeat.online_workers.length : 0)],
                ["Queue workers", String(workerHeartbeat.queue_workers ? Object.keys(workerHeartbeat.queue_workers).length : 0)],
                ["Heartbeat source", getString(workerHeartbeat.state_store, "sandbox")],
              ]}
            />

            <MetricPanel
              title="Retry and Dead-Letter Visibility"
              tone={warnings.length ? "error" : "ok"}
              summary={warnings.length ? `${warnings.length} warning(s)` : "No retry warnings"}
              items={[
                ["Retry pending", String(queuedForRetry)],
                ["Timed-out tasks", String(Array.isArray(taskTimeouts.timed_out_tasks) ? taskTimeouts.timed_out_tasks.length : 0)],
                ["Isolated dead queues", String(deadQueues.length)],
                ["Recovery hooks", String(Object.keys(autoRecoveryHooks).length)],
                ["Backlog warning threshold", String(getNumber(queueBacklog.warning_threshold, 0))],
                ["Warnings", String(warnings.length)],
              ]}
            />

            <MetricPanel
              title="Submission Lock Status"
              tone={getNumber(guardSummary.submission_locks, 0) > 0 ? "neutral" : "ok"}
              summary={`Locks: ${getNumber(guardSummary.submission_locks, 0)}`}
              items={[
                ["Submission locks", String(getNumber(guardSummary.submission_locks, 0))],
                ["Operator rejections", String(getNumber(guardSummary.operator_rejections, 0))],
                ["Paused sources", String(getNumber(guardSummary.paused_sources, 0))],
                ["Guard events", String(getNumber(guardSummary.guard_events, 0))],
                ["Latest guard update", getString(visibility.guardSummary?.updated_at, "n/a")],
                ["Dry-run enabled", dryRunLockStatus.label],
              ]}
            />

            <MetricPanel
              title="Telemetry Health"
              tone={systemResilienceScore >= 70 ? "ok" : "error"}
              summary={`System resilience ${systemResilienceScore.toFixed(2)}`}
              items={[
                ["Operational status", getString(operationalHealth.status, "unknown")],
                ["Review queue capacity", String(getNumber(reviewQueue.operator_capacity, 0))],
                ["Capacity remaining", String(getNumber(reviewQueue.operator_capacity_remaining, 0))],
                ["Capacity used", String(getNumber(reviewQueue.operator_capacity_used, 0))],
                ["Generated at", getString(lifecycleTelemetry.generated_at, "n/a")],
                ["Warnings", String(warnings.length)],
              ]}
            />
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Recent RFQ States</h2>
              <StatusBadge label="Read-only" tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">RFQ</th>
                    <th className="p-3 text-left">State</th>
                    <th className="p-3 text-left">Source</th>
                    <th className="p-3 text-left">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {visibility.recentRfqs.length ? (
                    visibility.recentRfqs.map((item) => (
                      <tr key={String(item.rfq_id || item.title || Math.random())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.rfq_id || item.reference || item.tender_id, "n/a")}</td>
                        <td className="p-3">
                          <StatusBadge label={getString(item.current_state || item.state || "unknown")} tone="neutral" />
                        </td>
                        <td className="p-3 text-slate-300">{getString(item.source || item.source_name || "staging")}</td>
                        <td className="p-3 text-slate-400">{getString(item.updated_at || item.created_at || "", "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={4}>
                        No RFQ records found in the current staging runtime.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Operational Warnings</h2>
              <StatusBadge
                label={warnings.length ? `${warnings.length} warning(s)` : "No warnings"}
                tone={warnings.length ? "error" : "ok"}
              />
            </div>

            <div className="mt-4 space-y-3">
              {warnings.length ? (
                warnings.map((warning, index) => (
                  <div key={`${warning}-${index}`} className="rounded-xl border border-amber-800 bg-amber-950/40 p-4 text-amber-100">
                    {warning}
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-slate-400">
                  Dry-run telemetry, lock protection, and queue visibility are stable.
                </div>
              )}
            </div>
          </div>
        </section>

        {dashboard ? (
          <>
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

function MetricPanel({
  title,
  summary,
  tone,
  items,
}: {
  title: string;
  summary: string;
  tone: "ok" | "error" | "neutral";
  items: Array<[string, string]>;
}) {
  const borderClass =
    tone === "ok"
      ? "border-emerald-800"
      : tone === "error"
        ? "border-rose-800"
        : "border-slate-800";

  return (
    <div className={`rounded-2xl border bg-slate-900 p-5 ${borderClass}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-bold">{title}</h3>
        <StatusBadge label={summary} tone={tone} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
