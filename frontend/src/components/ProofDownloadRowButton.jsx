import { useState } from "react";
import { openProofForRow } from "../services/proofDownloadService";

export default function ProofDownloadRowButton({ row, className = "" }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleOpen = async () => {
    try {
      setBusy(true);
      setError("");
      await openProofForRow(row);
    } catch (err) {
      console.error(err);
      setError(err?.message || "Proof failed");
    } finally {
      setBusy(false);
    }
  };

  const hasProof =
    row?.proof_pdf_path ||
    row?.proof_path ||
    row?.submission_pack?.proof_pdf_path ||
    row?.auto_proof_result?.proof_pdf_path ||
    row?.proof_result?.proof_pdf_path;

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <button
        type="button"
        onClick={handleOpen}
        disabled={busy}
        className={`rounded-xl px-3 py-2 text-xs font-bold transition ${
          busy
            ? "cursor-not-allowed bg-slate-700 text-slate-300"
            : hasProof
              ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30 hover:bg-emerald-500/25"
              : "bg-amber-500/15 text-amber-300 ring-1 ring-amber-400/30 hover:bg-amber-500/25"
        }`}
      >
        {busy ? "Opening..." : hasProof ? "Download Proof" : "Generate Proof"}
      </button>
      {error && <span className="text-[11px] text-red-300">{error}</span>}
    </div>
  );
}
