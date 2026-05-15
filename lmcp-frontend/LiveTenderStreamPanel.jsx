kkkimport { useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function tryFetchJson(paths = []) {
  for (const path of paths) {
    try {
      const response = await fetch(`${API_BASE}${path}`);
      if (!response.ok) continue;
      const data = await response.json();
      return { ok: true, path, data };
    } catch (_) {}
  }
  return { ok: false, path: null, data: null };
}

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
  });
}

function pickItems(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.opportunities)) return payload.opportunities;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

export default function LiveTenderStreamPanel() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [endpoint, setEndpoint] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");

    const result = await tryFetchJson([
      "/opportunities",
      "/opportunities?limit=10",
      "/dashboard/summary",
    ]);

    if (!result.ok) {
      setItems([]);
      setEndpoint("");
      setError("Could not load live tenders from the backend yet.");
      setLoading(false);
      return;
    }

    const rows = pickItems(result.data).slice(0, 10);
    setItems(rows);
    setEndpoint(result.path || "");
    setLoading(false);
  }

  // ✅ Initial load
  useEffect(() => {
    load();
  }, []);

  // 🔥 STEP 8.1 — LISTEN FOR GLOBAL REFRESH
  useEffect(() => {
    const handler = () => {
      load();
    };

    window.addEventListener("lmcp-refresh", handler);

    return () => window.removeEventListener("lmcp-refresh", handler);
  }, []);

  const count = useMemo(() => items.length, [items]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-5 shadow-2xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-cyan-300">
            Live Tenders
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-white">Live Tender Stream</h2>
          <p className="mt-2 text-sm text-slate-400">
            Watches recent opportunities coming from your LMCP backend.
          </p>
        </div>

        <button
          onClick={load}
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
        >
          Refresh
        </button>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">API Base</div>
          <div className="mt-2 break-all text-sm text-white">{API_BASE}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Endpoint Used</div>
          <div className="mt-2 text-sm text-white">{endpoint || "—"}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Loaded Items</div>
          <div className="mt-2 text-2xl font-semibold text-white">{count}</div>
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      <div className="mt-6 space-y-3">
        {loading ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
            Loading live tenders...
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
            No live tender rows returned yet.
          </div>
        ) : (
          items.map((item, index) => (
            <article
              key={`${item?.id || item?.buyer_rfq_number || item?.title || "tender"}-${index}`}
              className="rounded-3xl border border-white/10 bg-white/5 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    {item?.title || item?.description || item?.buyer_rfq_number || `Opportunity ${index + 1}`}
                  </h3>
                  <div className="mt-2 text-sm text-slate-400">
                    Buyer: {item?.buyer_name || item?.organ_of_state || item?.department || "—"}
                  </div>
                  <div className="mt-1 text-sm text-slate-400">
                    RFQ: {item?.buyer_rfq_number || item?.tender_number || item?.reference || "—"}
                  </div>
                </div>

                <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-200">
                  {item?.status || "live"}
                </div>
              </div>

              <div className="mt-3 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
                <div>Province: {item?.province || item?.region || "—"}</div>
                <div>Category: {item?.category || item?.classification || "—"}</div>
                <div>Published: {formatDate(item?.published_at || item?.created_at || item?.date)}</div>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
