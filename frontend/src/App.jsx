import { lazy, Suspense, useEffect, useState } from "react";
import {
  Activity,
  BadgeCheck,
  BrainCircuit,
  Calculator,
  ClipboardList,
  Cpu,
  FileText,
  LayoutDashboard,
  ListChecks,
  PackageCheck,
  ScrollText,
  Send,
  Settings,
  ShieldCheck,
} from "lucide-react";
import {
  API_BASE,
  getAutonomousStatus,
  getOperatorSession,
  getDashboardSummary,
  getHealth,
  getOpportunities,
  getPortalHealth,
  getRadarStatus,
  getWorkflowHealth,
  getQuoteCompilationComplianceSummary,
  getQuoteCompilationLatestPack,
  getQuoteCompilationPacks,
  getSubmissionHistory,
  getSubmissionProfit,
  getSubmissionSummary,
  getPolicy,
  getRfqLifecycleMissionControl,
  getRfqLifecycleAnalytics,
  getRfqLifecycleTelemetry,
  updatePolicy,
  runAutonomousOnce,
  bootstrapOperatorAdmin,
  loginOperator,
  logoutOperator,
} from "./services/api";
import "./App.css";
import WebSocketAutoConnector from "./components/WebSocketAutoConnector";

const DashboardWorkspace = lazy(() => import("./components/DashboardWorkspace"));
const DecisionPackWorkspace = lazy(() => import("./components/DecisionPackWorkspace"));
const PortalWorkersWorkspace = lazy(() => import("./components/PortalWorkersWorkspace"));
const ProofAuditCentreWorkspace = lazy(() => import("./components/ProofAuditCentreWorkspace"));
const QuotePackEngineWorkspace = lazy(() => import("./components/QuotePackEngineWorkspace"));
const RfqOperationsWorkspace = lazy(() => import("./components/RfqOperationsWorkspace"));
const SubmissionCentreWorkspace = lazy(() => import("./components/SubmissionCentreWorkspace"));
const WeeklyIntelligenceReportWorkspace = lazy(() => import("./components/WeeklyIntelligenceReportWorkspace"));
const WorkflowOrchestratorWorkspace = lazy(() => import("./components/WorkflowOrchestratorWorkspace"));

const REFRESH_MS = 15000;
const navItems = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, workspace: "dashboard" },
  { key: "rfq-operations", label: "RFQ Operations", icon: ClipboardList, workspace: "rfq-operations" },
  { key: "workflow-orchestrator", label: "Review Workflow", icon: Activity, workspace: "workflow-orchestrator" },
  { key: "rfq-intelligence", label: "RFQ Intelligence", icon: BrainCircuit, targetId: "rfq-intelligence" },
  { key: "harvest-queue", label: "Review Queue", icon: ListChecks, targetId: "harvest-queue" },
  { key: "quote-pack-engine", label: "Quote Pack Engine", icon: PackageCheck, workspace: "quote-pack-engine" },
  { key: "decision-pack", label: "Decision Pack", icon: LayoutDashboard, workspace: "decision-pack" },
  { key: "quote-engine", label: "Pricing Review", icon: Calculator, targetId: "quote-engine" },
  { key: "submission-centre", label: "Approval Centre", icon: Send, workspace: "submission-centre" },
  { key: "proof-audit-centre", label: "Review Audit Centre", icon: ScrollText, workspace: "proof-audit-centre" },
  { key: "weekly-report", label: "Weekly Report", icon: FileText, workspace: "weekly-report" },
  { key: "proof-centre", label: "Evidence Centre", icon: ShieldCheck, targetId: "submission-centre" },
  { key: "portal-health", label: "Portal Health", icon: Activity, targetId: "portal-health" },
  { key: "portal-workers", label: "Review Operations", icon: Cpu, workspace: "portal-workers" },
  { key: "workers", label: "Queue Monitor", icon: Cpu, targetId: "rfq-intelligence" },
  { key: "compliance", label: "Compliance Review", icon: BadgeCheck, targetId: "rfq-intelligence" },
  { key: "audit-trail", label: "Audit Trail", icon: ScrollText, targetId: "submission-centre" },
  { key: "settings", label: "Settings", icon: Settings },
];
export default function App() {
  const [state, setState] = useState({ loading: true, lastUpdated: null });
  const [busy, setBusy] = useState(false);
  const [activeWorkspace, setActiveWorkspace] = useState("dashboard");
  const [operatorAuthState, setOperatorAuthState] = useState({ loading: true, session: null, error: "" });
  const [complianceCatalog, setComplianceCatalog] = useState({ loading: true, items: [], error: "" });
  const [compliancePackId, setCompliancePackId] = useState("");
  const [complianceSummaryState, setComplianceSummaryState] = useState({ loading: false, data: null, error: "", loadedPackId: "" });
  const [showWorkflowRaw, setShowWorkflowRaw] = useState(false);

  async function loadComplianceSummary(packId) {
    const safePackId = String(packId || "").trim();
    if (!safePackId) {
      setComplianceSummaryState({ loading: false, data: null, error: "Select a pack ID to load a compliance summary.", loadedPackId: "" });
      return;
    }
    setComplianceSummaryState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await getQuoteCompilationComplianceSummary(safePackId);
    if (result?.status === "offline" && result?.error) {
      setComplianceSummaryState({ loading: false, data: null, error: result.error || "Compliance Review summary unavailable.", loadedPackId: safePackId });
      return;
    }
    setComplianceSummaryState({
      loading: false,
      data: result,
      error: "",
      loadedPackId: safePackId,
    });
  }

  async function refreshOperatorSession() {
    setOperatorAuthState((prev) => ({ ...prev, loading: true }));
    const result = await getOperatorSession();
    if (result?.authenticated) {
      setOperatorAuthState({ loading: false, session: result, error: "" });
      return result;
    }
    const error = result?.error || result?.detail || result?.message || "";
    setOperatorAuthState({ loading: false, session: null, error });
    return null;
  }

  async function handleOperatorLogin(payload) {
    setOperatorAuthState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await loginOperator(payload);
    if (result?.authenticated) {
      setOperatorAuthState({ loading: false, session: result, error: "" });
      return result;
    }
    setOperatorAuthState({ loading: false, session: null, error: result?.error || result?.detail || result?.message || "Login failed." });
    return result;
  }

  async function handleOperatorLogout() {
    setOperatorAuthState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await logoutOperator();
    if (result?.status === "ok") {
      setOperatorAuthState({ loading: false, session: null, error: "" });
      return result;
    }
    setOperatorAuthState((prev) => ({ ...prev, loading: false, error: result?.error || result?.detail || result?.message || "Logout failed." }));
    return result;
  }

  async function handleBootstrapOperatorAdmin(payload) {
    setOperatorAuthState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await bootstrapOperatorAdmin(payload);
    if (result?.status === "ok") {
      setOperatorAuthState((prev) => ({ ...prev, loading: false, error: "" }));
      return result;
    }
    setOperatorAuthState((prev) => ({ ...prev, loading: false, error: result?.error || result?.detail || result?.message || "Bootstrap admin failed." }));
    return result;
  }

  useEffect(() => {
    let cancelled = false;

    async function loadComplianceCatalog() {
      const [packsResponse, latestResponse] = await Promise.all([
        getQuoteCompilationPacks(8),
        getQuoteCompilationLatestPack(),
      ]);
      if (cancelled) return;
      const items = Array.isArray(packsResponse?.items) ? packsResponse.items : [];
      const latestPackId = String(latestResponse?.pack_id || items[0]?.pack_id || "").trim();
      setComplianceCatalog({
        loading: false,
        items,
        error: !items.length ? "No local quote-compilation packs were found." : "",
      });
      if (latestPackId) {
        setCompliancePackId((current) => current || latestPackId);
        await loadComplianceSummary(latestPackId);
      } else {
        setComplianceSummaryState({ loading: false, data: null, error: "", loadedPackId: "" });
      }
    }

    loadComplianceCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  async function load() {
    const [health, workflow, auto, summary, opps, subSummary, profit, history, portal, radar, policy, lifecycle, lifecycleAnalytics, lifecycleTelemetry] = await Promise.all([
      getHealth(), getWorkflowHealth(), getAutonomousStatus(), getDashboardSummary(), getOpportunities(), getSubmissionSummary(), getSubmissionProfit(), getSubmissionHistory(), getPortalHealth(), getRadarStatus(), getPolicy(), getRfqLifecycleMissionControl(), getRfqLifecycleAnalytics(), getRfqLifecycleTelemetry(),
    ]);
    setState({ health, workflow, auto, summary, opps, subSummary, profit, history, portal, radar, policy, lifecycle, lifecycleAnalytics, lifecycleTelemetry, loading: false, lastUpdated: new Date() });
  }

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    refreshOperatorSession();
  }, []);

  const control = state.lifecycle?.safety?.system_control || {};
  const effectiveStatus = String(control.effective_system_status || state.policy?.policy?.mode || "controlled").toLowerCase();
  const systemOn = Boolean(
    control.system_on !== undefined
      ? control.system_on
      : effectiveStatus === "on" || effectiveStatus === "controlled"
        ? true
        : state.policy?.policy?.enabled ?? state.auto?.enabled ?? true
  );
  const backendStatus =
    state.health?.status === "healthy" || state.lifecycleTelemetry?.worker_online || (state.radar?.radar || state.radar || {}).worker_online
      ? "healthy"
      : state.health?.status || "unknown";

  async function toggleSystem() {
    setBusy(true);
    const currentPolicy = state.policy?.policy || { enabled: systemOn, mode: "controlled", allow_email_send: false, allow_portal_upload: true, allow_portal_final_submit: true };
    await updatePolicy({ ...currentPolicy, enabled: !systemOn });
    await load();
    setBusy(false);
  }

  async function runNow() {
    setBusy(true);
    await runAutonomousOnce();
    await load();
    setBusy(false);
  }

  function selectWorkspace(item) {
    if (item.workspace) {
      setActiveWorkspace(item.workspace);
      return;
    }
    setActiveWorkspace("dashboard");
    if (item.targetId) {
      requestAnimationFrame(() => {
        document.getElementById(item.targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  const dashboardView = {
    apiBase: API_BASE,
    refreshMs: REFRESH_MS,
    state,
    backendStatus,
    systemOn,
    busy,
    toggleSystem,
    runNow,
    showWorkflowRaw,
    setShowWorkflowRaw,
    compliancePackId,
    complianceCatalog,
    complianceSummaryState,
    setCompliancePackId,
    loadComplianceSummary,
  };

  return (
    <div className="command-centre-layout">
      <aside className="command-sidebar" aria-label="Command centre navigation">
        <div className="sidebar-brand">
          <span>LMCP</span>
          <b>Command Centre</b>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.workspace ? activeWorkspace === item.workspace : false;
            return (
              <button key={item.key} className={active ? "active" : ""} type="button" aria-current={active ? "page" : undefined} onClick={() => selectWorkspace(item)}>
                <Icon size={17} strokeWidth={2.2} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-status">
          <span>Backend</span>
          <b>{backendStatus}</b>
        </div>
        <div className="sidebar-status">
          <span>Operator</span>
          <b>{operatorAuthState.session?.operator?.display_name || (operatorAuthState.loading ? "loading" : "guest")}</b>
        </div>
      </aside>

      <main className="dashboard-shell dashboard-view">
        <WebSocketAutoConnector />
        <Suspense fallback={<div className="card"><p className="muted">Loading workspace...</p></div>}>
          {activeWorkspace === "dashboard" ? (
            <DashboardWorkspace view={dashboardView} />
          ) : activeWorkspace === "workflow-orchestrator" ? (
            <WorkflowOrchestratorWorkspace />
          ) : activeWorkspace === "portal-workers" ? (
            <PortalWorkersWorkspace />
          ) : activeWorkspace === "proof-audit-centre" ? (
            <ProofAuditCentreWorkspace />
          ) : activeWorkspace === "weekly-report" ? (
            <WeeklyIntelligenceReportWorkspace />
          ) : activeWorkspace === "submission-centre" ? (
            <SubmissionCentreWorkspace
              authState={operatorAuthState}
              onRefreshAuth={refreshOperatorSession}
              onLogin={handleOperatorLogin}
              onLogout={handleOperatorLogout}
              onBootstrapAdmin={handleBootstrapOperatorAdmin}
            />
          ) : activeWorkspace === "quote-pack-engine" ? (
            <QuotePackEngineWorkspace />
          ) : activeWorkspace === "decision-pack" ? (
            <DecisionPackWorkspace />
          ) : activeWorkspace === "rfq-operations" ? (
            <RfqOperationsWorkspace />
          ) : (
            <div className="card"><p className="muted">Workspace not available.</p></div>
          )}
        </Suspense>
      </main>
    </div>
  );
}
