const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function toRuntimeUrl(path) {
  if (!path) return "";

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  let clean = String(path).trim();

  if (clean.startsWith("/app/")) {
    clean = clean.replace("/app/", "");
  }

  if (clean.startsWith("./")) {
    clean = clean.slice(2);
  }

  if (clean.startsWith("/")) {
    clean = clean.slice(1);
  }

  return `${API_BASE}/${clean}`;
}

export async function generateLatestProof() {
  const res = await fetch(`${API_BASE}/submission-proof/latest`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error("Failed to generate latest proof");
  }

  return res.json();
}

export async function generateProofForSubmission(submission) {
  const params = new URLSearchParams();

  if (submission?.buyer_rfq_number) {
    params.set("buyer_rfq_number", submission.buyer_rfq_number);
  }

  if (submission?.quote_number) {
    params.set("quote_number", submission.quote_number);
  }

  if (submission?.submitted_at) {
    params.set("submitted_at", submission.submitted_at);
  }

  const res = await fetch(`${API_BASE}/submission-proof/generate?${params.toString()}`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error("Failed to generate proof for submission");
  }

  return res.json();
}

export function openProofFromResponse(data) {
  const proofPath = data?.proof_pdf_path;

  if (!proofPath) {
    throw new Error("No proof PDF path returned");
  }

  const url = toRuntimeUrl(proofPath);
  window.open(url, "_blank", "noopener,noreferrer");
  return url;
}
