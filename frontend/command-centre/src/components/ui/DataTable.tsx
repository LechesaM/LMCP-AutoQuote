import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Search } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import EmptyTelemetryState from "./EmptyTelemetryState.tsx";
import StateBadge from "./StateBadge.tsx";
import { SkeletonCard } from "./SkeletonBlocks.tsx";

type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  className?: string;
  headerClassName?: string;
};

type DataTableProps<T> = {
  title: string;
  description?: string;
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  searchPlaceholder?: string;
  searchAccessor?: (row: T) => string;
  defaultSortKey?: string;
  defaultSortDirection?: "asc" | "desc";
  pageSize?: number;
  loading?: boolean;
  error?: string;
  stale?: boolean;
  refreshing?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  onRetry?: () => void;
  toolbar?: ReactNode;
};

export default function DataTable<T>({
  title,
  description,
  rows,
  columns,
  rowKey,
  searchPlaceholder = "Search records",
  searchAccessor,
  defaultSortKey,
  defaultSortDirection = "desc",
  pageSize = 8,
  loading = false,
  error = "",
  stale = false,
  refreshing = false,
  emptyMessage = "No records available.",
  onRowClick,
  onRetry,
  toolbar,
}: DataTableProps<T>) {
  const [searchTerm, setSearchTerm] = useState("");
  const [sortKey, setSortKey] = useState(defaultSortKey || columns[0]?.key || "");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">(defaultSortDirection);
  const [pageIndex, setPageIndex] = useState(0);

  const filteredRows = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const searchable = normalizedSearch
      ? rows.filter((row) => {
          if (!searchAccessor) {
            return JSON.stringify(row).toLowerCase().includes(normalizedSearch);
          }
          return searchAccessor(row).toLowerCase().includes(normalizedSearch);
        })
      : rows;

    const column = columns.find((entry) => entry.key === sortKey);
    const sorted = [...searchable].sort((left, right) => {
      const leftValue = column?.sortValue?.(left) ?? (left as Record<string, unknown>)[sortKey];
      const rightValue = column?.sortValue?.(right) ?? (right as Record<string, unknown>)[sortKey];
      const leftText = typeof leftValue === "number" ? leftValue : String(leftValue ?? "");
      const rightText = typeof rightValue === "number" ? rightValue : String(rightValue ?? "");
      if (typeof leftValue === "number" || typeof rightValue === "number") {
        return sortDirection === "asc" ? Number(leftText) - Number(rightText) : Number(rightText) - Number(leftText);
      }
      return sortDirection === "asc" ? leftText.localeCompare(rightText) : rightText.localeCompare(leftText);
    });

    return sorted;
  }, [columns, rows, searchAccessor, searchTerm, sortDirection, sortKey]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const pageRows = filteredRows.slice(pageIndex * pageSize, pageIndex * pageSize + pageSize);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
    setPageIndex(0);
  };

  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";

  if (loading) {
    return (
      <div className="glass-card rounded-3xl p-5">
        <SkeletonCard lines={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-black text-white">{title}</h3>
            {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
          </div>
          <StateBadge state="error" />
        </div>
        <div className="mt-4 rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div>
        {onRetry ? (
          <button className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan" onClick={onRetry} type="button">
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  if (!filteredRows.length) {
    return (
      <div className="glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-black text-white">{title}</h3>
            {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
          </div>
          <StateBadge state={statusState} />
        </div>
        <div className="mt-4">
          <EmptyTelemetryState title={emptyMessage} description="No matching records were found for the current filter set." />
        </div>
      </div>
    );
  }

  return (
    <div className={`glass-card rounded-3xl p-5 ${stale ? "opacity-95" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-black text-white">{title}</h3>
          {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge state={statusState} />
          {toolbar}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="flex min-w-[240px] flex-1 items-center gap-2 rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3">
          <Search size={15} className="text-slate-500" />
          <input
            className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-500"
            onChange={(event) => {
              setSearchTerm(event.target.value);
              setPageIndex(0);
            }}
            placeholder={searchPlaceholder}
            value={searchTerm}
          />
        </label>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-2 text-[10px] font-black uppercase tracking-[.22em] text-slate-400">
          {filteredRows.length} rows
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded-3xl border border-slate-700/60">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left">
            <thead className="bg-slate-950/70">
              <tr>
                {columns.map((column) => (
                  <th key={column.key} className={`whitespace-nowrap px-4 py-3 text-xs font-black uppercase tracking-[.24em] text-slate-400 ${column.headerClassName || ""}`}>
                    <button
                      className={`inline-flex items-center gap-2 ${column.sortable ? "cursor-pointer text-slate-300 hover:text-white" : ""}`}
                      onClick={column.sortable ? () => handleSort(column.key) : undefined}
                      type="button"
                    >
                      <span>{column.header}</span>
                      {column.sortable ? (
                        sortKey === column.key ? sortDirection === "asc" ? <ChevronUp size={13} /> : <ChevronDown size={13} /> : <span className="text-slate-600">↕</span>
                      ) : null}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row, index) => (
                <tr
                  key={rowKey(row)}
                  className={`border-t border-slate-800/70 ${onRowClick ? "cursor-pointer hover:bg-slate-900/60" : ""} ${index % 2 === 0 ? "bg-slate-950/25" : "bg-slate-950/10"}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={`px-4 py-4 align-top text-sm text-slate-300 ${column.className || ""}`}>
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs uppercase tracking-[.22em] text-slate-500">
          Page {pageIndex + 1} of {totalPages}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-3 py-2 text-sm font-bold text-slate-300 disabled:opacity-40"
            disabled={pageIndex === 0}
            onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
            type="button"
          >
            <ChevronLeft size={15} />
          </button>
          <button
            className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-3 py-2 text-sm font-bold text-slate-300 disabled:opacity-40"
            disabled={pageIndex >= totalPages - 1}
            onClick={() => setPageIndex((current) => Math.min(totalPages - 1, current + 1))}
            type="button"
          >
            <ChevronRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
