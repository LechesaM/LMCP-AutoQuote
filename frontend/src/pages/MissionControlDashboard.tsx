export default function MissionControlDashboard() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0f172a",
        color: "white",
        padding: "32px",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <h1 style={{ fontSize: "40px", marginBottom: "12px" }}>
          LMCP Mission Control Dashboard
        </h1>

        <p style={{ fontSize: "18px", color: "#cbd5e1", marginBottom: "32px" }}>
          Autonomous Tender Engine command center
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: "16px",
            marginBottom: "24px",
          }}
        >
          {[
            ["Total Opportunities", "121"],
            ["Relevant RFQs", "68"],
            ["Quotes Created", "19"],
            ["Emails Sent", "6"],
          ].map(([title, value]) => (
            <div
              key={title}
              style={{
                background: "#1e293b",
                borderRadius: "16px",
                padding: "20px",
                border: "1px solid #334155",
              }}
            >
              <div style={{ color: "#94a3b8", fontSize: "14px" }}>{title}</div>
              <div style={{ fontSize: "32px", fontWeight: "bold", marginTop: "8px" }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        <div
          style={{
            background: "#1e293b",
            borderRadius: "16px",
            padding: "24px",
            border: "1px solid #334155",
            marginBottom: "24px",
          }}
        >
          <h2 style={{ fontSize: "24px", marginBottom: "16px" }}>Mission Actions</h2>

          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <button
              style={{
                padding: "12px 18px",
                borderRadius: "12px",
                border: "none",
                background: "#22c55e",
                color: "white",
                fontWeight: "bold",
                cursor: "pointer",
              }}
            >
              Run Harvest
            </button>

            <button
              style={{
                padding: "12px 18px",
                borderRadius: "12px",
                border: "none",
                background: "#3b82f6",
                color: "white",
                fontWeight: "bold",
                cursor: "pointer",
              }}
            >
              Run Autonomous Cycle
            </button>
          </div>
        </div>

        <div
          style={{
            background: "#1e293b",
            borderRadius: "16px",
            padding: "24px",
            border: "1px solid #334155",
          }}
        >
          <h2 style={{ fontSize: "24px", marginBottom: "16px" }}>System Status</h2>
          <ul style={{ lineHeight: 1.9, color: "#cbd5e1", paddingLeft: "18px" }}>
            <li>Frontend UI running on localhost:5173</li>
            <li>Backend API expected on localhost:8000</li>
            <li>Mission Control route connected</li>
            <li>Ready for live backend integration</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
