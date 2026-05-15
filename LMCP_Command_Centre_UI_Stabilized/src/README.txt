Step 6 upgrade package.

Copy these files into your frontend project:

src/App.jsx
src/components/SubmissionControlActions.jsx
src/services/submissionControlApi.js

Keep your existing:
- src/components/LiveTenderStreamPanel.jsx
- src/components/PipelineActivityPanel.jsx

.env should contain:
VITE_API_BASE_URL=http://127.0.0.1:8000

Then run:
npm run dev -- --host 127.0.0.1 --port 5173
