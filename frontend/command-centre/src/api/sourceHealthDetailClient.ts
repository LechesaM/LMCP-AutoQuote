import { axiosAdapter } from "./axiosAdapter";
import { normalizeSourceHealthDetails } from "./normalize";
import useSourceHealthStore from "../store/sourceHealthStore";

export async function fetchSourceHealthDetails() {
  const remote = await axiosAdapter("/operations/source-health-details");
  if (remote?.rows) {
    return normalizeSourceHealthDetails(remote);
  }
  const snapshot = useSourceHealthStore.getState();
  return normalizeSourceHealthDetails({
    status: "ok",
    generatedAt: snapshot.lastUpdatedAt || new Date().toISOString(),
    dataSource: snapshot.dataSource || "static_seed",
    rows: snapshot.sources.map((source) => ({
      sourceId: source.id,
      name: source.name,
      sourceTier: source.tier,
      parserType: "html",
      status: source.status,
      lastSuccess: "",
      lastFailure: "",
      failureCount: Number(source.failureCount || 0),
      averageResponseTimeMs: 0,
      parserFailureRate: Number(source.parserFailureRate || 0),
      healthState: source.status,
    })),
    tierBreakdown: snapshot.sources.reduce((acc, item) => {
      acc[item.tier] = (acc[item.tier] || 0) + 1;
      return acc;
    }, {}),
    summary: {
      totalSources: snapshot.summary.totalSources || snapshot.sources.length,
      healthySources: snapshot.summary.healthySources || 0,
      degradedSources: snapshot.summary.degradedSources || 0,
      failingSources: snapshot.summary.failingSources || 0,
      disabledSources: snapshot.summary.disabledSources || 0,
    },
  });
}
