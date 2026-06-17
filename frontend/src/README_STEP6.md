# Step 6 — Submission Control Actions

This package gives you a clean LMCP frontend block for submission controls.

## Files included

- `src/services/submissionControlApi.js`
- `src/components/dashboard/SubmissionControlActions.jsx`
- `src/pages/SubmissionControlPage.jsx`

## What it does

- Runs the backend submission scheduler
- Pulls submission summary analytics
- Pulls profit analytics
- Pulls recent submission history
- Displays all of that in a dashboard card

## Expected backend endpoints

The component is built to call these endpoints:

- `POST /submission-scheduler/run-now?limit=10`
- `GET /submission-analytics/summary`
- `GET /submission-analytics/profit`
- `GET /submission-history?limit=20`

## API base URL

Set this in your frontend `.env` file:

```env
VITE_API_BASE_URL=http://127.0.0.1:8011
```

## Fast install

Copy the included `src` folder contents into your real frontend project.

Then mount the page inside your router or import the component into your dashboard page.

Example:

```jsx
import SubmissionControlActions from "./components/dashboard/SubmissionControlActions";

<SubmissionControlActions />
```

## Notes

If your backend returns slightly different field names, the component already contains fallback mappings for:
- submitted / total_submitted
- pending / pending_submission
- failed / submission_failed
- total_profit / profit
- total_revenue / revenue

If your real history endpoint is not yet available, the page still loads and shows the rest of the dashboard.
