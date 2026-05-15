# Live Tender Stream Panel — Integration Guide

## Files included
- `src/components/LiveTenderStreamPanel.jsx`
- `src/hooks/useLiveTenderStream.js`
- `src/services/liveTenderApi.js`

## What this panel does
- Displays a live stream of tenders from your backend
- Polls every 15 seconds
- Tries these endpoints in order:
  1. `/opportunities`
  2. `/opportunities/live`
  3. `/dashboard/live-tender-stream`
- Also reads:
  - `/autonomous/status`
  - `/dashboard/summary`

## Step 1 — Copy files into your frontend
From the extracted folder, copy:
- `src/components/LiveTenderStreamPanel.jsx` into your frontend `src/components/`
- `src/hooks/useLiveTenderStream.js` into your frontend `src/hooks/`
- `src/services/liveTenderApi.js` into your frontend `src/services/`

If the folders do not exist yet, create them.

## Step 2 — Set your backend base URL
In your frontend project root, create or edit `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If your frontend is already running, stop it and start it again after saving `.env`.

## Step 3 — Render the panel
Example in `src/App.jsx`:

```jsx
import LiveTenderStreamPanel from "./components/LiveTenderStreamPanel";

export default function App() {
  return (
    <main className="min-h-screen bg-slate-950 p-6">
      <LiveTenderStreamPanel />
    </main>
  );
}
```

## Step 4 — Start the frontend
Typical Vite commands:

```bash
npm install
npm run dev
```

Then open the local frontend URL shown in the terminal.

## Step 5 — Check backend endpoints
In a browser or terminal, confirm these work:

```bash
curl http://localhost:8000/opportunities
curl http://localhost:8000/autonomous/status
curl http://localhost:8000/dashboard/summary
```

If `/opportunities` is empty, the panel will still load but may show no tender rows until the backend returns data.

## Optional next improvement
Best next panel after this one:
- Pipeline Activity
- Quote Generation Activity
- Submission Activity
