# LMCP Frontend Step 1

This is a fresh Step 1 Mission Control frontend pack for a Vite + React app.

## Files included
- `src/App.jsx`
- `src/pages/MissionControlStep1.jsx`
- `src/components/TopStatsBar.jsx`
- `src/components/MetricPanel.jsx`
- `src/components/HeatMapPanel.jsx`
- `src/components/RadarPanel.jsx`
- `src/components/TenderColumns.jsx`
- `src/components/ArchitecturePanel.jsx`
- `src/data/missionControlData.js`
- `src/styles/mission-control-step1.css`

## How to use
1. Copy the `src` files into your frontend project.
2. Replace your current `src/App.jsx` with the provided one.
3. Import the CSS through the provided `App.jsx`.
4. Run:

```bash
npm install
npm run dev
```

## Notes
This Step 1 pack is a frontend visual build focused on matching the attached Mission Control look:
- dark neon control room theme
- top metrics
- South Africa heatmap panel
- radar panel
- tender priority boards
- architecture / pipeline view

The data is currently mocked for visual completeness.
In Step 2, these panels can be wired to your live LMCP backend endpoints.
