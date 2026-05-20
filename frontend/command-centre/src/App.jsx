import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import useAuthStore from "./auth/authStore";
import RequireRole from "./auth/RequireRole.tsx";
import CommandCentreRouteLayout from "./layouts/CommandCentreRouteLayout.tsx";
import RouteLoadingState from "./components/ui/RouteLoadingState.tsx";

const LoginPage = lazy(() => import("./pages/LoginPage.tsx"));
const DashboardPage = lazy(() => import("./pages/DashboardPage.tsx"));
const ExecutiveDashboardPage = lazy(() => import("./pages/ExecutiveDashboardPage.tsx"));
const ProfitabilityAnalyticsPage = lazy(() => import("./pages/ProfitabilityAnalyticsPage.tsx"));
const OperationalForecastingPage = lazy(() => import("./pages/OperationalForecastingPage.tsx"));
const RFQOperationsPage = lazy(() => import("./pages/RFQOperationsPage.tsx"));
const SourceHealthPage = lazy(() => import("./pages/SourceHealthPage.tsx"));
const QualificationInsightsPage = lazy(() => import("./pages/QualificationInsightsPage.tsx"));
const PricingEvidencePage = lazy(() => import("./pages/PricingEvidencePage.tsx"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage.tsx"));
const OperatorProductivityPage = lazy(() => import("./pages/OperatorProductivityPage.tsx"));
const QueueOptimizationPage = lazy(() => import("./pages/QueueOptimizationPage.tsx"));
const ReviewEfficiencyPage = lazy(() => import("./pages/ReviewEfficiencyPage.tsx"));
const GovernancePage = lazy(() => import("./pages/GovernancePage.tsx"));
const GovernanceCompliancePage = lazy(() => import("./pages/GovernanceCompliancePage.tsx"));
const AuditDefensibilityPage = lazy(() => import("./pages/AuditDefensibilityPage.tsx"));
const ComplianceReportingPage = lazy(() => import("./pages/ComplianceReportingPage.tsx"));
const OperatorOperationsPage = lazy(() => import("./pages/OperatorOperationsPage.tsx"));
const OperatorAssignmentsPage = lazy(() => import("./pages/OperatorAssignmentsPage.tsx"));
const RuntimeOperationsPage = lazy(() => import("./pages/RuntimeOperationsPage.tsx"));
const OperationalAnalyticsPage = lazy(() => import("./pages/OperationalAnalyticsPage.tsx"));
const IncidentManagementPage = lazy(() => import("./pages/IncidentManagementPage.tsx"));
const ObservabilityPage = lazy(() => import("./pages/ObservabilityPage.tsx"));
const SLAMonitoringPage = lazy(() => import("./pages/SLAMonitoringPage.tsx"));
const RuntimeAnomaliesPage = lazy(() => import("./pages/RuntimeAnomaliesPage.tsx"));
const StabilizationOperationsPage = lazy(() => import("./pages/StabilizationOperationsPage.tsx"));
const OperatorFeedbackPage = lazy(() => import("./pages/OperatorFeedbackPage.tsx"));
const RuntimeReliabilityPage = lazy(() => import("./pages/RuntimeReliabilityPage.tsx"));
const ActivityTimelinePage = lazy(() => import("./pages/ActivityTimelinePage.tsx"));
const DebugHitTestPage = lazy(() => import("./pages/DebugHitTestPage.tsx"));
const DebugNavigationPage = lazy(() => import("./pages/DebugNavigationPage.tsx"));

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
          <Route path="/__debug/navigation" element={<DebugNavigationPage />} />
          <Route
            element={
              <RequireRole>
                <CommandCentreRouteLayout />
              </RequireRole>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/executive-dashboard" element={<ExecutiveDashboardPage />} />
            <Route path="/profitability-analytics" element={<ProfitabilityAnalyticsPage />} />
            <Route path="/operational-forecasting" element={<OperationalForecastingPage />} />
            <Route path="/operations" element={<RFQOperationsPage />} />
            <Route
              path="/source-health"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <SourceHealthPage />
                </RequireRole>
              }
            />
            <Route path="/qualification-insights" element={<QualificationInsightsPage />} />
            <Route path="/pricing-evidence" element={<PricingEvidencePage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/operator-productivity" element={<OperatorProductivityPage />} />
            <Route path="/queue-optimization" element={<QueueOptimizationPage />} />
            <Route path="/review-efficiency" element={<ReviewEfficiencyPage />} />
            <Route path="/governance" element={<GovernancePage />} />
            <Route
              path="/governance-compliance"
              element={
                <RequireRole permissions={["view_governance"]}>
                  <GovernanceCompliancePage />
                </RequireRole>
              }
            />
            <Route
              path="/audit-defensibility"
              element={
                <RequireRole permissions={["view_audit"]}>
                  <AuditDefensibilityPage />
                </RequireRole>
              }
            />
            <Route
              path="/compliance-reporting"
              element={
                <RequireRole permissions={["view_governance", "view_audit"]}>
                  <ComplianceReportingPage />
                </RequireRole>
              }
            />
            <Route path="/operator-operations" element={<OperatorOperationsPage />} />
            <Route path="/operator-assignments" element={<OperatorAssignmentsPage />} />
            <Route
              path="/runtime-operations"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <RuntimeOperationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/operational-analytics"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <OperationalAnalyticsPage />
                </RequireRole>
              }
            />
            <Route
              path="/incident-management"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <IncidentManagementPage />
                </RequireRole>
              }
            />
            <Route
              path="/observability"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <ObservabilityPage />
                </RequireRole>
              }
            />
            <Route
              path="/sla-monitoring"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <SLAMonitoringPage />
                </RequireRole>
              }
            />
            <Route
              path="/runtime-anomalies"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <RuntimeAnomaliesPage />
                </RequireRole>
              }
            />
            <Route
              path="/stabilization-operations"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <StabilizationOperationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/operator-feedback"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <OperatorFeedbackPage />
                </RequireRole>
              }
            />
            <Route
              path="/runtime-reliability"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <RuntimeReliabilityPage />
                </RequireRole>
              }
            />
            <Route path="/activity-timeline" element={<ActivityTimelinePage />} />
            <Route path="/__debug/hit-test" element={<DebugHitTestPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
