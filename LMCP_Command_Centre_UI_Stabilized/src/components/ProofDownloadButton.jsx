import { useState } from "react";
import { generateLatestProof } from "../services/proofService";

export default function ProofDownloadButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleGenerate = async () => {
    try {
      setLoading(true);
      setMessage("");

      const data = await generateLatestProof();

      if (data.proof_pdf_path) {
        setMessage("Proof generated");

        // 🔥 Convert backend path → frontend accessible path
        const filePath = data.proof_pdf_path.replace("runtime/", "");

        // Open file in browser
        window.open(`http://localhost:8000/${filePath}`, "_blank");
      } else {
        setMessage("No proof returned");
      }
    } catch (err) {
      console.error(err);
      setMessage("Failed to generate proof");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 p-4 rounded-2xl shadow">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">
            Proof of Submission
          </h3>
          <p className="text-xs text-slate-400">
            Generate and download latest proof
          </p>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className={`px-4 py-2 rounded-xl text-sm font-medium ${
            loading
              ? "bg-slate-600 cursor-not-allowed"
              : "bg-green-600 hover:bg-green-700"
          }`}
        >
          {loading ? "Generating..." : "Download Proof"}
        </button>
      </div>

      {message && (
        <p className="text-xs text-slate-400 mt-2">{message}</p>
      )}
    </div>
  );
}
