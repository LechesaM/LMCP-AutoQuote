# LMCP Step 7 System Control Wiring

Drop these files into your existing frontend:

```text
lmcp-frontend/src/services/systemControl.js
lmcp-frontend/src/components/SystemControl.jsx
lmcp-frontend/src/components/SystemControl.css
```

## Use in your page

```jsx
import SystemControl from "./components/SystemControl";

export default function App() {
  return <SystemControl />;
}
```

## Backend endpoints wired

```text
GET  /autonomous/status
POST /system/control/on
POST /system/control/off
POST /autonomous/run-once
POST /system/control/pause-harvest
POST /system/control/pause-submissions
POST /system/control/resume-all
POST /system/control/emergency-stop
```

The service includes fallbacks for older autonomous endpoint names.
