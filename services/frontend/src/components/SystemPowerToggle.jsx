import { useEffect, useState } from 'react';
import {
  fetchSystemControlStatus,
  toggleSystemPower,
} from '../services/systemControlApi';

export default function SystemPowerToggle() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');

  async function loadStatus() {
    try {
      setError('');
      const data = await fetchSystemControlStatus();
      setStatus(data);
    } catch (err) {
      setError(err.message || 'Failed to load system status.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
    const id = window.setInterval(loadStatus, 10000);
    return () => window.clearInterval(id);
  }, []);

  async function handleToggle() {
    if (!status) return;
    const nextIsOn = !status.system_enabled;
    try {
      setSaving(true);
      setError('');
      const data = await toggleSystemPower(nextIsOn);
      setStatus(data);
    } catch (err) {
      setError(err.message || 'Failed to update power state.');
    } finally {
      setSaving(false);
    }
  }

  const isOn = Boolean(status?.system_enabled);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">System Power</p>
          <h3 className="text-xl font-semibold text-slate-900">
            {loading ? 'Loading…' : isOn ? 'LMCP is ON' : 'LMCP is OFF'}
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            {status?.message || 'Live control for autonomous harvesting and submission processes.'}
          </p>
        </div>

        <button
          type="button"
          onClick={handleToggle}
          disabled={loading || saving}
          className={`relative inline-flex h-14 w-32 items-center rounded-full px-2 transition ${
            isOn ? 'bg-emerald-500' : 'bg-slate-300'
          } ${loading || saving ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'}`}
          aria-pressed={isOn}
        >
          <span
            className={`inline-block h-10 w-10 transform rounded-full bg-white shadow transition ${
              isOn ? 'translate-x-18' : 'translate-x-0'
            }`}
          />
          <span className="absolute left-4 text-xs font-bold text-white">
            {isOn ? 'ON' : ''}
          </span>
          <span className="absolute right-4 text-xs font-bold text-slate-700">
            {!isOn ? 'OFF' : ''}
          </span>
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <InfoTile label="Autonomous Engine" value={status?.autonomous_enabled ? 'Enabled' : 'Disabled'} />
        <InfoTile label="Harvester" value={status?.harvester_enabled ? 'Enabled' : 'Disabled'} />
        <InfoTile label="Submission Scheduler" value={status?.submission_scheduler_enabled ? 'Enabled' : 'Disabled'} />
      </div>

      {!!status?.updated_at && (
        <p className="mt-3 text-xs text-slate-500">Last changed: {status.updated_at}</p>
      )}
      {!!error && <p className="mt-3 text-sm font-medium text-red-600">{error}</p>}
    </div>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}
