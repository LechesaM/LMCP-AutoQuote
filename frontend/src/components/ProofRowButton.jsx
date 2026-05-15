import { useState } from "react";
import { generateProofForSubmission, openProofFromResponse } from "../services/proofService";

export default function ProofRowButton({ submission, className = "" }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleClick = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await generateProofForSubmission(submission);
      openProofFromResponse(data);
    } catch (err) {
      console.error(err);
      setError("Proof failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`flex flex-col items-start gap-1 ${className}`}>
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
          loading
            ? "cursor-not-allowed bg-slate-700 text-slate-300"
            : "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30 hover:bg-emerald-500/25"
        }`}
      >
        {loading ? "Generating..." : "Proof PDF"}
      </button>

      {error && <span className="text-[11px] text-red-300">{error}</span>}
    </div>
  );
}
