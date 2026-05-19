import { provinceDistribution } from "../data/harvestedRfqs";

export function buildProvinceSummaryRows() {
  return provinceDistribution.map((row) => ({
    ...row,
    eligibleRate: row.rfqs ? Math.round((row.eligible / row.rfqs) * 1000) / 10 : 0,
  }));
}

export function buildTelemetryHighlights(metrics) {
  return [
    { label: "Harvested RFQs", value: metrics.totalHarvested },
    { label: "Eligible RFQs", value: metrics.eligibleRfqs },
    { label: "Average Margin", value: metrics.avgMargin },
  ];
}
