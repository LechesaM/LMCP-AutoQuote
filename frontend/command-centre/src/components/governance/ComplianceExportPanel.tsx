import SectionPanel from "../ui/SectionPanel.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import ActionBadge from "../ui/ActionBadge.tsx";

export default function ComplianceExportPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const manifest = data?.exportBundle?.manifest || data?.regulatoryExport?.manifest || {};
  const files = Array.isArray(data?.exportBundle?.bundle?.audit_pack?.zip_manifest?.files)
    ? data.exportBundle.bundle.audit_pack.zip_manifest.files
    : Array.isArray(data?.regulatoryExport?.bundle?.audit_pack?.zip_manifest?.files)
      ? data.regulatoryExport.bundle.audit_pack.zip_manifest.files
      : [];
  return (
    <SectionPanel title="Compliance Export" description="Read-only export bundles for compliance and legal review." state={state}>
      <div className="flex flex-wrap items-center gap-2">
        <ActionBadge action={Boolean(manifest.exportSafe ?? manifest.export_safe ?? true) ? "export safe" : "export review"} tone={Boolean(manifest.exportSafe ?? manifest.export_safe ?? true) ? "green" : "amber"} />
        <ActionBadge action={Boolean(manifest.noSecrets ?? manifest.no_secrets ?? true) ? "no secrets" : "check redaction"} tone={Boolean(manifest.noSecrets ?? manifest.no_secrets ?? true) ? "cyan" : "red"} />
      </div>
      {files.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {files.map((file: any) => (
            <div key={file.name} className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="font-black text-white">{file.name}</div>
              <div className="mt-1 text-sm text-slate-400">{file.records} records</div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyTelemetryState title="No export manifest" description="The export bundle is available when the compliance API is connected." />
      )}
    </SectionPanel>
  );
}
