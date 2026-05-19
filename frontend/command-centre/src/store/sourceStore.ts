import { provinceDistribution } from "../data/harvestedRfqs";

export function getSourceHealthSnapshot() {
  return provinceDistribution.map((row) => ({
    id: row.code,
    name: row.province,
    tier: row.rfqs > 150 ? "Tier 1" : row.rfqs > 80 ? "Tier 2" : "Tier 3",
    active: row.eligible > 20,
    eligible: row.eligible,
    total: row.rfqs,
  }));
}
