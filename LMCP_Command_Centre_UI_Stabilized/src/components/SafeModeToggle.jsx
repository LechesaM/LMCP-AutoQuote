import React, { useState } from "react";
import {
  enableFullSubmission,
  enableSafeMode,
  switchSystemOff,
  runAutonomousOnce,
} from "../services/v48AutonomousPolicy";

export default function SafeModeToggle() {
  const [loading, setLoading] = useState(false);

  async function handle(action) {
    setLoading(true);
    try {
      await action();
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  return (
    <div className="rounded-xl bg-slate-900 p-4 border border-slate-700">
      <h2 className="text-lg font-bold mb-3">System Control</h2>

      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => handle(enableFullSubmission)}
          disabled={loading}
          className="bg-green-600 hover:bg-green-700 p-2 rounded"
        >
          Full Submission
        </button>

        <button
          onClick={() => handle(enableSafeMode)}
          disabled={loading}
          className="bg-yellow-600 hover:bg-yellow-700 p-2 rounded"
        >
          Safe Mode
        </button>

        <button
          onClick={() => handle(switchSystemOff)}
          disabled={loading}
          className="bg-red-600 hover:bg-red-700 p-2 rounded"
        >
          OFF / Kill
        </button>

        <button
          onClick={() => handle(runAutonomousOnce)}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 p-2 rounded"
        >
          Run Once
        </button>
      </div>
    </div>
  );
}
