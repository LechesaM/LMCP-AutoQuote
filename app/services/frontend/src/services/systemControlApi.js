const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.detail || data?.message || 'Request failed';
    throw new Error(message);
  }
  return data;
}

export async function fetchSystemControlStatus() {
  const response = await fetch(`${API_BASE}/system-control/status`);
  return readJson(response);
}

export async function turnSystemOn(reason = 'Manual startup from dashboard') {
  const response = await fetch(
    `${API_BASE}/system-control/on?reason=${encodeURIComponent(reason)}`,
    { method: 'POST' }
  );
  return readJson(response);
}

export async function turnSystemOff(reason = 'Manual shutdown from dashboard') {
  const response = await fetch(
    `${API_BASE}/system-control/off?reason=${encodeURIComponent(reason)}`,
    { method: 'POST' }
  );
  return readJson(response);
}

export async function toggleSystemPower(nextIsOn) {
  if (nextIsOn) {
    return turnSystemOn();
  }
  return turnSystemOff();
}
