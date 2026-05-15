# LMCP Step 8 Autonomous Cycle Live Trigger + Dashboard Sync

Drop these files into your existing frontend:

```text
lmcp-frontend/src/services/autonomousCycle.js
lmcp-frontend/src/components/AutonomousCycleSync.jsx
lmcp-frontend/src/components/AutonomousCycleSync.css
```

## Use in your page

```jsx
import AutonomousCycleSync from "./components/AutonomousCycleSync";

export default function App() {
  return <AutonomousCycleSync />;
}
```

## Backend endpoints wired

```text
POST /autonomous/run-once
POST /autonomous/run-sync
POST /full-autonomous-cycle/run

GET /autonomous/status
GET /dashboard/summary
GET /submission-analytics/summary
GET /submission-analytics/profit
```

The service includes fallbacks where available.
