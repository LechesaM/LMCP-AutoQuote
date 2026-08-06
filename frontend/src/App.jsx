import { lazy, Suspense, useEffect, useState } from "react";
import {
  Activity,
  BadgeCheck,
  BrainCircuit,
  Calculator,
  BarChart3,
  ClipboardList,
  Cpu,
  Building2,
  Bell,
  FileText,
  Factory,
  LayoutDashboard,
  ListChecks,
  PackageCheck,
  PlugZap,
  Puzzle,
  Search,
  ScrollText,
  Send,
  Settings,
  Layers3,
  ShieldCheck,
  Gauge,
  TrendingUp,
  FlaskConical,
} from "lucide-react";
import {
  API_BASE,
  getAutonomousStatus,
  getOperatorSession,
  getDashboardSummary,
  getAgentCoordinationHealth,
  getAgentCoordinationAgents,
  getAgentCoordinationTasks,
  getAgentCoordinationPlans,
  getAgentCoordinationApiContract,
  getCrossOrganizationHealth,
  getCrossOrganizationOrganizations,
  getCrossOrganizationCounterparties,
  getCrossOrganizationInteractions,
  getCrossOrganizationRequests,
  getCrossOrganizationResponses,
  getCrossOrganizationApiContract,
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
  getWorkManagementItems,
  getWorkManagementReadiness,
  getPolicy,
  getPolicyDecisionContract,
  getPolicyDecisionEvaluations,
  getPolicyDecisionHealth,
  getPolicyDecisionPolicies,
  getApprovalsHealth,
  getApprovals,
  getApprovalsPending,
  getApprovalsEscalated,
  getApprovalsHistory,
  getApprovalsApiContract,
  getRfqLifecycleMissionControl,
  getRfqLifecycleAnalytics,
  getRfqLifecycleTelemetry,
  getResourceCapacityHealth,
  getResourceCapacityResources,
  getResourceCapacityMetrics,
  getResourceCapacityConstraints,
  getResourceCapacityForecasts,
  getResourceCapacityRecommendations,
  getResourceCapacityApiContract,
  getEnterpriseSimulationHealth,
  getEnterpriseSimulationScenarios,
  getEnterpriseSimulationApiContract,
  updatePolicy,
  runAutonomousOnce,
  bootstrapOperatorAdmin,
  loginOperator,
  logoutOperator,
} from "./services/api";
import { getPlatformFoundationSnapshot } from "./services/platformFoundationApi";
import { getMultiTenantArchitectureSnapshot } from "./services/multiTenantArchitectureApi";
import { getEnterpriseApiPlatformSnapshot } from "./services/enterpriseApiPlatformApi";
import { getExternalIntegrationFrameworkSnapshot } from "./services/externalIntegrationFrameworkApi";
import { getPluginExtensionFrameworkSnapshot } from "./services/pluginExtensionFrameworkApi";
import { getCustomerSelfServicePortalSnapshot } from "./services/customerSelfServicePortalApi";
import { getCustomerIdentitySnapshot } from "./services/customerIdentityApi";
import { getCustomerDashboardSnapshot } from "./services/customerDashboardApi";
import { getCustomerRfqQuoteWorkspaceSnapshot } from "./services/customerRfqQuoteApi";
import "./App.css";
import "./components/SupplierIntelligenceWorkspace.css";
import WebSocketAutoConnector from "./components/WebSocketAutoConnector";

const DashboardWorkspace = lazy(() => import("./components/DashboardWorkspace"));
const MissionControlLanding = lazy(() => import("./components/MissionControlLanding"));
const DecisionPackWorkspace = lazy(() => import("./components/DecisionPackWorkspace"));
const PortalWorkersWorkspace = lazy(() => import("./components/PortalWorkersWorkspace"));
const ProofAuditCentreWorkspace = lazy(() => import("./components/ProofAuditCentreWorkspace"));
const QuotePackEngineWorkspace = lazy(() => import("./components/QuotePackEngineWorkspace"));
const RfqOperationsWorkspace = lazy(() => import("./components/RfqOperationsWorkspace"));
const SubmissionCentreWorkspace = lazy(() => import("./components/SubmissionCentreWorkspace"));
const BuyerIntelligenceWorkspace = lazy(() => import("./components/BuyerIntelligenceWorkspace"));
const DecisionSupportWorkspace = lazy(() => import("./components/DecisionSupportWorkspace"));
const EnterpriseOptimizationWorkspace = lazy(() => import("./components/EnterpriseOptimizationWorkspace"));
const PredictiveAnalyticsWorkspace = lazy(() => import("./components/PredictiveAnalyticsWorkspace"));
const ResourceCapacityWorkspace = lazy(() => import("./components/ResourceCapacityWorkspace"));
const CrossOrganizationWorkspace = lazy(() => import("./components/CrossOrganizationWorkspace"));
const EnterpriseSimulationWorkspace = lazy(() => import("./components/EnterpriseSimulationWorkspace"));
const SupplierIntelligenceWorkspace = lazy(() => import("./components/SupplierIntelligenceWorkspace"));
const WeeklyIntelligenceReportWorkspace = lazy(() => import("./components/WeeklyIntelligenceReportWorkspace"));
const WorkflowOrchestratorWorkspace = lazy(() => import("./components/WorkflowOrchestratorWorkspace"));
const EnterprisePlatformWorkspace = lazy(() => import("./components/EnterprisePlatformWorkspace"));
const MultiTenantArchitectureWorkspace = lazy(() => import("./components/MultiTenantArchitectureWorkspace"));
const EnterpriseApiPlatformWorkspace = lazy(() => import("./components/EnterpriseApiPlatformWorkspace"));
const ExternalIntegrationFrameworkWorkspace = lazy(() => import("./components/ExternalIntegrationFrameworkWorkspace"));
const PluginExtensionFrameworkWorkspace = lazy(() => import("./components/PluginExtensionFrameworkWorkspace"));
const CustomerSelfServicePortalWorkspace = lazy(() => import("./components/CustomerSelfServicePortalWorkspace"));
const CustomerIdentityWorkspace = lazy(() => import("./components/CustomerIdentityWorkspace"));
const CustomerDashboardWorkspace = lazy(() => import("./components/CustomerDashboardWorkspace"));
const CustomerRfqQuoteWorkspace = lazy(() => import("./components/CustomerRfqQuoteWorkspace"));

const REFRESH_MS = 15000;
const navItems = [
  { key: "mission-control", label: "Mission Control", icon: LayoutDashboard, workspace: "mission-control" },
  { key: "production-readiness", label: "Production Readiness", icon: ShieldCheck, targetId: "production-readiness" },
  { key: "harvest-operations", label: "Harvest Operations", icon: Factory, targetId: "harvest-operations" },
  { key: "search", label: "Search", icon: Search, targetId: "enterprise-search" },
  { key: "alerts", label: "Alerts", icon: Bell, targetId: "alerts" },
  { key: "trends", label: "Trends", icon: TrendingUp, targetId: "trends" },
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
  { key: "buyer-intelligence", label: "Customer & Buyer Intelligence", icon: Building2, workspace: "buyer-intelligence" },
  { key: "decision-support", label: "Decision Support", icon: Gauge, workspace: "decision-support" },
  { key: "enterprise-optimization", label: "Enterprise Optimization", icon: BarChart3, workspace: "enterprise-optimization" },
  { key: "predictive-analytics", label: "Predictive Analytics", icon: TrendingUp, workspace: "predictive-analytics" },
  { key: "resource-capacity", label: "Resource Capacity", icon: BarChart3, workspace: "resource-capacity" },
  { key: "cross-organization", label: "Cross-Organisation", icon: Building2, workspace: "cross-organization" },
  { key: "enterprise-simulation", label: "Simulation", icon: FlaskConical, workspace: "enterprise-simulation" },
  { key: "supplier-intelligence", label: "Supplier Intelligence", icon: Factory, workspace: "supplier-intelligence" },
  { key: "platform-foundation", label: "Platform Foundation", icon: Layers3, workspace: "platform-foundation" },
  { key: "multi-tenant-architecture", label: "Multi-Tenant Architecture", icon: Building2, workspace: "multi-tenant-architecture" },
  { key: "enterprise-api-platform", label: "Enterprise API Platform", icon: Settings, workspace: "enterprise-api-platform" },
  { key: "external-integration-framework", label: "External Integration Framework", icon: PlugZap, workspace: "external-integration-framework" },
  { key: "plugin-extension-framework", label: "Plugin & Extension Framework", icon: Puzzle, workspace: "plugin-extension-framework" },
  { key: "customer-self-service-portal", label: "Customer Self-Service Portal", icon: FileText, workspace: "customer-self-service-portal" },
  { key: "customer-identity", label: "Customer Identity & Authentication", icon: BadgeCheck, workspace: "customer-identity" },
  { key: "customer-dashboard", label: "Customer Dashboard", icon: Gauge, workspace: "customer-dashboard" },
  { key: "customer-rfq-quotes", label: "RFQ & Quote Workspace", icon: FileText, workspace: "customer-rfq-quotes" },
  { key: "proof-centre", label: "Evidence Centre", icon: ShieldCheck, targetId: "submission-centre" },
  { key: "portal-health", label: "Portal Health", icon: Activity, targetId: "portal-health" },
  { key: "portal-workers", label: "Review Operations", icon: Cpu, workspace: "portal-workers" },
  { key: "workers", label: "Queue Monitor", icon: Cpu, targetId: "rfq-intelligence" },
  { key: "compliance", label: "Compliance Review", icon: BadgeCheck, targetId: "rfq-intelligence" },
  { key: "audit-trail", label: "Audit Trail", icon: ScrollText, targetId: "submission-centre" },
  { key: "legacy-dashboard", label: "Legacy Dashboard", icon: LayoutDashboard, workspace: "legacy-dashboard" },
  { key: "settings", label: "Settings", icon: Settings },
];
export default function App() {
  const [state, setState] = useState({ loading: true, lastUpdated: null });
  const [busy, setBusy] = useState(false);
  const [activeWorkspace, setActiveWorkspace] = useState("mission-control");
  const [operatorAuthState, setOperatorAuthState] = useState({ loading: true, session: null, error: "" });
  const [complianceCatalog, setComplianceCatalog] = useState({ loading: true, items: [], error: "" });
  const [compliancePackId, setCompliancePackId] = useState("");
  const [complianceSummaryState, setComplianceSummaryState] = useState({ loading: false, data: null, error: "", loadedPackId: "" });
  const [simulationState, setSimulationState] = useState({ loading: true, health: null, scenarios: [], contract: null });
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
    const [health, workflow, auto, summary, opps, subSummary, profit, history, portal, radar, policy, policyDecisionHealth, policyDecisionPolicies, policyDecisionEvaluations, policyDecisionContract, approvalHealth, approvalRecords, approvalPending, approvalEscalated, approvalHistory, approvalContract, lifecycle, lifecycleAnalytics, lifecycleTelemetry, workManagementReadiness, workManagementItems, agentCoordinationHealth, agentCoordinationAgents, agentCoordinationTasks, agentCoordinationPlans, agentCoordinationApiContract, resourceCapacityHealth, resourceCapacityResources, resourceCapacityMetrics, resourceCapacityConstraints, resourceCapacityForecasts, resourceCapacityRecommendations, resourceCapacityApiContract, crossOrganizationHealth, crossOrganizationOrganizations, crossOrganizationCounterparties, crossOrganizationInteractions, crossOrganizationRequests, crossOrganizationResponses, crossOrganizationApiContract, enterpriseSimulationHealth, enterpriseSimulationScenarios, enterpriseSimulationApiContract, platformFoundationSnapshot, multiTenantArchitectureSnapshot, enterpriseApiPlatformSnapshot, externalIntegrationFrameworkSnapshot, pluginExtensionFrameworkSnapshot, customerSelfServicePortalSnapshot, customerIdentitySnapshot, customerDashboardSnapshot, customerRfqQuoteWorkspaceSnapshot] = await Promise.all([
      getHealth(), getWorkflowHealth(), getAutonomousStatus(), getDashboardSummary(), getOpportunities(), getSubmissionSummary(), getSubmissionProfit(), getSubmissionHistory(), getPortalHealth(), getRadarStatus(), getPolicy(), getPolicyDecisionHealth(), getPolicyDecisionPolicies(), getPolicyDecisionEvaluations(), getPolicyDecisionContract(), getApprovalsHealth(), getApprovals(), getApprovalsPending(), getApprovalsEscalated(), getApprovalsHistory(), getApprovalsApiContract(), getRfqLifecycleMissionControl(), getRfqLifecycleAnalytics(), getRfqLifecycleTelemetry(), getWorkManagementReadiness(), getWorkManagementItems(), getAgentCoordinationHealth(), getAgentCoordinationAgents(), getAgentCoordinationTasks(), getAgentCoordinationPlans(), getAgentCoordinationApiContract(), getResourceCapacityHealth(), getResourceCapacityResources(), getResourceCapacityMetrics(), getResourceCapacityConstraints(), getResourceCapacityForecasts(), getResourceCapacityRecommendations(), getResourceCapacityApiContract(), getCrossOrganizationHealth(), getCrossOrganizationOrganizations(), getCrossOrganizationCounterparties(), getCrossOrganizationInteractions(), getCrossOrganizationRequests(), getCrossOrganizationResponses(), getCrossOrganizationApiContract(), getEnterpriseSimulationHealth(), getEnterpriseSimulationScenarios(), getEnterpriseSimulationApiContract(),
      getPlatformFoundationSnapshot(),
      getMultiTenantArchitectureSnapshot(),
      getEnterpriseApiPlatformSnapshot(),
      getExternalIntegrationFrameworkSnapshot(),
      getPluginExtensionFrameworkSnapshot(),
      getCustomerSelfServicePortalSnapshot(),
      getCustomerIdentitySnapshot(),
      getCustomerDashboardSnapshot(),
      getCustomerRfqQuoteWorkspaceSnapshot(),
    ]);
    setState({
      health,
      workflow,
      auto,
      summary,
      opps,
      subSummary,
      profit,
      history,
      portal,
      radar,
      policy,
      policyDecision: {
        health: policyDecisionHealth,
        policies: Array.isArray(policyDecisionPolicies?.policies) ? policyDecisionPolicies.policies : [],
        evaluations: Array.isArray(policyDecisionEvaluations?.evaluations) ? policyDecisionEvaluations.evaluations : [],
        contract: policyDecisionContract,
      },
      approvals: {
        health: approvalHealth,
        approvals: Array.isArray(approvalRecords?.approvals) ? approvalRecords.approvals : [],
        pending: Array.isArray(approvalPending?.approvals) ? approvalPending.approvals : [],
        escalated: Array.isArray(approvalEscalated?.approvals) ? approvalEscalated.approvals : [],
        history: Array.isArray(approvalHistory?.approvals) ? approvalHistory.approvals : [],
        contract: approvalContract,
      },
      lifecycle,
      lifecycleAnalytics,
      lifecycleTelemetry,
      workManagement: {
        readiness: workManagementReadiness,
        items: Array.isArray(workManagementItems?.items) ? workManagementItems.items : [],
        queues: Array.isArray(workManagementItems?.queues) ? workManagementItems.queues : [],
      },
      agentCoordination: {
        health: agentCoordinationHealth,
        agents: Array.isArray(agentCoordinationAgents?.agents) ? agentCoordinationAgents.agents : [],
        tasks: Array.isArray(agentCoordinationTasks?.tasks) ? agentCoordinationTasks.tasks : [],
        plans: Array.isArray(agentCoordinationPlans?.plans) ? agentCoordinationPlans.plans : [],
        apiContract: agentCoordinationApiContract,
      },
      resourceCapacity: {
        health: resourceCapacityHealth,
        resources: Array.isArray(resourceCapacityResources?.items) ? resourceCapacityResources.items : [],
        metrics: Array.isArray(resourceCapacityMetrics?.items) ? resourceCapacityMetrics.items : [],
        constraints: Array.isArray(resourceCapacityConstraints?.items) ? resourceCapacityConstraints.items : [],
        forecasts: Array.isArray(resourceCapacityForecasts?.items) ? resourceCapacityForecasts.items : [],
        recommendations: Array.isArray(resourceCapacityRecommendations?.items) ? resourceCapacityRecommendations.items : [],
        apiContract: resourceCapacityApiContract,
      },
      crossOrganization: {
        health: crossOrganizationHealth,
        organizations: Array.isArray(crossOrganizationOrganizations?.items) ? crossOrganizationOrganizations.items : [],
        counterparties: Array.isArray(crossOrganizationCounterparties?.items) ? crossOrganizationCounterparties.items : [],
        interactions: Array.isArray(crossOrganizationInteractions?.items) ? crossOrganizationInteractions.items : [],
        requests: Array.isArray(crossOrganizationRequests?.items) ? crossOrganizationRequests.items : [],
        responses: Array.isArray(crossOrganizationResponses?.items) ? crossOrganizationResponses.items : [],
        apiContract: crossOrganizationApiContract,
      },
      enterpriseSimulation: {
        health: enterpriseSimulationHealth,
        scenarios: Array.isArray(enterpriseSimulationScenarios?.items) ? enterpriseSimulationScenarios.items : [],
        apiContract: enterpriseSimulationApiContract,
      },
      platformFoundation: platformFoundationSnapshot,
      multiTenantArchitecture: multiTenantArchitectureSnapshot,
      enterpriseApiPlatform: enterpriseApiPlatformSnapshot,
      externalIntegrationFramework: externalIntegrationFrameworkSnapshot,
      pluginExtensionFramework: pluginExtensionFrameworkSnapshot,
      customerSelfServicePortal: customerSelfServicePortalSnapshot,
      customerIdentity: customerIdentitySnapshot,
      customerDashboard: customerDashboardSnapshot,
      customerRfqQuoteWorkspace: customerRfqQuoteWorkspaceSnapshot,
      loading: false,
      lastUpdated: new Date(),
    });
    setSimulationState({
      loading: false,
      health: enterpriseSimulationHealth,
      scenarios: Array.isArray(enterpriseSimulationScenarios?.items) ? enterpriseSimulationScenarios.items : [],
      contract: enterpriseSimulationApiContract,
    });
  }

  useEffect(() => {
    void Promise.resolve().then(() => load());
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => refreshOperatorSession());
  }, []);

  useEffect(() => {
    function openQuotePackWorkspace(event) {
      const packId = String(event?.detail?.packId || "").trim();

      if (packId) {
        window.sessionStorage.setItem(
          "lmcp-selected-quote-pack-id",
          packId
        );
      }

      setActiveWorkspace("quote-pack-engine");
    }

    window.addEventListener(
      "lmcp-open-quote-pack",
      openQuotePackWorkspace
    );

    return () => {
      window.removeEventListener(
        "lmcp-open-quote-pack",
        openQuotePackWorkspace
      );
    };
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
  const backendStatus = state.health?.status || "unknown";

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

  function navigateTo(target) {
    const workspaceTargets = new Set([
      "mission-control",
      "legacy-dashboard",
      "workflow-orchestrator",
      "portal-workers",
      "proof-audit-centre",
      "weekly-report",
      "buyer-intelligence",
      "decision-support",
      "predictive-analytics",
      "supplier-intelligence",
      "platform-foundation",
      "multi-tenant-architecture",
      "enterprise-api-platform",
      "external-integration-framework",
      "plugin-extension-framework",
      "customer-self-service-portal",
      "customer-identity",
      "customer-dashboard",
      "customer-rfq-quotes",
      "submission-centre",
      "quote-pack-engine",
      "decision-pack",
      "rfq-operations",
      "cross-organization",
      "enterprise-simulation",
    ]);

    if (workspaceTargets.has(target)) {
      setActiveWorkspace(target);
      return;
    }

    setActiveWorkspace("mission-control");
    requestAnimationFrame(() => {
      document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function selectWorkspace(item) {
    if (item.workspace) {
      setActiveWorkspace(item.workspace);
      return;
    }
    setActiveWorkspace("mission-control");
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
    resourceCapacity: state.resourceCapacity,
    crossOrganization: state.crossOrganization,
    enterpriseSimulation: simulationState,
    platformFoundation: state.platformFoundation || { loading: true, status: "NO_DATA", capabilities: [], services: [], modules: [], extensionPoints: [] },
    multiTenantArchitecture: state.multiTenantArchitecture || {
      loading: true,
      status: "NO_DATA",
      tenantIdentity: null,
      tenantRegistry: { tenant_count: 0, records: [] },
      tenantContextContract: null,
      tenantIsolation: null,
      tenantConfiguration: null,
      tenantCapabilityModel: { capabilities: [] },
      tenantServiceModel: { services: [] },
      tenantModuleModel: { modules: [] },
    },
    enterpriseApiPlatform: state.enterpriseApiPlatform || {
      loading: true,
      status: "NO_DATA",
      identity: null,
      registry: [],
      domains: [],
      classification: [],
      lifecycle: null,
      versions: null,
      compatibility: null,
      exposure: [],
      authenticationAuthorisation: null,
      tenantContext: null,
      policy: null,
      rateLimitQuota: null,
      requestResponse: null,
      errorContract: null,
      queryContract: null,
      idempotency: null,
      audit: null,
      observability: null,
      openapiGovernance: null,
      diagnostics: null,
      apiContract: null,
    },
    externalIntegrationFramework: state.externalIntegrationFramework || {
      loading: true,
      status: "NO_DATA",
      connectorActivation: null,
      identity: null,
      registry: [],
      connectors: [],
      adapters: [],
      providers: [],
      classification: [],
      lifecycle: null,
      compatibility: null,
      policy: null,
      authenticationAuthorisation: null,
      credentialReference: null,
      transformation: [],
      messageContract: null,
      eventModel: [],
      commandResponse: null,
      resilience: null,
      circuitBreaker: null,
      idempotency: null,
      deadLetter: null,
      tenantContext: null,
      audit: null,
      observability: null,
      diagnostics: null,
      apiContract: null,
    },
      pluginExtensionFramework: state.pluginExtensionFramework || {
        loading: true,
        status: "NO_DATA",
      identity: null,
      manifestContract: null,
      registry: [],
      extensionPoints: [],
      capabilities: [],
      classification: [],
      lifecycle: null,
      dependencies: [],
      compatibility: null,
      permissions: [],
      trust: null,
      certification: null,
      packageIntegrity: null,
      configuration: null,
      tenantContext: null,
      policy: null,
      audit: null,
      observability: null,
      diagnostics: null,
      persistence: null,
      apiContract: null,
      health: null,
      readiness: null,
      missionControlIntegration: null,
        frontendExperience: null,
        counts: { plugins: 0, extensionPoints: 0, capabilities: 0, disabledPlugins: 0, certificationRequired: 0 },
      },
      customerSelfServicePortal: state.customerSelfServicePortal || {
        loading: true,
        status: "NO_DATA",
        identity: null,
        registry: [],
        features: [],
        extensionPoints: [],
        permissions: [],
        tenantContext: null,
        policy: null,
        audit: null,
        diagnostics: null,
        compatibility: null,
        configuration: null,
        lifecycle: null,
        readiness: null,
        health: null,
        missionControlIntegration: null,
        frontendExperience: null,
        apiContract: null,
        counts: { features: 0, extensionPoints: 0, permissions: 0 },
      },
      customerIdentity: state.customerIdentity || {
        loading: true,
        status: "NO_DATA",
        identity: null,
        roles: [],
        permissions: [],
        tenantContext: null,
        sessionPolicy: null,
        policy: null,
        audit: null,
        diagnostics: null,
        compatibility: null,
        configuration: null,
        lifecycle: null,
        readiness: null,
        health: null,
        missionControlIntegration: null,
        frontendExperience: null,
        apiContract: null,
        counts: { roles: 0, permissions: 0, deniedPermissions: 0 },
      },
      customerDashboard: state.customerDashboard || {
        loading: true,
        status: "NO_DATA",
        identity: null,
        summary: null,
        sections: [],
        widgets: [],
        organisation: null,
        rfqs: null,
        quotations: null,
        activity: null,
        notifications: null,
        policy: null,
        audit: null,
        observability: null,
        compatibility: null,
        lifecycle: null,
        readiness: null,
        health: null,
        diagnostics: null,
        apiContract: null,
        missionControlIntegration: null,
        frontendExperience: null,
        counts: { sections: 0, widgets: 0 },
      },
      customerRfqQuoteWorkspace: state.customerRfqQuoteWorkspace || {
        loading: true,
        status: "NO_DATA",
        identity: null,
        rfqs: null,
        quotations: null,
        rfqLifecycle: null,
        quotationLifecycle: null,
        sourceAuthority: null,
        freshness: null,
        policy: null,
        audit: null,
        observability: null,
        compatibility: null,
        health: null,
        readiness: null,
        diagnostics: null,
        apiContract: null,
        missionControlIntegration: null,
        frontendExperience: null,
        counts: { rfqs: 0, quotations: 0 },
      },
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
    refreshAll: load,
    navigate: navigateTo,
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
          {activeWorkspace === "mission-control" || activeWorkspace === "dashboard" ? (
            <MissionControlLanding view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "legacy-dashboard" ? (
            <DashboardWorkspace view={{ ...dashboardView, legacyMode: true }} />
          ) : activeWorkspace === "workflow-orchestrator" ? (
            <WorkflowOrchestratorWorkspace />
          ) : activeWorkspace === "portal-workers" ? (
            <PortalWorkersWorkspace />
          ) : activeWorkspace === "proof-audit-centre" ? (
            <ProofAuditCentreWorkspace />
          ) : activeWorkspace === "weekly-report" ? (
            <WeeklyIntelligenceReportWorkspace />
          ) : activeWorkspace === "buyer-intelligence" ? (
            <BuyerIntelligenceWorkspace />
          ) : activeWorkspace === "decision-support" ? (
            <DecisionSupportWorkspace />
          ) : activeWorkspace === "enterprise-optimization" ? (
            <EnterpriseOptimizationWorkspace />
          ) : activeWorkspace === "predictive-analytics" ? (
            <PredictiveAnalyticsWorkspace />
          ) : activeWorkspace === "resource-capacity" ? (
            <ResourceCapacityWorkspace />
          ) : activeWorkspace === "cross-organization" ? (
            <CrossOrganizationWorkspace />
          ) : activeWorkspace === "enterprise-simulation" ? (
            <EnterpriseSimulationWorkspace />
          ) : activeWorkspace === "supplier-intelligence" ? (
            <SupplierIntelligenceWorkspace />
          ) : activeWorkspace === "platform-foundation" ? (
            <EnterprisePlatformWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "multi-tenant-architecture" ? (
            <MultiTenantArchitectureWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "enterprise-api-platform" ? (
            <EnterpriseApiPlatformWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "external-integration-framework" ? (
            <ExternalIntegrationFrameworkWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "plugin-extension-framework" ? (
            <PluginExtensionFrameworkWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "customer-self-service-portal" ? (
            <CustomerSelfServicePortalWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "customer-identity" ? (
            <CustomerIdentityWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "customer-dashboard" ? (
            <CustomerDashboardWorkspace view={dashboardView} onNavigate={navigateTo} />
          ) : activeWorkspace === "customer-rfq-quotes" ? (
            <CustomerRfqQuoteWorkspace view={dashboardView} onNavigate={navigateTo} />
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
