import { useEffect, useMemo, useState } from "react";

function formatDate(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString("en-ZA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function EventBadge({ type }) {
  const normalized = String(type || "unknown").toLowerCase();

  const palette =
    normalized === "submission_queued"
      ? "bg-amber-500/15 text-amber-300 border-amber-500/20"
      : normalized === "submission_dispatched"
      ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/20"
      : normalized === "submission_submitted"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
      : normalized === "submission_retrying"
      ? "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/20"
      : normalized === "submission_manual_action_required"
      ? "bg-orange-500/15 text-orange-300 border-orange-500/20"
      : normalized === "submission_failed"
      ? "bg-rose-500/15 text-rose-300 border-rose-500/20"
      : "bg-slate-500/15 text-slate-300 border-slate-500/20";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${palette}`}>
      {type || "unknown"}
    </span>
  );
}

export default function SubmissionOutcomeLivePanel() {
  const [events, setEvents] = useState([]);
  const [lastEventAt, setLastEventAt] = useState(null);

  // ✅ WebSocket events (existing behavior)
  useEffect(() => {
    function handleMessage(event) {
      const detail = event.detail || {};
      const payload = detail.payload || {};

      const resolvedType =
        payload?.type ||
        payload?.payload?.type ||
        detail?.payload?.type;

      const resolvedPayload = payload?.payload || payload || {};

      const allowed = new Set([
        "submission_queued",
        "submission_dispatched",
        "submission_submitted",
        "submission_retrying",
        "submission_manual_action_required",
        "submission_failed",
      ]);

      if (!allowed.has(resolvedType)) return;

      const item = {
        id:
          resolvedType +
          "-" +
          Date.now() +
          "-" +
          Math.random().toString(36).slice(2, 8),
        type: resolvedType,
        receivedAt: detail.receivedAt || new Date().toISOString(),
        source: payload?.source || "submission-pipeline",
        data: resolvedPayload,
      };

      setEvents((prev) => [item, ...prev].slice(0, 20));
      setLastEventAt(item.receivedAt);
    }

    window.addEventListener("lmcp-ws-message", handleMessage);
    return () => window.removeEventListener("lmcp-ws-message", handleMessage);
  }, []);

  // 🔥 STEP 8.2 — Sync with Run Cycle (visual refresh)
  useEffect(() => {
    const handler = () => {
      setLastEventAt(new Date().toISOString());
    };

    window.addEventListener("lmcp-refresh", handler);
    return () => window.removeEventListener("lmcp-refresh", handler);
  }, []);

  const stats = useMemo(() => {
    return {
      total: events.length,
      submitted: events.filter((e) => e.type === "submission_submitted").length,
      failed: events.filter((e) => e.type === "submission_failed").length,
      manual: events.filter((e) => e.type === "submission_manual_action_required").length,
    };
  }, [events]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-fuchsia-300">
            Step 15
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Submission Outcome Live Events</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Watches real-time submission status changes flowing through the websocket feed.
          </p>
        </div>

        <div className="rounded-full border border-fuchsia-500/20 bg-fuchsia-500/10 px-4 py-2 text-xs text-fuchsia-200">
          Last Event: {formatDate(lastEventAt)}
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Tracked Events</div>
          <div className="mt-2 text-2xl font-semibold">{stats.total}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Submitted</div>
          <div className="mt-2 text-2xl font-semibold">{stats.submitted}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Failed</div>
          <div className="mt-2 text-2xl font-semibold">{stats.failed}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Manual Action</div>
          <div className="mt-2 text-2xl font-semibold">{stats.manual}</div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {events.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
            No submission outcome websocket events received yet.
          </div>
        ) : (
          events.map((item) => (
            <article key={item.id} className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-3">
                    <EventBadge type={item.type} />
                    <span className="text-xs text-slate-400">{formatDate(item.receivedAt)}</span>
                  </div>

                  <h3 className="mt-3 text-base font-semibold text-white">
                    {item.data?.buyer_rfq_number || "Unknown RFQ"}
                  </h3>

                  <div className="mt-2 text-sm text-slate-300">
                    Quote: {item.data?.quote_number || "—"}
                  </div>
                  <div className="mt-1 text-sm text-slate-300">
                    Submission Channel: {item.data?.submission_channel || "—"}
                  </div>
                  <div className="mt-1 text-sm text-slate-300">
                    Stage: {item.data?.stage || "—"}
                  </div>
                  <div className="mt-1 text-sm text-slate-300">
                    Retry Count: {item.data?.retry_count ?? "—"}
                  </div>
                </div>
              </div>

              {item.data?.error_message && (
                <div className="mt-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {item.data.error_message}
                </div>
              )}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
