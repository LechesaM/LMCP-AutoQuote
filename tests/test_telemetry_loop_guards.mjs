import assert from "node:assert/strict";
import {
  sameRuntimeApiHealth,
  sameTelemetrySnapshot,
  sameTelemetryStatus,
} from "../frontend/command-centre/src/store/telemetryGuards.js";

const baseSnapshot = {
  commandMetrics: { totalHarvested: 120, eligibleRfqs: 48 },
  opportunityBreakdown: [{ name: "High Value", value: 12 }],
  provinceDistribution: [{ code: "GP", province: "Gauteng", rfqs: 18 }],
  recentAlerts: ["Telemetry temporarily unavailable"],
  topHighProfitRfqs: [{ title: "RFQ-1", province: "GP", value: "R10 000", profit: "R2 500" }],
  loading: false,
  refreshing: false,
  stale: true,
  error: "",
  dataSource: "runtime_fallback",
  lastRefreshedAt: "2026-05-20T00:00:00.000Z",
};

assert.equal(
  sameTelemetrySnapshot(baseSnapshot, { ...baseSnapshot }),
  true,
  "identical telemetry fallback snapshots should be treated as unchanged",
);

assert.equal(
  sameTelemetrySnapshot(baseSnapshot, { ...baseSnapshot, lastRefreshedAt: "2026-05-20T00:00:01.000Z" }),
  false,
  "changed fallback timestamps should be detected as a real update",
);

assert.equal(
  sameTelemetryStatus(
    { loading: false, refreshing: false, error: "", stale: true },
    { loading: false, refreshing: false, error: "", stale: true },
  ),
  true,
  "identical telemetry failure state should not trigger another store write",
);

assert.equal(
  sameTelemetryStatus(
    { loading: false, refreshing: false, error: "", stale: true },
    { loading: false, refreshing: false, error: "Unable to refresh telemetry", stale: true },
  ),
  false,
  "changed telemetry error state should still be detected",
);

assert.equal(
  sameRuntimeApiHealth(
    { status: "degraded", dataSource: "runtime_fallback", error: "API base URL is not configured", latencyMs: 0, lastCheckedAt: "2026-05-20T00:00:00.000Z", route: "/observability/uptime" },
    { status: "degraded", dataSource: "runtime_fallback", error: "API base URL is not configured", latencyMs: 0, lastCheckedAt: "2026-05-20T00:00:00.000Z", route: "/observability/uptime" },
  ),
  true,
  "identical runtime API health states should not trigger another update",
);

console.log("telemetry loop guard checks passed");
