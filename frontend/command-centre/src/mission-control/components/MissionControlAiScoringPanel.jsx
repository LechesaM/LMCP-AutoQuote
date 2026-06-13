import { useEffect, useState } from "react";
import "./MissionControlAiScoringPanel.css";

function formatMoney(value) {
  const n = Number(value || 0);
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0,
  }).format(n);
}

function toneForAction(action) {
  const value = String(action || "").toLowerCase();
  if (value === "quote") return "good";
  if (value === "review") return "blue";
  if (value === "needs_human_check") return "gold";
  if (value === "skip") return "bad";
  return "";
}

function ActionChip({ value }) {
  const tone = toneForAction(value);
  return <span className={`ai-chip ${tone}`}>{value || "n/a"}</span>;
}

function stringValue(value, fallback = "—") {
  if (value == null || value === "") return fallback;
  return String(value);
}

function arrayValue(value) {
  if (Array.isArray(value)) return value.map((item) => stringValue(item, "")).filter(Boolean);
  if (typeof value === "string") return value.split(/\r?\n|•|,|;/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function formatPercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(1)}%`;
}

function normalizeScoringItem(item = {}, index = 0) {
  return {
    id: stringValue(item.rfqId || item.rfq_id || item.id || item.reference || `scoring-item-${index}`, `scoring-item-${index}`),
    title: stringValue(item.title || item.name || item.subject, "Untitled RFQ"),
    rfqId: stringValue(item.rfqId || item.rfq_id || item.id || item.reference || item.buyerRfqNumber || item.buyer_rfq_number, "—"),
    buyer: stringValue(item.buyer || item.buyerName || item.buyer_name || item.organisation || item.department, "—"),
    province: stringValue(item.province || item.buyerProvince || item.buyer_province || item.location || item.region, "—"),
    category: stringValue(item.category || item.categoryName || item.category_name, "—"),
    score: Number(item.score ?? item.priorityScore ?? item.priority_score ?? 0),
    priority: stringValue(item.priority || item.priorityGroup || item.priority_group || item.priorityLabel || "—", "—"),
    estimatedProfit: Number(item.estimatedProfit ?? item.estimated_profit ?? item.profit ?? 0),
    marginEstimate: Number(item.marginEstimate ?? item.estimatedMargin ?? item.estimated_margin ?? item.margin ?? NaN),
    recommendedAction: stringValue(item.recommendedAction || item.recommendation || item.nextAction || item.action, "n/a"),
    reasons: arrayValue(item.reasons || item.reason || item.recommendationReasons || item.recommendation_reasons),
    risks: arrayValue(item.risks || item.risk || item.riskFlags || item.risk_flags),
  };
}

export default function MissionControlAiScoringPanel({ aiScoring = {} }) {
  const summary = aiScoring.summary || {};
  const items = Array.isArray(aiScoring.items) ? aiScoring.items.slice(0, 5).map(normalizeScoringItem) : [];
  const status = String(aiScoring.status || "not_configured").toLowerCase();
  const [selectedId, setSelectedId] = useState(items[0]?.id || "");

  useEffect(() => {
    const hasSelection = items.some((item) => item.id === selectedId);
    if (!hasSelection) {
      setSelectedId(items[0]?.id || "");
    }
  }, [items, selectedId]);

  const selectedItem = items.find((item) => item.id === selectedId) || items[0] || null;

  return (
    <section className="card ai-scoring">
      <div className="card-head">
        <div>
          <h2>AI Scoring</h2>
          <span>Read-only contract from snapshot.aiScoring</span>
        </div>
        <span className={`ai-status ${status}`}>{status.replaceAll("_", " ")}</span>
      </div>

      <div className="ai-summary-grid">
        <div className="ai-summary-item">
          <span>Scored Opportunities</span>
          <b>{Number(summary.scoredCount || 0)}</b>
        </div>
        <div className="ai-summary-item">
          <span>High Priority</span>
          <b>{Number(summary.highPriorityCount || 0)}</b>
        </div>
        <div className="ai-summary-item">
          <span>Average Score</span>
          <b>{Number(summary.averageScore || 0).toFixed(1)}</b>
        </div>
      </div>

      <div className="ai-drilldown-grid">
        <div className="ai-top-list">
          <div className="ai-top-head">
            <span>Top 5 Opportunities</span>
            <span>Click an opportunity to inspect the score</span>
          </div>

          {items.length ? (
            <div className="ai-table-wrap">
              <table className="ai-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Score</th>
                    <th>Estimated Profit</th>
                    <th>Recommended Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const selected = item.id === selectedItem?.id;
                    return (
                      <tr
                        key={item.id}
                        className={selected ? "selected" : ""}
                        role="button"
                        tabIndex={0}
                        aria-pressed={selected}
                        onClick={() => setSelectedId(item.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedId(item.id);
                          }
                        }}
                      >
                        <td>
                          <strong>{item.title}</strong>
                          <small>{item.province} · {item.buyer} · {item.category}</small>
                        </td>
                        <td><b>{Number(item.score || 0).toFixed(1)}</b></td>
                        <td>{formatMoney(item.estimatedProfit || 0)}</td>
                        <td><ActionChip value={item.recommendedAction} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ai-empty">No scored opportunities available.</div>
          )}
        </div>

        <aside className="ai-detail-card" aria-label="AI scoring drill-down">
          <div className="ai-detail-head">
            <div>
              <span className="ai-detail-eyebrow">Drill-Down</span>
              <h3>{selectedItem?.title || "Select an opportunity"}</h3>
            </div>
            {selectedItem ? <ActionChip value={selectedItem.recommendedAction} /> : null}
          </div>

          {selectedItem ? (
            <div className="ai-detail-body">
              <div className="ai-detail-meta">
                <div><span>RFQ ID</span><b>{selectedItem.rfqId}</b></div>
                <div><span>Buyer</span><b>{selectedItem.buyer}</b></div>
                <div><span>Province</span><b>{selectedItem.province}</b></div>
                <div><span>Category</span><b>{selectedItem.category}</b></div>
              </div>

              <div className="ai-detail-metrics">
                <div>
                  <span>Score</span>
                  <b>{Number(selectedItem.score || 0).toFixed(1)}</b>
                </div>
                <div>
                  <span>Priority</span>
                  <b>{selectedItem.priority}</b>
                </div>
                <div>
                  <span>Estimated Profit</span>
                  <b>{formatMoney(selectedItem.estimatedProfit || 0)}</b>
                </div>
                <div>
                  <span>Margin Estimate</span>
                  <b>{formatPercent(selectedItem.marginEstimate)}</b>
                </div>
              </div>

              <div className="ai-detail-section">
                <h4>Recommended Action</h4>
                <p>{selectedItem.recommendedAction}</p>
              </div>

              <div className="ai-detail-section">
                <h4>Reasons</h4>
                {selectedItem.reasons.length ? (
                  <ul>
                    {selectedItem.reasons.slice(0, 6).map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                ) : (
                  <p>No reasons provided in snapshot.aiScoring.items.</p>
                )}
              </div>

              <div className="ai-detail-section">
                <h4>Risks</h4>
                {selectedItem.risks.length ? (
                  <ul>
                    {selectedItem.risks.slice(0, 6).map((risk) => <li key={risk}>{risk}</li>)}
                  </ul>
                ) : (
                  <p>No risks provided in snapshot.aiScoring.items.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="ai-empty ai-empty-detail">Select a scored opportunity to inspect its decision context.</div>
          )}
        </aside>
      </div>
    </section>
  );
}
