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
const AdminDemoSeedPage = lazy(() => import("./pages/AdminDemoSeedPage.tsx"));
const SupplierQuoteIntelligencePage = lazy(() => import("./pages/SupplierQuoteIntelligencePage.tsx"));
const AutoQuoteLibrariesPage = lazy(() => import("./pages/AutoQuoteLibrariesPage.tsx"));
const AutoQuoteWeeklyReportPage = lazy(() => import("./pages/AutoQuoteWeeklyReportPage.tsx"));
const MissionControlPage = lazy(() => import("./pages/MissionControlPage.jsx"));

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
            <Route index element={<Navigate to="/review" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/mission-control" element={<MissionControlPage />} />
            <Route path="/executive-dashboard" element={<ExecutiveDashboardPage />} />
            <Route path="/profitability-analytics" element={<ProfitabilityAnalyticsPage />} />
            <Route path="/operational-forecasting" element={<OperationalForecastingPage />} />
            <Route
              path="/operations"
              element={
                <RequireRole permissions={["view_rfqs"]}>
                  <RFQOperationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/source-health"
              element={
                <RequireRole roles={["supervisor", "admin"]}>
                  <SourceHealthPage />
                </RequireRole>
              }
            />
            <Route
              path="/qualification-insights"
              element={
                <RequireRole permissions={["view_rfqs"]}>
                  <QualificationInsightsPage />
                </RequireRole>
              }
            />
            <Route
              path="/pricing-evidence"
              element={
                <RequireRole permissions={["view_rfqs"]}>
                  <PricingEvidencePage />
                </RequireRole>
              }
            />
            <Route
              path="/review"
              element={
                <RequireRole permissions={["view_operator_queue"]}>
                  <ReviewQueuePage />
                </RequireRole>
              }
            />
            <Route path="/operator-productivity" element={<OperatorProductivityPage />} />
            <Route path="/queue-optimization" element={<QueueOptimizationPage />} />
            <Route path="/review-efficiency" element={<ReviewEfficiencyPage />} />
            <Route
              path="/governance"
              element={
                <RequireRole permissions={["view_governance"]}>
                  <GovernancePage />
                </RequireRole>
              }
            />
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
            <Route
              path="/operator-operations"
              element={
                <RequireRole permissions={["view_operator_review"]}>
                  <OperatorOperationsPage />
                </RequireRole>
              }
            />
            <Route
              path="/operator-assignments"
              element={
                <RequireRole permissions={["view_operator_queue"]}>
                  <OperatorAssignmentsPage />
                </RequireRole>
              }
            />
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
            <Route
              path="/admin/demo-seed"
              element={
                <RequireRole roles={["admin"]}>
                  <AdminDemoSeedPage />
                </RequireRole>
              }
            />
            <Route
              path="/supplier-quote-intelligence"
              element={
                <RequireRole permissions={["view_supplier_quote_intelligence"]}>
                  <SupplierQuoteIntelligencePage />
                </RequireRole>
              }
            />
            <Route path="/autoquote-libraries" element={<AutoQuoteLibrariesPage />} />
            <Route path="/autoquote-weekly-report" element={<AutoQuoteWeeklyReportPage />} />
            <Route path="/activity-timeline" element={<ActivityTimelinePage />} />
            <Route path="/__debug/hit-test" element={<DebugHitTestPage />} />
            <Route path="*" element={<Navigate to="/review" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/review" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
