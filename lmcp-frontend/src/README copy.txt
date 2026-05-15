Step 7 ON/OFF System Control package.

Copy these files into your frontend project:

src/App.jsx
src/components/SystemControlPanel.jsx
src/services/systemControlApi.js

Keep your existing files:
- src/components/LiveTenderStreamPanel.jsx
- src/components/PipelineActivityPanel.jsx
- src/components/SubmissionControlActions.jsx
- src/services/submissionControlApi.js

Restart Vite:
npm run dev -- --host 127.0.0.1 --port 5173

Notes:
- Status reads from /autonomous/status
- ON/OFF buttons try common enable/disable endpoint patterns
- If your backend uses different ON/OFF endpoints, only systemControlApi.js will need a small path update
