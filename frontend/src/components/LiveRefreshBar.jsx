import { useEffect, useMemo, useState } from "react";

const STORAGE_KEY_ENABLED = "lmcp_live_refresh_enabled";
const STORAGE_KEY_INTERVAL = "lmcp_live_refresh_interval_seconds";

function formatTime(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function LiveRefreshBar() {
  const [enabled, setEnabled] = useState(() => {
    const stored = localStorage.getItem(STORAGE_KEY_ENABLED);
    return stored === null ? true : stored === "true";
  });

  const [intervalSeconds, setIntervalSeconds] = useState(() => {
    const stored = Number(localStorage.getItem(STORAGE_KEY_INTERVAL));
    return Number.isFinite(stored) && stored > 0 ? stored : 20;
  });

  const [lastTick, setLastTick] = useState(null);
  const [nextRefreshIn, setNextRefreshIn] = useState(intervalSeconds);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_ENABLED, String(enabled));
  }, [enabled]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_INTERVAL, String(intervalSeconds));
  }, [intervalSeconds]);

  useEffect(() => {
    setNextRefreshIn(intervalSeconds);
  }, [intervalSeconds]);

  useEffect(() => {
    if (!enabled) return;

    const countdown = setInterval(() => {
      setNextRefreshIn((prev) => {
        if (prev <= 1) {
          return intervalSeconds;
        }
        return prev - 1;
      });
    }, 1000);

    const refresher = setInterval(() => {
      setLastTick(new Date().toISOString());
      window.dispatchEvent(
        new CustomEvent("lmcp-live-refresh", {
          detail: {
            triggeredAt: new Date().toISOString(),
            intervalSeconds,
          },
        })
      );
    }, intervalSeconds * 1000);

    return () => {
      clearInterval(countdown);
      clearInterval(refresher);
    };
  }, [enabled, intervalSeconds]);

  const statusText = useMemo(() => {
    if (!enabled) return "LIVE AUTO-REFRESH OFF";
    return "LIVE AUTO-REFRESH ON";
  }, [enabled]);

  return (
    <section className="rounded-[24px] border border-cyan-500/20 bg-cyan-500/5 px-5 py-4 shadow-lg">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold text-cyan-200">
            <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-300" />
            <span>{statusText}</span>
          </div>

          <div className="text-sm text-slate-300">
            Last auto-refresh: <span className="text-white">{formatTime(lastTick)}</span>
          </div>

          <div className="text-sm text-slate-300">
            Next refresh in: <span className="text-white">{enabled ? `${nextRefreshIn}s` : "paused"}</span>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
            <span className="text-sm text-slate-300">Interval</span>
            <select
              value={intervalSeconds}
              onChange={(e) => setIntervalSeconds(Number(e.target.value))}
              className="rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none"
            >
              <option value={10}>10 sec</option>
              <option value={15}>15 sec</option>
              <option value={20}>20 sec</option>
              <option value={30}>30 sec</option>
              <option value={60}>60 sec</option>
            </select>
          </label>

          <button
            onClick={() => setEnabled((prev) => !prev)}
            className={`rounded-2xl px-5 py-3 text-sm font-semibold transition ${
              enabled
                ? "bg-rose-400 text-slate-950 hover:opacity-90"
                : "bg-emerald-400 text-slate-950 hover:opacity-90"
            }`}
          >
            {enabled ? "Pause Auto-Refresh" : "Resume Auto-Refresh"}
          </button>

          <button
            onClick={() => {
              const now = new Date().toISOString();
              setLastTick(now);
              setNextRefreshIn(intervalSeconds);
              window.dispatchEvent(
                new CustomEvent("lmcp-live-refresh", {
                  detail: {
                    triggeredAt: now,
                    intervalSeconds,
                    manual: true,
                  },
                })
              );
            }}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            Refresh All Now
          </button>
        </div>
      </div>
    </section>
  );
}

