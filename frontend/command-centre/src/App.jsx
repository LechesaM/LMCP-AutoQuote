import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import useAuthStore from "./auth/authStore";
import RequireRole from "./auth/RequireRole.tsx";
import CommandCentreRouteLayout from "./layouts/CommandCentreRouteLayout.tsx";
import RouteLoadingState from "./components/ui/RouteLoadingState.tsx";

const LoginPage = lazy(() => import("./pages/LoginPage.tsx"));
const DashboardPage = lazy(() => import("./pages/DashboardPage.tsx"));
const RFQOperationsPage = lazy(() => import("./pages/RFQOperationsPage.tsx"));
const SourceHealthPage = lazy(() => import("./pages/SourceHealthPage.tsx"));
const QualificationInsightsPage = lazy(() => import("./pages/QualificationInsightsPage.tsx"));
const PricingEvidencePage = lazy(() => import("./pages/PricingEvidencePage.tsx"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage.tsx"));
const GovernancePage = lazy(() => import("./pages/GovernancePage.tsx"));
const OperatorOperationsPage = lazy(() => import("./pages/OperatorOperationsPage.tsx"));
const OperatorAssignmentsPage = lazy(() => import("./pages/OperatorAssignmentsPage.tsx"));
const ActivityTimelinePage = lazy(() => import("./pages/ActivityTimelinePage.tsx"));

export default function App() {
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const hydrated = useAuthStore((state) => state.hydrated);

  useEffect(() => {
    if (hydrated) {
      bootstrap().catch(() => {});
    }
  }, [bootstrap, hydrated]);

  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoadingState label="Loading command centre route" />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireRole>
                <CommandCentreRouteLayout />
              </RequireRole>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/operations" element={<RFQOperationsPage />} />
            <Route path="/source-health" element={<SourceHealthPage />} />
            <Route path="/qualification-insights" element={<QualificationInsightsPage />} />
            <Route path="/pricing-evidence" element={<PricingEvidencePage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/governance" element={<GovernancePage />} />
            <Route path="/operator-operations" element={<OperatorOperationsPage />} />
            <Route path="/operator-assignments" element={<OperatorAssignmentsPage />} />
            <Route path="/activity-timeline" element={<ActivityTimelinePage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
