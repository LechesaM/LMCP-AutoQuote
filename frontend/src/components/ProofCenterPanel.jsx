import React, { useEffect, useMemo, useState } from "react";
import {
  getProofCenter,
  scanProofCenter,
  proofDownloadUrl,
  proofScreenshotUrl,
} from "../services/proofCenterService";

function Badge({ children, tone = "neutral" }) {
  const classes = {
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warning: "bg-amber-100 text-amber-800 border-amber-200",
    danger: "bg-rose-100 text-rose-800 border-rose-200",
    neutral: "bg-slate-100 text-slate-700 border-slate-200",
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-semibold ${classes[tone] || classes.neutral}`}>
      {children}
    </span>
  );
}

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function ProofCenterPanel() {
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState({});
  const [query, setQuery] = useState("");
  const [submittedOnly, setSubmittedOnly] = useState(false);
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState("Loading proof center...");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const data = await getProofCenter(100, submittedOnly, query);
      setRecords(data.records || []);
      setSummary(data.summary || {});
      setStatus("Proof center loaded.");
    } catch (error) {
      setStatus(error.message || "Failed to load proof center.");
    } finally {
      setBusy(false);
    }
  }

  async function scanAndLoad() {
    setBusy(true);
    try {
      await scanProofCenter();
      const data = await getProofCenter(100, submittedOnly, query);
      setRecords(data.records || []);
      setSummary(data.summary || {});
      setStatus("Proof center scanned and refreshed.");
    } catch (error) {
      setStatus(error.message || "Failed to scan proof center.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submittedOnly]);

  const selectedRecord = useMemo(() => {
    if (!selected) return null;
    return records.find((r) => r.record_id === selected) || null;
  }, [selected, records]);

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Production Proof Center</h2>
          <p className="text-sm text-slate-500">
            Submission proof JSON, screenshots, and portal audit records.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={scanAndLoad}
            disabled={busy}
            className="rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Working..." : "Scan proofs"}
          </button>

          <button
            onClick={load}
            disabled={busy}
            className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Total proofs</div>
          <div className="text-2xl font-bold">{summary.proof_total ?? 0}</div>
        </div>
        <div className="rounded-2xl border bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Submitted</div>
          <div className="text-2xl font-bold text-emerald-700">{summary.submitted_total ?? 0}</div>
        </div>
        <div className="rounded-2xl border bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Pending / unverified</div>
          <div className="text-2xl font-bold text-amber-700">{summary.pending_or_unverified_total ?? 0}</div>
        </div>
        <div className="rounded-2xl border bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Screenshots</div>
          <div className="text-2xl font-bold">{summary.screenshot_total ?? 0}</div>
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") load();
          }}
          placeholder="Search RFQ, quote, portal, status..."
          className="min-w-0 flex-1 rounded-2xl border border-slate-300 px-4 py-2 text-sm outline-none focus:border-slate-700"
        />
        <label className="flex items-center gap-2 rounded-2xl border border-slate-200 px-3 py-2 text-sm">
          <input
            type="checkbox"
            checked={submittedOnly}
            onChange={(e) => setSubmittedOnly(e.target.checked)}
          />
          Submitted only
        </label>
        <button
          onClick={load}
          disabled={busy}
          className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold"
        >
          Search
        </button>
      </div>

      <div className="mb-3 text-xs text-slate-500">{status}</div>

      <div className="overflow-hidden rounded-2xl border border-slate-200">
        <div className="max-h-[440px] overflow-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">RFQ</th>
                <th className="px-3 py-3">Quote</th>
                <th className="px-3 py-3">Created</th>
                <th className="px-3 py-3">Proof</th>
                <th className="px-3 py-3">Screenshots</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr
                  key={record.record_id}
                  className="border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="px-3 py-3">
                    <Badge tone={record.submitted ? "success" : "warning"}>
                      {record.submission_status || "unknown"}
                    </Badge>
                  </td>
                  <td className="max-w-[260px] px-3 py-3 font-semibold text-slate-800">
                    <button
                      className="text-left hover:underline"
                      onClick={() => setSelected(record.record_id)}
                    >
                      {record.buyer_rfq_number}
                    </button>
                  </td>
                  <td className="px-3 py-3 text-slate-600">{record.quote_number}</td>
                  <td className="px-3 py-3 text-slate-500">{formatDate(record.created_at || record.submitted_at)}</td>
                  <td className="px-3 py-3">
                    <a
                      href={proofDownloadUrl(record.record_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white"
                    >
                      Download JSON
                    </a>
                  </td>
                  <td className="px-3 py-3">
                    {record.screenshot_count > 0 ? (
                      <a
                        href={proofScreenshotUrl(record.record_id, 0)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
                      >
                        View screenshot
                      </a>
                    ) : (
                      <span className="text-xs text-slate-400">No screenshot</span>
                    )}
                  </td>
                </tr>
              ))}

              {records.length === 0 && (
                <tr>
                  <td colSpan="6" className="px-3 py-8 text-center text-slate-500">
                    No proof records found. Run “Scan proofs”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRecord && (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-2 flex items-start justify-between gap-3">
            <div>
              <h3 className="font-bold text-slate-900">{selectedRecord.buyer_rfq_number}</h3>
              <p className="text-sm text-slate-500">{selectedRecord.quote_number}</p>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="rounded-xl border border-slate-300 px-3 py-1 text-xs font-semibold"
            >
              Close
            </button>
          </div>

          <div className="grid gap-2 text-sm md:grid-cols-2">
            <div><strong>Status:</strong> {selectedRecord.submission_status}</div>
            <div><strong>Submitted:</strong> {selectedRecord.submitted ? "Yes" : "No"}</div>
            <div><strong>Portal:</strong> {selectedRecord.portal_domain || "—"}</div>
            <div><strong>Screenshots:</strong> {selectedRecord.screenshot_count || 0}</div>
            <div className="md:col-span-2"><strong>Proof file:</strong> {selectedRecord.proof_file}</div>
            {selectedRecord.verification_note && (
              <div className="md:col-span-2"><strong>Verification:</strong> {selectedRecord.verification_note}</div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
