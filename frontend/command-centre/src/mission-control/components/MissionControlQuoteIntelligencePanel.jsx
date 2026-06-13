import { useEffect, useState } from "react";
import "../mission-control-quote-intelligence.css";

function stringValue(value, fallback = "—") {
  if (value == null || value === "") return fallback;
  return String(value);
}

function formatCount(value, status) {
  if (String(status || "").toLowerCase() !== "configured") return "insufficient_history";
  const n = Number(value || 0);
  return Number.isFinite(n) ? String(n) : "—";
}

function findDetail(source, keys = []) {
  for (const key of keys) {
    if (Array.isArray(source?.[key]) || typeof source?.[key] === "string") return source[key];
    if (source?.[key] != null && typeof source[key] !== "object") return source[key];
  }
  return null;
}

function renderDetailValue(value) {
  if (Array.isArray(value)) {
    const normalized = value.map((item) => stringValue(item, "")).filter(Boolean);
    return normalized.length ? normalized.join(" · ") : "insufficient_history";
  }
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value || "insufficient_history";
  if (value == null) return "insufficient_history";
  return stringValue(value, "insufficient_history");
}

function metricForKey(quoteIntelligence = {}, key) {
  const status = String(quoteIntelligence.status || "insufficient_history").toLowerCase();
  if (key === "supplierCoverage") return formatCount(quoteIntelligence.supplierCoverage, status);
  if (key === "pricingFreshness") return formatCount(quoteIntelligence.pricingFreshness, status);
  if (key === "awardSignals") return formatCount(quoteIntelligence.awardSignals, status);
  if (key === "competitorSignals") return formatCount(quoteIntelligence.competitorSignals, status);
  return "—";
}

function detailConfig(quoteIntelligence, selectedKey) {
  const status = String(quoteIntelligence.status || "insufficient_history").toLowerCase();
  const sections = {
    supplierCoverage: {
      title: "Supplier Coverage",
      rows: [
        { label: "Suppliers tracked", value: findDetail(quoteIntelligence, ["supplierCoverageSuppliersTracked", "supplier_tracked", "suppliersTracked"]) },
        { label: "Provinces covered", value: findDetail(quoteIntelligence, ["supplierCoverageProvincesCovered", "provincesCovered", "coverageProvinces"]) },
        { label: "Categories covered", value: findDetail(quoteIntelligence, ["supplierCoverageCategoriesCovered", "categoriesCovered", "coverageCategories"]) },
      ],
    },
    pricingFreshness: {
      title: "Pricing Freshness",
      rows: [
        { label: "Current", value: findDetail(quoteIntelligence, ["pricingFreshnessCurrent", "current"]) },
        { label: "Stale", value: findDetail(quoteIntelligence, ["pricingFreshnessStale", "stale"]) },
        { label: "Missing", value: findDetail(quoteIntelligence, ["pricingFreshnessMissing", "missing"]) },
      ],
    },
    awardSignals: {
      title: "Award Signals",
      rows: [
        { label: "Recent awards detected", value: findDetail(quoteIntelligence, ["awardSignalsRecentAwardsDetected", "recentAwardsDetected", "recentAwards"]) },
        { label: "Top agencies", value: findDetail(quoteIntelligence, ["awardSignalsTopAgencies", "topAgencies"]) },
      ],
    },
    competitorSignals: {
      title: "Competitor Signals",
      rows: [
        { label: "Competitor activity", value: findDetail(quoteIntelligence, ["competitorSignalsActivity", "competitorActivity", "activity"]) },
        { label: "Award frequency", value: findDetail(quoteIntelligence, ["competitorSignalsAwardFrequency", "awardFrequency"]) },
      ],
    },
  };
  const selected = sections[selectedKey] || sections.supplierCoverage;
  return {
    ...selected,
    status,
  };
}

export default function MissionControlQuoteIntelligencePanel({ quoteIntelligence = {} }) {
  const metricKeys = ["supplierCoverage", "pricingFreshness", "awardSignals", "competitorSignals"];
  const [selectedKey, setSelectedKey] = useState("supplierCoverage");
  const status = String(quoteIntelligence.status || "insufficient_history").toLowerCase();

  useEffect(() => {
    setSelectedKey((current) => (metricKeys.includes(current) ? current : "supplierCoverage"));
  }, [quoteIntelligence]);

  const tiles = [
    { key: "supplierCoverage", label: "Supplier Coverage", value: metricForKey(quoteIntelligence, "supplierCoverage") },
    { key: "pricingFreshness", label: "Pricing Freshness", value: metricForKey(quoteIntelligence, "pricingFreshness") },
    { key: "awardSignals", label: "Award Signals", value: metricForKey(quoteIntelligence, "awardSignals") },
    { key: "competitorSignals", label: "Competitor Signals", value: metricForKey(quoteIntelligence, "competitorSignals") },
  ];
  const detail = detailConfig(quoteIntelligence, selectedKey);

  return (
    <section className="card quote-intelligence">
      <div className="card-head">
        <div>
          <h2>Quote Intelligence</h2>
          <span>Read-only intelligence summary from snapshot.quoteIntelligence</span>
        </div>
        <span className={`qi-status ${status}`}>{status.replaceAll("_", " ")}</span>
      </div>

      <div className="qi-summary-grid">
        {tiles.map((tile) => (
          <button
            key={tile.key}
            type="button"
            className={`qi-tile ${selectedKey === tile.key ? "selected" : ""}`}
            onClick={() => setSelectedKey(tile.key)}
          >
            <span>{tile.label}</span>
            <b>{tile.value}</b>
          </button>
        ))}
      </div>

      <div className="qi-detail">
        <div className="qi-detail-head">
          <div>
            <span className="qi-detail-eyebrow">Detail</span>
            <h3>{detail.title}</h3>
          </div>
          <span className="qi-detail-status">{detail.status}</span>
        </div>

        <div className="qi-detail-grid">
          {detail.rows.map((row) => (
            <div key={row.label} className="qi-detail-row">
              <span>{row.label}</span>
              <b>{renderDetailValue(row.value)}</b>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
