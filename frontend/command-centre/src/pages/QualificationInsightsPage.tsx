import { useMemo } from "react";
import SectionPanel from "../components/ui/SectionPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import DataTable from "../components/ui/DataTable.tsx";
import { useQualificationInsights } from "../hooks/useQualificationInsights";
import { formatPercent } from "../utils/formatters";

export default function QualificationInsightsPage() {
  const insights = useQualificationInsights();

  const heatRows = useMemo(() => {
    return Object.entries(insights.provinceHeat || {}).map(([province, counts]) => ({
      province,
      go: Number(counts?.GO || 0),
      manualReview: Number(counts?.MANUAL_REVIEW || 0),
      reject: Number(counts?.REJECT || 0),
      total: Number(counts?.GO || 0) + Number(counts?.MANUAL_REVIEW || 0) + Number(counts?.REJECT || 0),
    }));
  }, [insights.provinceHeat]);

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Qualification Insights</h2>
        <p className="mt-2 text-sm text-slate-400">Qualification outcomes, risk signals, and low-confidence RFQs are visible here as advisory telemetry.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        <TelemetryStat label="GO" value={insights.goCount} tone="green" />
        <TelemetryStat label="Manual Review" value={insights.manualReviewCount} tone="amber" />
        <TelemetryStat label="Reject" value={insights.rejectCount} tone="red" />
        <TelemetryStat label="Qual Score Avg" value={formatPercent(insights.qualificationScoreAverage)} tone="cyan" />
        <TelemetryStat label="Risk Avg" value={formatPercent(insights.riskScoreAverage)} tone="slate" />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionPanel title="Top Rejection Reasons" description="Why RFQs are held or rejected." state={insights.loading ? "loading" : insights.error ? "error" : insights.dataSource !== "runtime" ? "stale" : "ready"}>
          <div className="space-y-2">
            {(insights.topRejectionReasons || []).length ? (
              insights.topRejectionReasons.map((reason, index) => (
                <div key={`${reason}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
                  {reason}
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-400">No rejection reasons available.</div>
            )}
          </div>
        </SectionPanel>

        <SectionPanel title="Top Manual-Review Triggers" description="Signals that drive operator attention." state={insights.loading ? "loading" : insights.error ? "error" : insights.dataSource !== "runtime" ? "stale" : "ready"}>
          <div className="space-y-2">
            {(insights.topManualReviewTriggers || []).length ? (
              insights.topManualReviewTriggers.map((trigger, index) => (
                <div key={`${trigger}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
                  {trigger}
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-400">No manual-review triggers available.</div>
            )}
          </div>
        </SectionPanel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_.9fr]">
        <SectionPanel title="Province Qualification Heat" description="Province-level recommendation distribution." state={insights.loading ? "loading" : insights.error ? "error" : "ready"}>
          <div className="grid gap-3">
            {heatRows.length ? (
              heatRows.map((row) => (
                <div key={row.province} className="grid grid-cols-[140px_1fr_1fr_1fr_70px] items-center gap-3 rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
                  <div className="font-bold text-white">{row.province}</div>
                  <div>GO {row.go}</div>
                  <div>Manual {row.manualReview}</div>
                  <div>Reject {row.reject}</div>
                  <div className="text-right text-xs text-slate-500">{row.total}</div>
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-400">No province heat available.</div>
            )}
          </div>
        </SectionPanel>

        <SectionPanel title="Low Confidence RFQs" description="RFQs that remain low-confidence or require manual review." state={insights.loading ? "loading" : insights.error ? "error" : insights.dataSource !== "runtime" ? "stale" : "ready"}>
          <DataTable
            columns={[
              { key: "title", header: "RFQ", sortable: true, render: (row) => <div className="font-bold text-white">{row.title || row.tenderId || "Unknown RFQ"}</div>, sortValue: (row) => row.title || row.tenderId || "" },
              { key: "province", header: "Province", sortable: true, render: (row) => row.province || "Unknown", sortValue: (row) => row.province || "" },
              { key: "qualificationState", header: "State", sortable: true, render: (row) => row.qualificationState || row.recommendation || "MANUAL_REVIEW", sortValue: (row) => row.qualificationState || row.recommendation || "" },
            ]}
            defaultSortKey="title"
            emptyMessage="No low-confidence RFQs visible."
            loading={insights.loading}
            pageSize={5}
            rowKey={(row) => row.tenderId || row.title || row.province || "low-confidence"}
            rows={insights.lowConfidenceRfqs || []}
            searchAccessor={(row) => `${row.title || ""} ${row.province || ""} ${row.tenderId || ""}`}
            searchPlaceholder="Search low confidence RFQs"
            stale={insights.dataSource !== "runtime"}
            title="Low Confidence RFQs"
          />
        </SectionPanel>
      </div>
    </div>
  );
}
