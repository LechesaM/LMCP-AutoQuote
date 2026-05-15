import { useEffect, useMemo, useState } from "react";
import ProofRowButton from "./ProofRowButton";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function formatMoney(value) {
  const amount = Number(value || 0);
  return amount.toLocaleString("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 2,
  });
}

function shortDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("en-ZA", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export default function SubmissionProofFeedPanel() {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({
    submitted: 0,
    failed: 0,
    total_profit: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadSubmissions = async () => {
    try {
      setLoading(true);
      setError("");

      const res = await fetch(`${API_BASE}/submission-history/recent-real?limit=20`);

      if (!res.ok) {
        throw new Error("Failed to load submission feed");
      }

      const data = await res.json();
      const rows = data?.items || data?.recent || data?.submissions || [];

      setItems(Array.isArray(rows) ? rows : []);
      setSummary({
        submitted: data?.submitted || 0,
        failed: data?.failed || 0,
        total_profit: data?.total_profit || 0,
      });
    } catch (err) {
      console.error(err);
      setError("Could not load live submission proof feed.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSubmissions();
    const timer = setInterval(loadSubmissions, 30000);
    return () => clearInterval(timer);
  }, []);

  const hasRows = useMemo(() => items.length > 0, [items]);

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/20">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-emerald-300">
            Submission Proofs
          </p>
          <h2 className="mt-1 text-xl font-bold text-white">
            Proof per Submission Row
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Generate an audit proof PDF directly from each submitted RFQ record.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-2xl bg-slate-950/70 px-4 py-3 ring-1 ring-slate-800">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Submitted</p>
            <p className="text-lg font-bold text-emerald-300">{summary.submitted}</p>
          </div>
          <div className="rounded-2xl bg-slate-950/70 px-4 py-3 ring-1 ring-slate-800">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Failed</p>
            <p className="text-lg font-bold text-red-300">{summary.failed}</p>
          </div>
          <div className="rounded-2xl bg-slate-950/70 px-4 py-3 ring-1 ring-slate-800">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Profit</p>
            <p className="text-lg font-bold text-white">{formatMoney(summary.total_profit)}</p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={loadSubmissions}
          className="rounded-xl bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
        >
          Refresh
        </button>
      </div>

      {loading && (
        <div className="mt-4 rounded-2xl bg-slate-950/60 p-4 text-sm text-slate-400">
          Loading submission proof feed...
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {!loading && !error && !hasRows && (
        <div className="mt-4 rounded-2xl bg-slate-950/60 p-4 text-sm text-slate-400">
          No submissions found yet.
        </div>
      )}

      {!loading && !error && hasRows && (
        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-800">
          <div className="hidden grid-cols-[1.1fr_1fr_0.8fr_0.8fr_0.7fr] gap-3 bg-slate-950/80 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 md:grid">
            <div>RFQ / Buyer</div>
            <div>Quote / Recipient</div>
            <div>Status</div>
            <div>Profit</div>
            <div>Proof</div>
          </div>

          <div className="divide-y divide-slate-800">
            {items.map((item, index) => (
              <div
                key={`${item.buyer_rfq_number || "rfq"}-${item.quote_number || "quote"}-${item.submitted_at || index}`}
                className="grid gap-3 bg-slate-900/60 px-4 py-4 text-sm md:grid-cols-[1.1fr_1fr_0.8fr_0.8fr_0.7fr] md:items-center"
              >
                <div>
                  <p className="font-semibold text-white">
                    {item.buyer_rfq_number || "UNKNOWN RFQ"}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {item.buyer_name || "Unknown buyer"}
                  </p>
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                    {item.title || "Submitted RFQ"}
                  </p>
                </div>

                <div>
                  <p className="font-medium text-slate-200">
                    {item.quote_number || "No quote number"}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {item.recipient_email || "No recipient"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {shortDate(item.submitted_at)}
                  </p>
                </div>

                <div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      String(item.status || item.submission_status).toLowerCase() === "submitted"
                        ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30"
                        : "bg-red-500/15 text-red-300 ring-1 ring-red-400/30"
                    }`}
                  >
                    {item.status || item.submission_status || "unknown"}
                  </span>
                </div>

                <div>
                  <p className="font-semibold text-white">
                    {formatMoney(item.total_profit)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Incl VAT {formatMoney(item.total_sell_incl_vat)}
                  </p>
                </div>

                <ProofRowButton submission={item} />
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
