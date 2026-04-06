import { useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import DashboardPage from "./pages/DashboardPage";
import { useDashboardData } from "./hooks/useDashboardData";

export default function App() {
  const [query, setQuery] = useState("");
  const [submissionFilter, setSubmissionFilter] = useState("all");
  const { loading, summary, tenders, alerts, refresh } = useDashboardData();

  const filteredTenders = useMemo(() => {
    let result = tenders;

    if (submissionFilter !== "all") {
      result = result.filter((tender) => tender.submission_type === submissionFilter);
    }

    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter((tender) =>
        [
          tender.title,
          tender.buyer,
          tender.province,
          tender.sector,
          tender.submission_type,
          tender.status,
        ]
          .join(" ")
          .toLowerCase()
          .includes(q)
      );
    }

    return result;
  }, [tenders, query, submissionFilter]);

  return (
    <div className="min-h-screen bg-slate-100 p-6 text-slate-900">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-3xl bg-slate-900 p-6 text-white shadow-xl">
          <h1 className="text-3xl font-bold">LMCP Autonomous Tender System</h1>
          <p className="mt-2 max-w-3xl text-slate-300">
            Live procurement intelligence dashboard for LMCP.
          </p>
        </header>

        <div className="flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search tenders, buyers, sectors..."
              className="w-64 bg-transparent text-sm outline-none placeholder:text-slate-400"
            />
          </div>

          <div className="flex gap-3">
            <select
              value={submissionFilter}
              onChange={(event) => setSubmissionFilter(event.target.value)}
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm"
            >
              <option value="all">All submissions</option>
              <option value="email-only">Email-only</option>
              <option value="portal-only">Portal-only</option>
            </select>

            <button
              onClick={refresh}
              className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-medium text-white"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>

        {loading ? (
          <div className="rounded-3xl bg-white p-10 text-center shadow-sm ring-1 ring-slate-200">
            Loading dashboard...
          </div>
        ) : (
          <DashboardPage summary={summary} tenders={filteredTenders} alerts={alerts} />
        )}
      </div>
    </div>
  );
}
