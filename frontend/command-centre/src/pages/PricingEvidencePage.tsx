import { useEffect, useMemo, useState } from "react";
import SectionPanel from "../components/ui/SectionPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import DataTable from "../components/ui/DataTable.tsx";
import StateBadge from "../components/ui/StateBadge.tsx";
import RFQPricingEvidencePanel from "../components/workflows/RFQPricingEvidencePanel.tsx";
import { usePricingEvidence } from "../hooks/usePricingEvidence";

export default function PricingEvidencePage() {
  const pricing = usePricingEvidence();
  const [selectedTenderId, setSelectedTenderId] = useState(pricing.pricingEvidenceRows[0]?.tenderId || "");

  const selectedRow = useMemo(
    () => pricing.pricingEvidenceRows.find((row) => row.tenderId === selectedTenderId) || pricing.pricingEvidenceRows[0] || null,
    [pricing.pricingEvidenceRows, selectedTenderId],
  );

  useEffect(() => {
    if (!selectedTenderId && pricing.pricingEvidenceRows.length) {
      setSelectedTenderId(pricing.pricingEvidenceRows[0].tenderId);
    }
  }, [pricing.pricingEvidenceRows, selectedTenderId]);

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Pricing Evidence</h2>
        <p className="mt-2 text-sm text-slate-400">Supplier quote completeness, defensibility and traceability remain visible and advisory only.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Completeness" value={pricing.summary.supplier_quote_completeness_average || 0} tone="cyan" />
        <TelemetryStat label="Defensibility" value={pricing.summary.pricing_defensibility_average || 0} tone="green" />
        <TelemetryStat label="Confidence" value={pricing.summary.pricing_confidence_average || 0} tone="amber" />
        <TelemetryStat label="Stale Quotes" value={pricing.summary.stale_quote_count || 0} tone="red" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_.9fr]">
        <SectionPanel title="Pricing Evidence Rows" description="Read-only evidence, confidence and traceability summaries." state={pricing.loading ? "loading" : pricing.error ? "error" : pricing.dataSource !== "runtime" ? "stale" : "ready"}>
          <div className="mb-3 flex items-center gap-2">
            <StateBadge state={pricing.dataSource === "runtime" ? "ready" : "stale"} />
            <div className="text-xs uppercase tracking-[.22em] text-slate-500">Last updated {pricing.generatedAt || "unknown"}</div>
          </div>
          <DataTable
            columns={[
              { key: "title", header: "RFQ", sortable: true, render: (row) => <div className="font-bold text-white">{row.title}</div>, sortValue: (row) => row.title, className: "min-w-[220px]" },
              { key: "supplierEvidenceScore", header: "Evidence", sortable: true, render: (row) => row.supplierEvidenceScore, sortValue: (row) => row.supplierEvidenceScore },
              { key: "pricingDefensibilityScore", header: "Defensibility", sortable: true, render: (row) => row.pricingDefensibilityScore, sortValue: (row) => row.pricingDefensibilityScore },
              { key: "pricingConfidence", header: "Confidence", sortable: true, render: (row) => row.pricingConfidence, sortValue: (row) => row.pricingConfidence },
              { key: "quoteAgeDays", header: "Age", sortable: true, render: (row) => `${row.quoteAgeDays} days`, sortValue: (row) => row.quoteAgeDays },
              { key: "riskLevel", header: "Risk", sortable: true, render: (row) => row.riskLevel, sortValue: (row) => row.riskLevel },
            ]}
            defaultSortKey="pricingConfidence"
            emptyMessage="No pricing evidence rows visible."
            loading={pricing.loading}
            onRowClick={(row) => setSelectedTenderId(row.tenderId)}
            pageSize={7}
            rowKey={(row) => row.tenderId}
            rows={pricing.pricingEvidenceRows || []}
            searchAccessor={(row) => `${row.title} ${row.tenderId} ${row.riskLevel}`}
            searchPlaceholder="Search pricing evidence"
            stale={pricing.dataSource !== "runtime"}
            title="Pricing Evidence"
          />
        </SectionPanel>

        <RFQPricingEvidencePanel
          pricingEvidence={selectedRow || {}}
          pricingTraceability={selectedRow || {}}
          row={selectedRow || {}}
          pricingValidation={{
            validation_errors: pricing.pricingAnomalies?.length ? pricing.pricingAnomalies.map((item) => `${item.name}: ${item.count}`) : [],
            validation_warnings: pricing.summary.stale_quote_count ? ["Stale quote evidence detected"] : [],
          }}
        />
      </div>

      <SectionPanel title="Pricing Anomalies" description="Counts of advisory pricing concerns visible in telemetry." state={pricing.loading ? "loading" : pricing.error ? "error" : "ready"}>
        <div className="grid gap-3 md:grid-cols-3">
          {pricing.pricingAnomalies.length ? (
            pricing.pricingAnomalies.map((anomaly) => (
              <div key={anomaly.name} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
                <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">{anomaly.name}</div>
                <div className="mt-2 text-3xl font-black text-white">{anomaly.count}</div>
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-400">No pricing anomalies recorded.</div>
          )}
        </div>
      </SectionPanel>
    </div>
  );
}
