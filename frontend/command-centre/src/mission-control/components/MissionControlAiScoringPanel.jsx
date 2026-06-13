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

export default function MissionControlAiScoringPanel({ aiScoring = {} }) {
  const summary = aiScoring.summary || {};
  const items = Array.isArray(aiScoring.items) ? aiScoring.items.slice(0, 5) : [];
  const status = String(aiScoring.status || "not_configured").toLowerCase();

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

      <div className="ai-top-list">
        <div className="ai-top-head">
          <span>Top 5 Opportunities</span>
          <span>Title / Score / Estimated Profit / Recommended Action</span>
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
                {items.map((item) => (
                  <tr key={item.rfqId || item.title}>
                    <td>
                      <strong>{item.title || "Untitled RFQ"}</strong>
                      <small>{item.province || "Unknown"} · {item.buyer || "—"} · {item.category || "—"}</small>
                    </td>
                    <td><b>{Number(item.score || 0).toFixed(1)}</b></td>
                    <td>{formatMoney(item.estimatedProfit || 0)}</td>
                    <td><ActionChip value={item.recommendedAction} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="ai-empty">No scored opportunities available.</div>
        )}
      </div>
    </section>
  );
}
