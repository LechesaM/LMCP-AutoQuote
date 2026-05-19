import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import CommandCentreRouteLayout from "./layouts/CommandCentreRouteLayout.tsx";
import RouteLoadingState from "./components/ui/RouteLoadingState.tsx";

const DashboardPage = lazy(() => import("./pages/DashboardPage.tsx"));
const RFQOperationsPage = lazy(() => import("./pages/RFQOperationsPage.tsx"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage.tsx"));
const GovernancePage = lazy(() => import("./pages/GovernancePage.tsx"));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoadingState label="Loading command centre route" />}>
        <Routes>
          <Route element={<CommandCentreRouteLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/operations" element={<RFQOperationsPage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/governance" element={<GovernancePage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
