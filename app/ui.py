from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["LMCP UI"])


HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LMCP Tender Command Center</title>
    <style>
        :root {
            --bg: #0b1020;
            --panel: #131a2e;
            --panel-2: #1b2440;
            --text: #eef2ff;
            --muted: #aab4d6;
            --accent: #4f8cff;
            --good: #23c55e;
            --warn: #f59e0b;
            --bad: #ef4444;
            --line: rgba(255,255,255,0.08);
            --shadow: 0 12px 30px rgba(0,0,0,0.25);
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #0b1020 0%, #111933 100%);
            color: var(--text);
        }

        .wrapper {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }

        .title-wrap h1 {
            margin: 0 0 6px 0;
            font-size: 32px;
            font-weight: 800;
            letter-spacing: 0.2px;
        }

        .title-wrap p {
            margin: 0;
            color: var(--muted);
            font-size: 14px;
        }

        .actions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        button {
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 12px 18px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: var(--shadow);
        }

        button.secondary {
            background: var(--panel-2);
            border: 1px solid var(--line);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 18px;
            margin-bottom: 24px;
        }

        .card {
            background: rgba(19, 26, 46, 0.92);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 20px;
            box-shadow: var(--shadow);
        }

        .metric-label {
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 10px;
        }

        .metric-value {
            font-size: 34px;
            font-weight: 800;
            line-height: 1.1;
        }

        .metric-sub {
            margin-top: 8px;
            font-size: 13px;
            color: var(--muted);
        }

        .green { color: var(--good); }
        .orange { color: var(--warn); }
        .red { color: var(--bad); }

        .section-grid {
            display: grid;
            grid-template-columns: 1.4fr 1fr;
            gap: 18px;
        }

        .section-title {
            font-size: 18px;
            font-weight: 800;
            margin: 0 0 16px 0;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
        }

        .small {
            font-size: 12px;
            color: var(--muted);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            text-align: left;
            padding: 12px 10px;
            border-bottom: 1px solid var(--line);
            font-size: 14px;
            vertical-align: top;
        }

        th {
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }

        .pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            background: rgba(255,255,255,0.08);
        }

        .status-online {
            background: rgba(35,197,94,0.16);
            color: #86efac;
        }

        .status-db {
            background: rgba(79,140,255,0.16);
            color: #93c5fd;
        }

        .footer-note {
            margin-top: 18px;
            color: var(--muted);
            font-size: 12px;
        }

        .empty {
            color: var(--muted);
            font-size: 14px;
            padding: 10px 0 2px 0;
        }

        @media (max-width: 1100px) {
            .grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .section-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 700px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .title-wrap h1 {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="topbar">
            <div class="title-wrap">
                <h1>LMCP Tender Command Center</h1>
                <p>Live dashboard for the LMCP Autonomous Tender Engine</p>
            </div>
            <div class="actions">
                <button onclick="loadDashboard()">Refresh Dashboard</button>
                <button class="secondary" onclick="window.location.href='/docs'">Open API Docs</button>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="metric-label">Total Opportunities</div>
                <div class="metric-value" id="total_opportunities">0</div>
                <div class="metric-sub">All harvested RFQs and tenders</div>
            </div>

            <div class="card">
                <div class="metric-label">High-Relevance RFQs</div>
                <div class="metric-value green" id="high_relevance">0</div>
                <div class="metric-sub">Strong bidding opportunities</div>
            </div>

            <div class="card">
                <div class="metric-label">Quotes Generated</div>
                <div class="metric-value" id="quotes_generated">0</div>
                <div class="metric-sub">Quotation drafts built by the system</div>
            </div>

            <div class="card">
                <div class="metric-label">System Health</div>
                <div class="metric-value" id="api_status">ONLINE</div>
                <div class="metric-sub">
                    API: <span id="api_status_text" class="pill status-online">online</span>
                    &nbsp;
                    DB: <span id="db_status_text" class="pill status-db">connected</span>
                </div>
            </div>
        </div>

        <div class="section-grid">
            <div class="card">
                <div class="panel-header">
                    <h2 class="section-title">Recent Opportunities</h2>
                    <div class="small" id="opportunity_count_label">Loading...</div>
                </div>
                <div id="opportunities_container"></div>
            </div>

            <div class="card">
                <div class="panel-header">
                    <h2 class="section-title">Recent Quotes</h2>
                    <div class="small" id="quote_count_label">Loading...</div>
                </div>
                <div id="quotes_container"></div>
            </div>
        </div>

        <div class="footer-note" id="last_updated">
            Last updated: waiting for first refresh...
        </div>
    </div>

    <script>
        async function fetchJson(url) {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error("Request failed: " + url);
            }
            return await response.json();
        }

        function escapeHtml(value) {
            if (value === null || value === undefined) return "";
            return String(value)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function scorePill(score) {
            const numeric = Number(score || 0);
            let cls = "pill";
            if (numeric >= 70) cls += " status-online";
            else if (numeric >= 50) cls += " status-db";
            else cls += "";
            return `<span class="${cls}">${numeric}</span>`;
        }

        function renderOpportunities(rows) {
            const container = document.getElementById("opportunities_container");
            const label = document.getElementById("opportunity_count_label");

            if (!rows || rows.length === 0) {
                label.textContent = "0 records";
                container.innerHTML = `<div class="empty">No opportunities found yet.</div>`;
                return;
            }

            label.textContent = rows.length + " records";

            const html = `
                <table>
                    <thead>
                        <tr>
                            <th>Title</th>
                            <th>Buyer</th>
                            <th>Score</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map(row => `
                            <tr>
                                <td>
                                    <strong>${escapeHtml(row.title || "")}</strong><br>
                                    <span class="small">${escapeHtml(row.source || row.department || "")}</span>
                                </td>
                                <td>${escapeHtml(row.buyer || row.department || "-")}</td>
                                <td>${scorePill(row.relevance_score)}</td>
                                <td>${escapeHtml(row.created_at || "-")}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
            container.innerHTML = html;
        }

        function renderQuotes(rows) {
            const container = document.getElementById("quotes_container");
            const label = document.getElementById("quote_count_label");

            if (!rows || rows.length === 0) {
                label.textContent = "0 records";
                container.innerHTML = `<div class="empty">No quotes generated yet.</div>`;
                return;
            }

            label.textContent = rows.length + " records";

            const html = `
                <table>
                    <thead>
                        <tr>
                            <th>Quote No.</th>
                            <th>Status</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map(row => `
                            <tr>
                                <td>
                                    <strong>${escapeHtml(row.quote_number || ("Quote #" + row.id))}</strong><br>
                                    <span class="small">Opportunity ID: ${escapeHtml(row.opportunity_id || "-")}</span>
                                </td>
                                <td>${escapeHtml(row.status || "draft")}</td>
                                <td>R ${Number(row.total_amount || 0).toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
            container.innerHTML = html;
        }

        async function loadDashboard() {
            try {
                const [summary, opportunities, quotes, health] = await Promise.all([
                    fetchJson("/dashboard/summary"),
                    fetchJson("/dashboard/opportunities"),
                    fetchJson("/dashboard/quotes"),
                    fetchJson("/dashboard/health")
                ]);

                document.getElementById("total_opportunities").textContent = summary.total_opportunities ?? 0;
                document.getElementById("high_relevance").textContent = summary.high_relevance ?? 0;
                document.getElementById("quotes_generated").textContent = summary.quotes_generated ?? 0;
                document.getElementById("api_status").textContent = String(summary.api_status || "online").toUpperCase();
                document.getElementById("api_status_text").textContent = health.api || "online";
                document.getElementById("db_status_text").textContent = health.database || "connected";

                renderOpportunities(opportunities);
                renderQuotes(quotes);

                document.getElementById("last_updated").textContent =
                    "Last updated: " + new Date().toLocaleString();
            } catch (error) {
                console.error(error);
                document.getElementById("last_updated").textContent =
                    "Last updated: dashboard failed to load. Check API logs.";
            }
        }

        loadDashboard();
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>
"""


@router.get("/ui", response_class=HTMLResponse)
def tender_command_center():
    return HTML_PAGE
