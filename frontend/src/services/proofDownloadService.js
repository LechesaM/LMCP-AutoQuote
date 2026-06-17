const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function buildBackendFileUrl(path) {
  if (!path) return "";

  let clean = String(path).trim();

  if (clean.startsWith("http://") || clean.startsWith("https://")) {
    return clean;
  }

  clean = clean.replace(/^\/app\//, "");
  clean = clean.replace(/^\.\//, "");
  clean = clean.replace(/^\/+/, "");

  return `${API_BASE}/${clean}`;
}

export async function generateProofForRow(row) {
  const params = new URLSearchParams();

  if (row?.buyer_rfq_number) params.set("buyer_rfq_number", row.buyer_rfq_number);
  if (row?.quote_number) params.set("quote_number", row.quote_number);
  if (row?.submitted_at) params.set("submitted_at", row.submitted_at);

  const res = await fetch(`${API_BASE}/submission-proof/generate?${params.toString()}`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error("Could not generate proof PDF");
  }

  return res.json();
}

export async function openProofForRow(row) {
  const existingPath =
    row?.proof_pdf_path ||
    row?.proof_path ||
    row?.submission_pack?.proof_pdf_path ||
    row?.auto_proof_result?.proof_pdf_path ||
    row?.proof_result?.proof_pdf_path;

  if (existingPath) {
    const url = buildBackendFileUrl(existingPath);
    window.open(url, "_blank", "noopener,noreferrer");
    return { opened: true, url, generated: false };
  }

  const generated = await generateProofForRow(row);
  const proofPath = generated?.proof_pdf_path;

  if (!proofPath) {
    throw new Error("Proof generated but no PDF path was returned");
  }

  const url = buildBackendFileUrl(proofPath);
  window.open(url, "_blank", "noopener,noreferrer");
  return { opened: true, url, generated: true };
}
