import React from "react";
import ReactDOM from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./styles/globals.css";
import App from "./App.jsx";
import ErrorBoundary from "./components/error/ErrorBoundary.tsx";
import TelemetryFailureFallback from "./components/error/TelemetryFailureFallback.tsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary fallback={TelemetryFailureFallback}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
