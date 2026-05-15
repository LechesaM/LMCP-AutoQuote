// lmcp-frontend/src/components/SafeModeToggle.jsx

import React, { useState } from "react";
import {
  enableFullSubmission,
  enableSafeMode,
  switchSystemOff,
  runAutonomousOnce,
} from "../services/v48AutonomousPolicy";

export default function SafeModeToggle() {
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState("");

  async function apply(action) {
    setLoading(true);
    setError("");
    try {
      const result = await action();
      setLastResult(result);
    } catch (err) {
      setError(err.message || "Action failed");
    } finally {
      setLoading(false);
    }
  }

  const policy = lastResult?.policy || null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-1">
        <h2 className="text-xl font-bold text-slate-900">Autonomous Submission Control</h2>
        <p className="text-sm text-slate-500">
          Control full submission, safe mode, and emergency shutdown.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <button
          disabled={loading}
          onClick={() => apply(enableFullSubmission)}
          className="rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-60"
        >
          Enable Full Submission
        </button>

        <button
          disabled={loading}
          onClick={() => apply(enableSafeMode)}
          className="rounded-xl bg-amber-500 px-4 py-3 font-semibold text-white shadow-sm hover:bg-amber-600 disabled:opacity-60"
        >
          Safe Mode
        </button>

        <button
          disabled={loading}
          onClick={() => apply(switchSystemOff)}
          className="rounded-xl bg-red-600 px-4 py-3 font-semibold text-white shadow-sm hover:bg-red-700 disabled:opacity-60"
        >
          OFF / Kill Switch
        </button>
      </div>

      <button
        disabled={loading}
        onClick={() => apply(runAutonomousOnce)}
        className="mt-3 w-full rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
      >
        Run Once Now
      </button>

      {loading && <p className="mt-4 text-sm text-slate-500">Working...</p>}

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {policy && (
        <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
          <div><strong>Enabled:</strong> {String(policy.enabled)}</div>
          <div><strong>Mode:</strong> {policy.mode}</div>
          <div><strong>Email Send:</strong> {String(policy.allow_email_send)}</div>
          <div><strong>Portal Upload:</strong> {String(policy.allow_portal_upload)}</div>
          <div><strong>Portal Final Submit:</strong> {String(policy.allow_portal_final_submit)}</div>
          <div><strong>Requires Confirmation:</strong> {String(policy.require_confirmation_phrase)}</div>
        </div>
      )}

      {lastResult && !policy && (
        <pre className="mt-4 max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-white">
          {JSON.stringify(lastResult, null, 2)}
        </pre>
      )}
    </section>
  );
}
