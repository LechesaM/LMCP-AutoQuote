import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";

type Opportunity = {
  id: number | string;
  title?: string;
  buyer?: string;
};

type Quote = {
  id?: number | string;
  quote_number?: string;
  opportunity_id?: number | string;
  total_amount?: number | string;
  status?: string;
};

function StatCard({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div
      style={{
        border: "1px solid #d1d5db",
        borderRadius: 12,
        padding: 20,
        background: "#ffffff",
        boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
      }}
    >
      <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>
        {title}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: "#111827" }}>
        {value}
      </div>
    </div>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: "#ffffff",
        borderRadius: 16,
        padding: 24,
        boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
        border: "1px solid #e5e7eb",
        marginBottom: 24,
      }}
    >
      <h2 style={{ marginTop: 0, color: "#111827" }}>{title}</h2>
      {children}
    </div>
  );
}

function App() {
  const [systemStatus, setSystemStatus] = useState("Checking...");
  const [apiMessage, setApiMessage] = useState("Trying to reach backend...");
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [runMessage, setRunMessage] = useState("Not started");
  const [runLoading, setRunLoading] = useState(false);

  const loadDashboardData = async () => {
    try {
      const summaryRes = await fetch("http://localhost:8000/dashboard/summary");
      if (!summaryRes.ok) {
        throw new Error(`Summary HTTP ${summaryRes.status}`);
      }
      await summaryRes.json();
      setSystemStatus("Online");
      setApiMessage("Backend connected successfully.");
    } catch (err) {
      console.error("Summary fetch failed:", err);
      setSystemStatus("Offline / Not Connected");
      setApiMessage("Could not connect to http://localhost:8000/dashboard/summary");
    }

    try {
      const oppRes = await fetch("http://localhost:8000/dashboard/opportunities");
      if (!oppRes.ok) {
        throw new Error(`Opportunities HTTP ${oppRes.status}`);
      }
      const oppData = await oppRes.json();
      setOpportunities(Array.isArray(oppData) ? oppData : []);
    } catch (err) {
      console.error("Opportunities fetch failed:", err);
      setOpportunities([]);
    }

    try {
      const quoteRes = await fetch("http://localhost:8000/dashboard/quotes");
      if (!quoteRes.ok) {
        throw new Error(`Quotes HTTP ${quoteRes.status}`);
      }
      const quoteData = await quoteRes.json();
      setQuotes(Array.isArray(quoteData) ? quoteData : []);
    } catch (err) {
      console.error("Quotes fetch failed:", err);
      setQuotes([]);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const runAutonomousOnce = async () => {
    setRunLoading(true);
    setRunMessage("Running autonomous engine...");

    try {
      const res = await fetch("http://localhost:8000/autonomous/run-once", {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error(`Run-once HTTP ${res.status}`);
      }

      const data = await res.json();
      setRunMessage(
        typeof data === "object"
          ? JSON.stringify(data)
          : "Autonomous run completed successfully."
      );

      await loadDashboardData();
    } catch (err) {
      console.error("Autonomous run failed:", err);
      setRunMessage("Could not run autonomous engine.");
    } finally {
      setRunLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#f3f4f6",
        fontFamily: "Arial, sans-serif",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div
          style={{
            background: "#111827",
            color: "white",
            borderRadius: 16,
            padding: 24,
            marginBottom: 24,
            boxShadow: "0 6px 18px rgba(0,0,0,0.12)",
          }}
        >
          <div style={{ fontSize: 14, opacity: 0.85, marginBottom: 8 }}>
            LMCP Autonomous Tender Engine
          </div>
          <h1 style={{ margin: 0, fontSize: 36 }}>
            Tender Mission Control Dashboard
          </h1>
          <p style={{ marginTop: 10, marginBottom: 0, opacity: 0.9 }}>
            Live backend connection, opportunities, quotes, and autonomous run control.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
            marginBottom: 24,
          }}
        >
          <StatCard title="System Status" value={systemStatus} />
          <StatCard title="Frontend" value="Stable" />
          <StatCard title="Opportunities" value={String(opportunities.length)} />
          <StatCard title="Quotes" value={String(quotes.length)} />
        </div>

        <SectionCard title="Backend connection result">
          <p style={{ color: "#374151", lineHeight: 1.6 }}>{apiMessage}</p>

          <div
            style={{
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
              marginTop: 20,
              marginBottom: 16,
            }}
          >
            <button
              onClick={loadDashboardData}
              style={{
                padding: "12px 18px",
                borderRadius: 10,
                border: "1px solid #d1d5db",
                background: "#ffffff",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Refresh Dashboard
            </button>

            <button
              onClick={runAutonomousOnce}
              disabled={runLoading}
              style={{
                padding: "12px 18px",
                borderRadius: 10,
                border: "none",
                background: runLoading ? "#9ca3af" : "#111827",
                color: "#ffffff",
                cursor: runLoading ? "not-allowed" : "pointer",
                fontWeight: 600,
              }}
            >
              {runLoading ? "Running..." : "Run Autonomous Once"}
            </button>
          </div>

          <div
            style={{
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: 12,
              padding: 16,
              color: "#111827",
              lineHeight: 1.6,
            }}
          >
            <strong>Run result:</strong>
            <div style={{ marginTop: 8, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {runMessage}
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Harvested Opportunities">
          {opportunities.length === 0 ? (
            <div
              style={{
                background: "#f9fafb",
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                padding: 16,
                color: "#6b7280",
              }}
            >
              No opportunities loaded yet.
            </div>
          ) : (
            <div
              style={{
                overflowX: "auto",
                border: "1px solid #e5e7eb",
                borderRadius: 12,
              }}
            >
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  background: "#ffffff",
                }}
              >
                <thead>
                  <tr style={{ background: "#f3f4f6" }}>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      ID
                    </th>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      Title
                    </th>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      Buyer
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {opportunities.map((opp) => (
                    <tr key={String(opp.id)}>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {opp.id}
                      </td>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {opp.title ?? "-"}
                      </td>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {opp.buyer ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Generated Quotes">
          {quotes.length === 0 ? (
            <div
              style={{
                background: "#f9fafb",
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                padding: 16,
                color: "#6b7280",
              }}
            >
              No quotes loaded yet.
            </div>
          ) : (
            <div
              style={{
                overflowX: "auto",
                border: "1px solid #e5e7eb",
                borderRadius: 12,
              }}
            >
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  background: "#ffffff",
                }}
              >
                <thead>
                  <tr style={{ background: "#f3f4f6" }}>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      ID
                    </th>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      Quote Number
                    </th>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      Opportunity ID
                    </th>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      Total Amount
                    </th>
                    <th style={{ padding: 12, borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {quotes.map((quote, index) => (
                    <tr key={String(quote.id ?? index)}>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {quote.id ?? "-"}
                      </td>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {quote.quote_number ?? "-"}
                      </td>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {quote.opportunity_id ?? "-"}
                      </td>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {quote.total_amount ?? "-"}
                      </td>
                      <td style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
                        {quote.status ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

const root = document.getElementById("root");

if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
