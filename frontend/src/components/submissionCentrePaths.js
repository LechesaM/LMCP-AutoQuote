function hasText(value) {
  return String(value || "").trim().length > 0;
}

function queryWithReference(rfqReference) {
  const params = new URLSearchParams();
  if (hasText(rfqReference)) params.set("rfq_reference", String(rfqReference).trim());
  return params.toString();
}

export function submissionGatePath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = hasText(rfqReference) ? `?rfq_reference=${encodeURIComponent(String(rfqReference).trim())}` : "";
  return `/quote-compilation/submission-gate/${encodedPack}${query}`;
}

export function submissionGateSummaryPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/summary${query ? `?${query}` : ""}`;
}

export function submissionGateSummaryExportPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/summary.json${query ? `?${query}` : ""}`;
}

export function submissionChecklistPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const params = new URLSearchParams({ include_text: "true" });
  if (hasText(rfqReference)) params.set("rfq_reference", String(rfqReference).trim());
  return `/quote-compilation/submission-gate/${encodedPack}/checklist?${params.toString()}`;
}

export function submissionChecklistTxtPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/checklist.txt${query ? `?${query}` : ""}`;
}

export function submissionAuditLogPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/audit-log${query ? `?${query}` : ""}`;
}

export function submissionAuditExportPath(packId, rfqReference, extension) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/audit-log.${extension}${query ? `?${query}` : ""}`;
}

export function submissionEvidenceManifestPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/evidence-manifest${query ? `?${query}` : ""}`;
}

export function submissionEvidenceManifestExportPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/evidence-manifest.json${query ? `?${query}` : ""}`;
}

export function submissionManualCompletionPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/manual-completion`;
}

export function submissionManualCompletionExportPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/manual-completion.json`;
}

export function submissionProofPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/submission-proof`;
}

export function submissionProofExportPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/submission-proof.json`;
}

export function submissionAuditTrailPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/audit-trail`;
}

export function submissionAuditTrailExportPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/audit-trail.json`;
}

export function submissionReadinessChecklistPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/readiness-checklist${query ? `?${query}` : ""}`;
}

export function submissionReadinessChecklistExportPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/readiness-checklist.json${query ? `?${query}` : ""}`;
}

export function submissionEvidenceBundlePath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/evidence-bundle${query ? `?${query}` : ""}`;
}

export function submissionEvidenceBundleExportPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/evidence-bundle.json${query ? `?${query}` : ""}`;
}

export function submissionPrintableReportPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/printable-report${query ? `?${query}` : ""}`;
}

export function submissionPrintableReportHtmlPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/printable-report.html${query ? `?${query}` : ""}`;
}

export function submissionEvidenceSnapshotPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/evidence-snapshot${query ? `?${query}` : ""}`;
}

export function submissionEvidenceSnapshotExportPath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/evidence-snapshot.json${query ? `?${query}` : ""}`;
}

export function submissionComplianceArchivePath(packId, rfqReference) {
  const encodedPack = encodeURIComponent(packId);
  const query = queryWithReference(rfqReference);
  return `/quote-compilation/submission-gate/${encodedPack}/compliance-archive${query ? `?${query}` : ""}`;
}

export function submissionComplianceArchivesPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/compliance-archives`;
}

export function submissionComplianceArchiveLatestZipPath(packId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/compliance-archive/latest/bundle.zip`;
}

export function submissionComplianceArchiveZipPath(packId, archiveId) {
  return `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/compliance-archive/${encodeURIComponent(archiveId)}/bundle.zip`;
}
