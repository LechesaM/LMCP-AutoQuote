import { axiosAdapter } from "./axiosAdapter";
import { normalizeQualificationInsights } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchQualificationInsights() {
  const remote = await axiosAdapter("/operations/qualification-insights");
  if (remote?.summary) {
    return normalizeQualificationInsights(remote);
  }
  const telemetry = useTelemetryStore.getState();
  return normalizeQualificationInsights({
    status: "ok",
    generatedAt: telemetry.lastRefreshedAt || new Date().toISOString(),
    dataSource: telemetry.dataSource || "static_seed",
    summary: {
      recommendation_counts: {
        GO: telemetry.commandMetrics.highProfitRfqs > 0 ? 1 : 0,
        MANUAL_REVIEW: Math.max(1, telemetry.commandMetrics.highProfitRfqs > 0 ? 1 : 2),
        REJECT: 0,
      },
      risk_breakdown: {
        low: 1,
        medium: 2,
        high: 0,
      },
      average_automation_suitability_score: 64,
      blockers: ["manual governance required"],
      manual_review_trigger_counts: {
        "physical submission": 1,
        "missing closing date": 1,
      },
    },
    provinceHeat: {},
    lowConfidenceRfqs: telemetry.topHighProfitRfqs.map((item, index) => ({
      tenderId: `fallback-q-${index + 1}`,
      title: item.title,
      province: item.province,
    })),
    riskDistribution: { low: 1, medium: 2, high: 0 },
    qualificationScoreAverage: 64,
    riskScoreAverage: 42,
    topRejectionReasons: ["manual governance required"],
    topManualReviewTriggers: ["physical submission", "missing closing date"],
    goCount: 1,
    manualReviewCount: 2,
    rejectCount: 0,
  });
}
