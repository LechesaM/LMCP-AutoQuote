import { useEffect, useState } from "react";
import { useRFQOperations } from "../hooks/useRFQOperations";
import TelemetrySummary from "../components/telemetry/TelemetrySummary.tsx";
import AnalyticsPanel from "../components/charts/AnalyticsPanel.tsx";
import RFQWorkflowTable from "../components/workflows/RFQWorkflowTable.tsx";
import RFQWorkflowDrawer from "../components/workflows/RFQWorkflowDrawer.tsx";
import RFQQualificationPanel from "../components/workflows/RFQQualificationPanel.tsx";
import RFQPricingEvidencePanel from "../components/workflows/RFQPricingEvidencePanel.tsx";
import RFQGovernancePanel from "../components/workflows/RFQGovernancePanel.tsx";
import OperationalAlertsPanel from "../components/workflows/OperationalAlertsPanel.tsx";
import SectionPanel from "../components/ui/SectionPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";

export default function RFQOperationsPage() {
  const { rows, summary, loading, refreshing, error, dataSource, getDetail } = useRFQOperations();
  const [selectedTenderId, setSelectedTenderId] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    if (!selectedTenderId && rows.length) {
      setSelectedTenderId(rows[0].tenderId);
    }
  }, [rows, selectedTenderId]);

  useEffect(() => {
    let active = true;
    const loadDetail = async () => {
      if (!selectedTenderId) {
        setDetail(null);
        return;
      }
      setDetailLoading(true);
      setDetailError("");
      try {
        const nextDetail = await getDetail(selectedTenderId);
        if (active) {
          setDetail(nextDetail);
        }
      } catch (exception) {
        if (active) {
          setDetailError(exception instanceof Error ? exception.message : "Unable to load RFQ detail");
        }
      } finally {
        if (active) {
          setDetailLoading(false);
        }
      }
    };
    loadDetail();
    return () => {
      active = false;
    };
  }, [selectedTenderId, getDetail]);

  return (
    <div className="space-y-6">
      <TelemetrySummary />
      <OperationalAlertsPanel />

      <div className="grid gap-6 xl:grid-cols-[1.55fr_.95fr]">
        <div className="space-y-6">
          <RFQWorkflowTable onSelectRFQ={setSelectedTenderId} selectedTenderId={selectedTenderId} />
          <AnalyticsPanel />
        </div>

        <div className="space-y-6">
          <SectionPanel title="Workflow Snapshot" description="Live versus fallback state for the current workflow view." state={loading ? "loading" : error ? "error" : refreshing ? "refreshing" : dataSource !== "runtime" ? "stale" : "ready"}>
            <div className="grid gap-3 md:grid-cols-2">
              <TelemetryStat label="GO" value={summary.go} tone="green" />
              <TelemetryStat label="Manual Review" value={summary.manualReview} tone="amber" />
              <TelemetryStat label="Reject" value={summary.reject} tone="red" />
              <TelemetryStat label="Total" value={summary.total} tone="cyan" />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
                Data source {dataSource || "runtime_fallback"}
              </div>
              <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
                {loading ? "Loading" : refreshing ? "Refreshing" : error ? "Error" : "Ready"}
              </div>
            </div>
          </SectionPanel>

          <RFQQualificationPanel qualification={detail?.qualificationSummary || detail?.qualification || {}} row={detail?.summary || {}} />
          <RFQPricingEvidencePanel pricingEvidence={detail?.pricingEvidence || {}} pricingValidation={detail?.pricingValidation || {}} pricingTraceability={detail?.pricingTraceability || {}} row={detail?.summary || {}} />
          <RFQGovernancePanel governanceSummary={detail?.governanceSummary || {}} />
        </div>
      </div>

      <RFQWorkflowDrawer open={Boolean(selectedTenderId)} detail={detail} error={detailError} loading={detailLoading} onClose={() => setSelectedTenderId("")} />
    </div>
  );
}
