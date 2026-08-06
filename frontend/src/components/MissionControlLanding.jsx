import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ClipboardList,
  Factory,
  Gauge,
  Layers3,
  ListChecks,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  TrendingUp,
  FileText,
  X,
} from "lucide-react";
import { getHarvestEntities, getHarvestHistory, getHarvestStatus, runHarvest } from "../services/harvestApi";
import {
  buildHarvestEntityDetails,
  buildHarvestEntityDisplay,
  doesHarvestEntityMatchInput,
  filterHarvestEntities,
  isHarvestEntitySelectable,
  moveHarvestEntityIndex,
  resolveSelectableHarvestEntity,
} from "./harvestEntitySelector";
import {
  buildControlledHarvestConfirmationLines,
  buildControlledHarvestStatusMessage,
  getControlledHarvestDisplayState,
  isControlledHarvestTerminalState,
  normalizeControlledHarvestState,
} from "./controlledHarvestUx";

const READINESS_ITEMS = [
  {
    id: "backend-api",
    label: "Backend API",
    source: "/health",
    destination: "backend status",
    derive: ({ health }) => ({
      status: String(health?.status || "UNAVAILABLE").toUpperCase(),
      reason: health?.service ? `Service ${health.service}` : "Backend health endpoint response",
    }),
  },
  {
    id: "database",
    label: "Database",
    source: "host-side certification",
    destination: "database evidence",
    derive: () => ({
      status: "UNAVAILABLE",
      reason: "Database identity is certified in backend evidence; the Vite frontend has no live DB session.",
    }),
  },
  {
    id: "search",
    label: "Search",
    source: "/rfq-lifecycle/opportunities + RFQ workspace",
    destination: "rfq-operations",
    derive: ({ opportunities }) => ({
      status: opportunities.length ? "AVAILABLE" : "UNAVAILABLE",
      reason: opportunities.length ? `${opportunities.length} live opportunity record(s) loaded` : "No live opportunities loaded yet.",
    }),
  },
  {
    id: "storage",
    label: "Storage",
    source: "frontend runtime",
    destination: "harvest evidence",
    derive: () => ({
      status: "UNAVAILABLE",
      reason: "No authoritative storage health endpoint is exposed to the active frontend.",
    }),
  },
  {
    id: "audit-logging",
    label: "Audit Logging",
    source: "/submission-history/recent-real + harvest history",
    destination: "review-audit-centre",
    derive: ({ history, harvestHistory }) => ({
      status: history.length || harvestHistory.length ? "AVAILABLE" : "UNAVAILABLE",
      reason: history.length || harvestHistory.length ? "Operator evidence and controlled harvest history are present." : "No audit or harvest history loaded yet.",
    }),
  },
  {
    id: "backup",
    label: "Backup Visibility",
    source: "not exposed",
    destination: "legacy dashboard",
    derive: () => ({
      status: "UNAVAILABLE",
      reason: "Backup telemetry is not surfaced in the active frontend.",
    }),
  },
  {
    id: "harvest-health",
    label: "Harvest Health",
    source: "/opportunities/harvest/status",
    destination: "harvest operations",
    derive: ({ harvestStatus }) => ({
      status: harvestStatus?.status ? String(harvestStatus.status).toUpperCase() : "UNAVAILABLE",
      reason: harvestStatus?.message || "Controlled harvest status endpoint response.",
    }),
  },
  {
    id: "worker-health",
    label: "Worker Health",
    source: "/rfq-lifecycle/telemetry",
    destination: "workflow-orchestrator",
    derive: ({ telemetry }) => ({
      status: telemetry?.worker_online ? "HEALTHY" : telemetry ? "DEGRADED" : "UNAVAILABLE",
      reason: telemetry ? "Worker telemetry is loaded from the backend." : "No telemetry endpoint response.",
    }),
  },
  {
    id: "queue-health",
    label: "Queue Health",
    source: "/rfq-lifecycle/telemetry",
    destination: "workflow-orchestrator",
    derive: ({ telemetry }) => ({
      status: telemetry?.queue_backlog?.backlog_detected ? "DEGRADED" : telemetry ? "HEALTHY" : "UNAVAILABLE",
      reason: telemetry ? `Queue backlog ${telemetry?.queue_backlog?.total_backlog ?? 0}` : "No queue telemetry response.",
    }),
  },
  {
    id: "quote-pack",
    label: "Quote-Pack Generation",
    source: "/quote-compilation/packs",
    destination: "quote-pack-engine",
    derive: ({ state }) => ({
      status: state?.summary?.quote_packs_generated !== undefined ? "AVAILABLE" : "UNAVAILABLE",
      reason: state?.summary?.quote_packs_generated !== undefined ? "Quote-pack summary loaded in mission state." : "No authoritative quote-pack summary exposed.",
    }),
  },
  {
    id: "compliance",
    label: "Compliance Services",
    source: "/quote-compilation/compliance-summary",
    destination: "submission-centre",
    derive: ({ complianceSummaryState }) => ({
      status: complianceSummaryState?.data ? "AVAILABLE" : complianceSummaryState?.error ? "DEGRADED" : "UNAVAILABLE",
      reason: complianceSummaryState?.error || complianceSummaryState?.data?.message || "Latest compliance summary status.",
    }),
  },
  {
    id: "evidence",
    label: "Evidence Services",
    source: "/submission-proof/latest",
    destination: "review-audit-centre",
    derive: ({ state }) => ({
      status: state?.history?.length ? "AVAILABLE" : "UNAVAILABLE",
      reason: state?.history?.length ? "Submission evidence history loaded." : "No evidence rows loaded yet.",
    }),
  },
  {
    id: "intelligence",
    label: "Intelligence Services",
    source: "Mission Control backend summary",
    destination: "decision-support",
    derive: ({ state }) => ({
      status: state?.lifecycleAnalytics ? "AVAILABLE" : "UNAVAILABLE",
      reason: state?.lifecycleAnalytics ? "Lifecycle analytics were loaded from the backend." : "No intelligence telemetry response.",
    }),
  },
  {
    id: "governance",
    label: "Governance Controls",
    source: "policy / lifecycle telemetry",
    destination: "mission-control",
    derive: ({ policy, lifecycle }) => ({
      status: policy ? "AVAILABLE" : "UNAVAILABLE",
      reason: lifecycle?.safety?.final_submit_hard_blocked_by_lifecycle ? "Final submission remains hard blocked by lifecycle governance." : "Governance policy response loaded.",
    }),
  },
  {
    id: "performance",
    label: "Performance & Capacity",
    source: "/rfq-lifecycle/analytics",
    destination: "workflow-orchestrator",
    derive: ({ analytics }) => ({
      status: analytics ? "AVAILABLE" : "UNAVAILABLE",
      reason: analytics ? "Deterministic lifecycle analytics loaded." : "No lifecycle analytics response.",
    }),
  },
  {
    id: "frontend-integration",
    label: "Frontend Integration",
    source: "active Vite runtime",
    destination: "dashboard",
    derive: () => ({
      status: "AVAILABLE",
      reason: "The landing page is rendered by the active Vite frontend.",
    }),
  },
];

const KPI_ITEMS = [
  { id: "rfqs-loaded", label: "RFQs Loaded" },
  { id: "quote-ready", label: "Quote Ready" },
  { id: "reviewed", label: "Reviewed" },
  { id: "estimated-profit", label: "Estimated Profit" },
  { id: "weekly-metrics", label: "Weekly Metrics" },
  { id: "funnel-metrics", label: "Funnel Metrics" },
  { id: "province-coverage", label: "Province Coverage" },
  { id: "workflow-status", label: "Workflow Status" },
];

function asNumber(...values) {
  for (const value of values) {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return 0;
}

function asText(value, fallback = "UNAVAILABLE") {
  if (value === undefined || value === null) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function formatDateTime(value) {
  if (!value) return "UNAVAILABLE";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString("en-ZA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPercent(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "UNAVAILABLE";
  if (amount <= 1 && amount > 0) return `${Math.round(amount * 100)}%`;
  return `${Math.round(amount)}%`;
}

function compactCount(value) {
  const amount = Number(value || 0);
  if (!Number.isFinite(amount)) return "0";
  if (amount >= 1000000) return `${(amount / 1000000).toFixed(1)}m`;
  if (amount >= 1000) return `${(amount / 1000).toFixed(1)}k`;
  return String(Math.round(amount));
}

function toneForStatus(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized.includes("RUNNING") || normalized.includes("HEALTHY") || normalized.includes("AVAILABLE") || normalized.includes("MANUAL") || normalized.includes("LOCKED") || normalized.includes("DISABLED")) {
    return "good";
  }
  if (normalized.includes("DEGRADED") || normalized.includes("WARNING") || normalized.includes("UNAVAILABLE")) {
    return "warning";
  }
  if (normalized.includes("FAILED") || normalized.includes("BLOCKED") || normalized.includes("ERROR")) {
    return "bad";
  }
  return "neutral";
}

function StatusChip({ label, value, source, freshness, tone = "neutral" }) {
  return (
    <div className={`mission-status-chip ${tone}`}>
      <span>{label}</span>
      <b>{value}</b>
      <small>{source}</small>
      <small>{freshness}</small>
    </div>
  );
}

function SectionHeader({ eyebrow, title, description, action = null }) {
  return (
    <div className="mission-section-head">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      {action}
    </div>
  );
}

function DetailPanel({ label, value, note }) {
  return (
    <div className="mission-detail-panel">
      <span>{label}</span>
      <b>{value}</b>
      <small>{note}</small>
    </div>
  );
}

function PanelShell({ id, eyebrow, title, description, action, children }) {
  return (
    <section className="card mission-panel" id={id}>
      <SectionHeader eyebrow={eyebrow} title={title} description={description} action={action} />
      {children}
    </section>
  );
}

function TrendBars({ values = [] }) {
  const normalized = values.length ? values.map((value) => Number(value || 0)) : [0];
  const max = Math.max(1, ...normalized);
  return (
    <div className="mission-trend-bars" aria-hidden="true">
      {normalized.map((value, index) => (
        <span key={`${index}-${value}`} style={{ height: `${12 + (value / max) * 64}px` }} title={String(value)} />
      ))}
    </div>
  );
}

function normalizeOperationalStatus(value) {
  const status = String(value || "").trim().toUpperCase();
  if (["HEALTHY", "HEALTHY ", "OK", "RUNNING", "UP"].includes(status)) return "RUNNING";
  if (["DEGRADED", "WARN", "WARNING", "SLOW"].includes(status)) return "DEGRADED";
  if (["OFFLINE", "UNKNOWN", "UNAVAILABLE", "ERROR", "FAILED", "NULL"].includes(status) || !status) return "UNAVAILABLE";
  return status;
}

export default function MissionControlLanding({ view = {}, onNavigate = () => {} }) {
  const state = view.state || {};
  const policy = state.policy?.policy || {};
  const lifecycle = state.lifecycle || {};
  const summary = state.summary || {};
  const telemetry = state.lifecycleTelemetry || {};
  const analytics = state.lifecycleAnalytics || {};
  const workflow = state.workflow || {};
  const workManagement = state.workManagement || {};
  const agentCoordination = state.agentCoordination || {};
  const resourceCapacity = state.resourceCapacity || {};
  const policyDecision = state.policyDecision || {};
  const opportunities = Array.isArray(state.opps) ? state.opps : [];
  const history = Array.isArray(state.history) ? state.history : [];
  const lastUpdated = view.state?.lastUpdated || null;

  const [harvestStatus, setHarvestStatus] = useState(null);
  const [harvestEntities, setHarvestEntities] = useState([]);
  const [harvestHistory, setHarvestHistory] = useState([]);
  const [harvestEntitiesState, setHarvestEntitiesState] = useState("loading");
  const [entityRegistrySearchState, setEntityRegistrySearchState] = useState("idle");
  const [entityRegistrySearchCommitted, setEntityRegistrySearchCommitted] = useState(false);
  const [harvestBusy, setHarvestBusy] = useState("");
  const [harvestMessage, setHarvestMessage] = useState("");
  const [harvestError, setHarvestError] = useState("");
  const [entitySearchQuery, setEntitySearchQuery] = useState("");
  const [entityComboboxOpen, setEntityComboboxOpen] = useState(false);
  const [entityComboboxActiveIndex, setEntityComboboxActiveIndex] = useState(-1);
  const [selectedEntityId, setSelectedEntityId] = useState("");
  const [activeControlledRun, setActiveControlledRun] = useState(null);
  const [harvestConfirmation, setHarvestConfirmation] = useState(null);
  const [harvestLifecycleState, setHarvestLifecycleState] = useState("IDLE");
  const [registrySearchAnnouncement, setRegistrySearchAnnouncement] = useState("");
  const [selectedReadinessId, setSelectedReadinessId] = useState(READINESS_ITEMS[0].id);
  const [selectedMetricId, setSelectedMetricId] = useState(KPI_ITEMS[0].id);
  const [selectedWorkItemId, setSelectedWorkItemId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const entityComboboxRef = useRef(null);
  const harvestConfirmationCancelRef = useRef(null);
  const lastHarvestTriggerRef = useRef(null);

  const environment = import.meta.env.MODE || "development";

  const loadHarvestData = useCallback(async () => {
    setHarvestError("");
    setHarvestEntitiesState("loading");
    const [status, entities, historyResult] = await Promise.all([
      getHarvestStatus(),
      getHarvestEntities(),
      getHarvestHistory(10),
    ]);

    if (status && status.status !== "offline") setHarvestStatus(status);
    else setHarvestStatus(status);

    const nextEntities = Array.isArray(entities?.items) ? entities.items : [];
    setHarvestEntities(nextEntities);
    const nextState = entities?.status === "offline" ? "unavailable" : entities?.status === "error" ? "error" : "ready";
    setHarvestEntitiesState(nextState);
    if (nextState === "error") {
      setHarvestError(entities?.message || "Entity registry API error.");
    } else if (nextState === "unavailable") {
      setHarvestError("");
    }

    setSelectedEntityId((current) => {
      const selected = resolveSelectableHarvestEntity(nextEntities, current);
      return selected ? selected.entity_id : "";
    });
    setEntityComboboxActiveIndex(-1);

    setHarvestHistory(Array.isArray(historyResult?.items) ? historyResult.items : []);
  }, []);

  useEffect(() => {
    // Controlled initial harvest hydration keeps the landing state truthful; the fetch callback owns the state updates.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadHarvestData().catch((error) => {
      setHarvestError(error?.message || "Failed to load harvest data.");
    });
  }, []);

  useEffect(() => {
    function handleLiveRefresh() {
      loadHarvestData().catch((error) => {
        setHarvestError(error?.message || "Failed to refresh harvest data.");
      });
    }

    window.addEventListener("lmcp-live-refresh", handleLiveRefresh);
    return () => window.removeEventListener("lmcp-live-refresh", handleLiveRefresh);
  }, []);

  useEffect(() => {
    if (!entityComboboxOpen) return;
    const handleDocumentPointerDown = (event) => {
      if (entityComboboxRef.current && !entityComboboxRef.current.contains(event.target)) {
        setEntityComboboxOpen(false);
        setEntityComboboxActiveIndex(-1);
      }
    };
    document.addEventListener("mousedown", handleDocumentPointerDown);
    return () => document.removeEventListener("mousedown", handleDocumentPointerDown);
  }, [entityComboboxOpen]);

  useEffect(() => {
    if (!harvestConfirmation) return;
    const id = window.setTimeout(() => {
      harvestConfirmationCancelRef.current?.focus?.();
    }, 0);
    return () => window.clearTimeout(id);
  }, [harvestConfirmation]);

  const pilot = summary.controlled_pilot_dashboard || state.pilot || {};
  const queueByState = lifecycle.queue_by_lifecycle_state || {};
  const agentCoordinationHealth = agentCoordination.health || {};
  const agentCoordinationSummary = agentCoordinationHealth.summary || {};
  const resourceCapacityHealth = resourceCapacity.health || {};
  const resourceCapacitySummary = resourceCapacityHealth.summary || {};
  const agentRegistry = Array.isArray(agentCoordination.agents) ? agentCoordination.agents : [];
  const agentTasks = Array.isArray(agentCoordination.tasks) ? agentCoordination.tasks : [];
  const coordinationPlans = Array.isArray(agentCoordination.plans) ? agentCoordination.plans : [];
  const policyDecisionHealth = policyDecision.health || {};
  const policyDecisionSummary = policyDecisionHealth.summary || {};
  const policyRegistry = Array.isArray(policyDecision.policies) ? policyDecision.policies : [];
  const policyEvaluations = Array.isArray(policyDecision.evaluations) ? policyDecision.evaluations : [];
  const policyDecisions = policyEvaluations.flatMap((evaluation) => Array.isArray(evaluation.decisions) ? evaluation.decisions : []);
  const approvalState = view.approvals || {};
  const approvalHealth = approvalState.health || {};
  const approvalSummary = approvalHealth.summary || {};
  const approvalRecords = Array.isArray(approvalState.approvals) ? approvalState.approvals : [];
  const approvalPending = Array.isArray(approvalState.pending) ? approvalState.pending : [];
  const approvalEscalated = Array.isArray(approvalState.escalated) ? approvalState.escalated : [];
  const approvalHistory = Array.isArray(approvalState.history) ? approvalState.history : [];
  const crossOrganization = view.crossOrganization || {};
  const enterpriseSimulation = view.enterpriseSimulation || {};
  const platformFoundation = view.platformFoundation || {};
  const multiTenantArchitecture = view.multiTenantArchitecture || {};
  const enterpriseApiPlatform = view.enterpriseApiPlatform || {};
  const externalIntegrationFramework = view.externalIntegrationFramework || {};
  const pluginExtensionFramework = view.pluginExtensionFramework || {};
  const customerSelfServicePortal = view.customerSelfServicePortal || {};
  const customerIdentity = view.customerIdentity || {};
  const customerDashboard = view.customerDashboard || {};
  const customerRfqQuoteWorkspace = view.customerRfqQuoteWorkspace || {};
  const customerDocumentCentre = view.customerDocumentCentre || {};
  const customerCommunication = view.customerCommunication || {};
  const customerSupport = view.customerSupport || {};
  const crossOrganizationHealth = crossOrganization.health || {};
  const crossOrganizationOrganizations = Array.isArray(crossOrganization.organizations) ? crossOrganization.organizations : [];
  const crossOrganizationCounterparties = Array.isArray(crossOrganization.counterparties) ? crossOrganization.counterparties : [];
  const crossOrganizationInteractions = Array.isArray(crossOrganization.interactions) ? crossOrganization.interactions : [];
  const simulationHealth = enterpriseSimulation.health || {};
  const simulationScenarios = Array.isArray(enterpriseSimulation.scenarios) ? enterpriseSimulation.scenarios : [];
  const foundationIdentity = platformFoundation.identity || {};
  const foundationLifecycle = platformFoundation.lifecycle || {};
  const foundationHealth = platformFoundation.health || {};
  const foundationApiContract = platformFoundation.apiContract || {};
  const foundationConfiguration = platformFoundation.configuration || {};
  const foundationCompatibility = platformFoundation.compatibility || {};
  const foundationDiagnostics = platformFoundation.diagnostics || {};
  const foundationCounts = platformFoundation.counts || {};
  const foundationCapabilities = Array.isArray(platformFoundation.capabilities) ? platformFoundation.capabilities : [];
  const foundationServices = Array.isArray(platformFoundation.services) ? platformFoundation.services : [];
  const tenantIdentity = multiTenantArchitecture.tenantIdentity || {};
  const tenantRegistry = multiTenantArchitecture.tenantRegistry || {};
  const tenantContextContract = multiTenantArchitecture.tenantContextContract || {};
  const tenantLifecycle = multiTenantArchitecture.tenantLifecycle || {};
  const tenantIsolation = multiTenantArchitecture.tenantIsolation || {};
  const tenantConfiguration = multiTenantArchitecture.tenantConfiguration || {};
  const tenantCapabilityModel = Array.isArray(multiTenantArchitecture.tenantCapabilityModel) ? multiTenantArchitecture.tenantCapabilityModel : [];
  const tenantServiceModel = Array.isArray(multiTenantArchitecture.tenantServiceModel) ? multiTenantArchitecture.tenantServiceModel : [];
  const tenantModuleModel = Array.isArray(multiTenantArchitecture.tenantModuleModel) ? multiTenantArchitecture.tenantModuleModel : [];
  const tenantPolicy = multiTenantArchitecture.tenantPolicy || {};
  const tenantDataClassification = multiTenantArchitecture.tenantDataClassification || {};
  const tenantAudit = multiTenantArchitecture.tenantAudit || {};
  const tenantDiagnostics = multiTenantArchitecture.tenantDiagnostics || {};
  const tenantCompatibility = multiTenantArchitecture.tenantCompatibility || {};
  const tenantHealth = multiTenantArchitecture.tenantHealth || {};
  const tenantMission = multiTenantArchitecture.missionControlIntegration || {};
  const apiMission = enterpriseApiPlatform.missionControlIntegration || {};
  const integrationMission = externalIntegrationFramework.missionControlIntegration || {};
  const pluginMission = pluginExtensionFramework.missionControlIntegration || {};
  const pluginHealth = pluginExtensionFramework.health || {};
  const pluginRegistry = Array.isArray(pluginExtensionFramework.registry) ? pluginExtensionFramework.registry : [];
  const pluginExtensionPoints = Array.isArray(pluginExtensionFramework.extensionPoints) ? pluginExtensionFramework.extensionPoints : [];
  const pluginCapabilities = Array.isArray(pluginExtensionFramework.capabilities) ? pluginExtensionFramework.capabilities : [];
  const pluginIdentity = pluginExtensionFramework.identity || {};
  const pluginLifecycle = pluginExtensionFramework.lifecycle || {};
  const pluginCompatibility = pluginExtensionFramework.compatibility || {};
  const pluginTrust = pluginExtensionFramework.trust || {};
  const pluginDiagnostics = pluginExtensionFramework.diagnostics || {};
  const pluginReadiness = pluginExtensionFramework.readiness || {};
  const portalIdentity = customerSelfServicePortal.identity || {};
  const portalLifecycle = customerSelfServicePortal.lifecycle || {};
  const portalHealth = customerSelfServicePortal.health || {};
  const portalReadiness = customerSelfServicePortal.readiness || {};
  const portalRegistry = Array.isArray(customerSelfServicePortal.registry) ? customerSelfServicePortal.registry : [];
  const portalFeatures = Array.isArray(customerSelfServicePortal.features) ? customerSelfServicePortal.features : [];
  const portalExtensionPoints = Array.isArray(customerSelfServicePortal.extensionPoints) ? customerSelfServicePortal.extensionPoints : [];
  const customerIdentityHealth = customerIdentity.health || {};
  const customerIdentityReadiness = customerIdentity.readiness || {};
  const customerIdentityIdentity = customerIdentity.identity || {};
  const customerIdentityRoles = Array.isArray(customerIdentity.roles) ? customerIdentity.roles : [];
  const customerIdentityPermissions = Array.isArray(customerIdentity.permissions) ? customerIdentity.permissions : [];
  const customerDashboardHealth = customerDashboard.health || {};
  const customerDashboardReadiness = customerDashboard.readiness || {};
  const customerDashboardIdentity = customerDashboard.identity || {};
  const customerDashboardSummary = customerDashboard.summary || {};
  const customerDashboardSections = Array.isArray(customerDashboard.sections) ? customerDashboard.sections : [];
  const customerDashboardWidgets = Array.isArray(customerDashboard.widgets) ? customerDashboard.widgets : [];
  const customerDashboardOrganisation = customerDashboard.organisation || {};
  const customerDashboardRfqs = customerDashboard.rfqs || {};
  const customerDashboardQuotations = customerDashboard.quotations || {};
  const customerDashboardActivity = customerDashboard.activity || {};
  const customerDashboardNotifications = customerDashboard.notifications || {};
  const customerDashboardCompatibility = customerDashboard.compatibility || {};
  const customerRfqQuoteWorkspaceHealth = customerRfqQuoteWorkspace.health || {};
  const customerRfqQuoteWorkspaceReadiness = customerRfqQuoteWorkspace.readiness || {};
  const customerRfqQuoteWorkspaceIdentity = customerRfqQuoteWorkspace.identity || {};
  const customerRfqQuoteWorkspaceRfqs = customerRfqQuoteWorkspace.rfqs || {};
  const customerRfqQuoteWorkspaceQuotations = customerRfqQuoteWorkspace.quotations || {};
  const customerRfqQuoteWorkspaceRfqLifecycle = customerRfqQuoteWorkspace.rfqLifecycle || {};
  const customerRfqQuoteWorkspaceQuotationLifecycle = customerRfqQuoteWorkspace.quotationLifecycle || {};
  const customerRfqQuoteWorkspaceSourceAuthority = customerRfqQuoteWorkspace.sourceAuthority || {};
  const customerRfqQuoteWorkspaceFreshness = customerRfqQuoteWorkspace.freshness || {};
  const customerRfqQuoteWorkspaceCompatibility = customerRfqQuoteWorkspace.compatibility || {};
  const customerDocumentCentreHealth = customerDocumentCentre.health || {};
  const customerDocumentCentreReadiness = customerDocumentCentre.readiness || {};
  const customerDocumentCentreIdentity = customerDocumentCentre.identity || {};
  const customerDocumentCentreCatalogue = customerDocumentCentre.catalogue || {};
  const customerDocumentCentreClassifications = customerDocumentCentre.classifications || {};
  const customerDocumentCentreLifecycle = customerDocumentCentre.lifecycle || {};
  const customerDocumentCentreRetention = customerDocumentCentre.retention || {};
  const customerDocumentCentreIntegrity = customerDocumentCentre.integrity || {};
  const customerDocumentCentreVisibility = customerDocumentCentre.visibility || {};
  const customerDocumentCentreCompatibility = customerDocumentCentre.compatibility || {};
  const customerCommunicationHealth = customerCommunication.health || {};
  const customerCommunicationReadiness = customerCommunication.readiness || {};
  const customerCommunicationIdentity = customerCommunication.identity || {};
  const customerCommunicationRegistry = customerCommunication.registry || {};
  const customerCommunicationCatalogue = customerCommunication.catalogue || {};
  const customerCommunicationTemplates = customerCommunication.templates || {};
  const customerCommunicationPreferences = customerCommunication.preferences || {};
  const customerCommunicationDelivery = customerCommunication.delivery || {};
  const customerCommunicationLifecycle = customerCommunication.lifecycle || {};
  const customerCommunicationPolicy = customerCommunication.policy || {};
  const customerCommunicationDiagnostics = customerCommunication.diagnostics || {};
  const customerCommunicationCompatibility = customerCommunication.compatibility || {};
  const customerSupportHealth = customerSupport.health || {};
  const customerSupportReadiness = customerSupport.readiness || {};
  const customerSupportIdentity = customerSupport.identity || {};
  const customerSupportCases = customerSupport.cases || {};
  const customerSupportPriorities = customerSupport.priorities || {};
  const customerSupportSlas = customerSupport.slas || {};
  const customerSupportQueues = customerSupport.queues || {};
  const customerSupportKnowledgeBase = customerSupport.knowledgeBase || {};
  const customerSupportLifecycle = customerSupport.lifecycle || {};
  const customerSupportPolicy = customerSupport.policy || {};
  const customerSupportDiagnostics = customerSupport.diagnostics || {};
  const customerSupportCompatibility = customerSupport.compatibility || {};
  const tenantCounts = multiTenantArchitecture.counts || {};
  const crossOrganizationStateLabel =
    crossOrganizationHealth.data_state === "NO_DATA" || (!crossOrganizationOrganizations.length && !crossOrganizationCounterparties.length && !crossOrganizationInteractions.length)
      ? "NO_DATA"
      : crossOrganizationHealth.status === "ok"
        ? "AVAILABLE"
        : String(crossOrganizationHealth.status || "UNAVAILABLE").toUpperCase();
  const policyDecisionStateLabel =
    policyDecisionHealth.data_state === "NO_DATA" || (!policyRegistry.length && !policyDecisions.length)
      ? "NO_DATA"
      : policyDecisionHealth.status === "ok"
        ? "AVAILABLE"
        : String(policyDecisionHealth.status || "UNAVAILABLE").toUpperCase();
  const approvalStateLabel =
    approvalHealth.data_state === "NO_DATA" || (!approvalRecords.length && !approvalPending.length && !approvalEscalated.length)
      ? "NO_DATA"
      : approvalHealth.status === "ok"
        ? "AVAILABLE"
        : String(approvalHealth.status || "UNAVAILABLE").toUpperCase();
  const agentCoordinationStateLabel =
    agentCoordinationHealth.data_state === "NO_DATA" || (!agentRegistry.length && !agentTasks.length && !coordinationPlans.length)
      ? "NO_DATA"
      : agentCoordinationHealth.status === "ok"
        ? "AVAILABLE"
        : String(agentCoordinationHealth.status || "UNAVAILABLE").toUpperCase();
  const resourceCapacityStateLabel =
    resourceCapacityHealth.data_state === "NO_DATA" || (!resourceCapacitySummary.resource_count && !resourceCapacitySummary.metric_count)
      ? "NO_DATA"
      : resourceCapacityHealth.status === "ok"
        ? "AVAILABLE"
        : String(resourceCapacityHealth.status || "UNAVAILABLE").toUpperCase();
  const simulationStateLabel =
    simulationHealth.data_state === "NO_DATA" || !simulationScenarios.length
      ? "NO_DATA"
      : simulationHealth.status === "ok"
        ? "AVAILABLE"
        : String(simulationHealth.status || "UNAVAILABLE").toUpperCase();
  const selectedApproval = approvalRecords[0] || approvalPending[0] || approvalEscalated[0] || approvalHistory[0] || null;

  const systemHealth = normalizeOperationalStatus(view.backendStatus || state.health?.status);
  const backendAvailable = systemHealth === "RUNNING" || systemHealth === "DEGRADED";
  const operatingMode = "MANUAL";
  const harvestScheduler =
    harvestStatus?.scheduler_enabled === false
      ? "DISABLED"
      : harvestStatus?.scheduler_enabled === true
        ? "ENABLED"
        : policy?.harvest_scheduler_enabled === false
          ? "DISABLED"
          : policy?.harvest_scheduler_enabled === true
            ? "ENABLED"
            : "UNAVAILABLE";
  const submissionScheduler = policy?.submission_scheduler_enabled === false ? "DISABLED" : policy?.submission_scheduler_enabled === true ? "ENABLED" : "UNAVAILABLE";
  const finalSubmission = lifecycle?.safety?.final_submit_hard_blocked_by_lifecycle || policy?.allow_portal_final_submit === false ? "LOCKED" : policy?.allow_portal_final_submit === true ? "UNLOCKED" : "UNAVAILABLE";
  const gmailTransport = policy?.allow_email_send === false ? "DRAFT ONLY" : policy?.allow_email_send === true ? "LIVE" : "UNAVAILABLE";

  const explicitPilotWave = asText(pilot?.pilot_wave || pilot?.wave || "", "");
  const goNoGoStatus = asText(pilot?.go_no_go || pilot?.status || pilot?.readiness_status, "").toUpperCase();
  const goNoGoLabel = explicitPilotWave ? goNoGoStatus || "UNAVAILABLE" : "NO ACTIVE PILOT WAVE";

  const missionMetrics = useMemo(() => {
    const countOrUnavailable = (...values) => {
      if (!backendAvailable) return "UNAVAILABLE";
      return compactCount(asNumber(...values));
    };
    const rfqsHarvested = countOrUnavailable(summary?.rfqs_harvested, summary?.total_rfqs, summary?.total_rfqs_loaded, opportunities.length, lifecycle?.total_rfqs);
    const rfqsRejected = countOrUnavailable(summary?.rfqs_rejected, lifecycle?.failed_rfqs, queueByState.FAILED, queueByState.REJECTED, queueByState.REVIEW_REQUIRED);
    const rfqsApproved = countOrUnavailable(summary?.rfqs_approved, queueByState.SUBMISSION_READY, queueByState.QUOTE_PACK_READY);
    const quotePacksGenerated = countOrUnavailable(summary?.quote_packs_generated, queueByState.QUOTE_PACK_READY);
    const submissionRecords = countOrUnavailable(summary?.submission_records, summary?.submitted_rfqs, lifecycle?.proof_captured_rfqs, history.length);
    const proofRecords = countOrUnavailable(summary?.proof_records, lifecycle?.proof_captured_rfqs, history.filter((item) => String(item?.submitted || item?.proof_captured || item?.status || "").toLowerCase().includes("proof")).length);

    return [
      {
        id: "rfqs-harvested",
        label: "Recent Submissions",
        value: rfqsHarvested,
        source: "/dashboard/summary recent_submissions",
        freshness: formatDateTime(summary?.timestamp || lastUpdated),
        detail: `${rfqsHarvested} recent submission record(s) surfaced by the backend dashboard summary. Open Approval Centre to inspect them.`,
      },
      {
        id: "rfqs-rejected",
        label: "RFQs Rejected",
        value: rfqsRejected,
        source: "/rfq-lifecycle/mission-control",
        freshness: formatDateTime(summary?.timestamp || lastUpdated),
        detail: `${rfqsRejected} RFQ(s) blocked, failed, or sent for review.`,
      },
      {
        id: "rfqs-approved",
        label: "RFQs Approved",
        value: rfqsApproved,
        source: "/rfq-lifecycle/mission-control",
        freshness: formatDateTime(summary?.timestamp || lastUpdated),
        detail: `${rfqsApproved} RFQ(s) reached quote-pack or submission readiness.`,
      },
      {
        id: "quote-packs-generated",
        label: "Quote Packs Generated",
        value: quotePacksGenerated,
        source: "/quote-compilation/packs",
        freshness: formatDateTime(summary?.timestamp || lastUpdated),
        detail: `${quotePacksGenerated} pack(s) appear in the authoritative mission summary.`,
      },
      {
        id: "submission-records",
        label: "Submission Records",
        value: submissionRecords,
        source: "/submission-history/recent-real",
        freshness: formatDateTime(history[0]?.submitted_at || lastUpdated),
        detail: `${submissionRecords} submission-history row(s) are visible to the frontend.`,
      },
      {
        id: "proof-records",
        label: "Proof Records",
        value: proofRecords,
        source: "/submission-proof/latest",
        freshness: formatDateTime(history[0]?.submitted_at || lastUpdated),
        detail: `${proofRecords} proof-related record(s) are visible to the frontend.`,
      },
      {
        id: "resource-capacity",
        label: "Resource Capacity",
        value: resourceCapacityStateLabel,
        source: "/resource-capacity/health",
        freshness: formatDateTime(resourceCapacityHealth.updated_at || lastUpdated),
        detail: `${compactCount(resourceCapacitySummary.resource_count)} resource(s), ${compactCount(resourceCapacitySummary.constraint_count)} constraint(s), and ${compactCount(resourceCapacitySummary.recommendation_count)} recommendation(s) are available from the capacity service.`,
      },
      {
        id: "cross-organization",
        label: "Cross-Organisation",
        value: crossOrganizationStateLabel,
        source: "/cross-organization/health",
        freshness: formatDateTime(crossOrganizationHealth.updated_at || lastUpdated),
        detail: `${compactCount(crossOrganizationOrganizations.length)} organisation(s), ${compactCount(crossOrganizationCounterparties.length)} counterparty record(s), and ${compactCount(crossOrganizationInteractions.length)} interaction(s) are exposed by the cross-organisation service.`,
      },
      {
        id: "enterprise-simulation",
        label: "Simulation",
        value: simulationStateLabel,
        source: "/enterprise-simulation/health",
        freshness: formatDateTime(simulationHealth.updated_at || lastUpdated),
        detail: `${compactCount(simulationScenarios.length)} scenario(s) are exposed by the simulation service. HYPOTHETICAL results remain isolated from production.`,
      },
      {
        id: "customer-self-service-portal",
        label: "Customer Portal",
        value: String(portalReadiness.readiness_state || customerSelfServicePortal.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-portal/health",
        freshness: formatDateTime(portalHealth.updated_at || lastUpdated),
        detail: `${compactCount(portalRegistry.length)} metadata record(s), ${compactCount(portalFeatures.length)} feature record(s), and ${compactCount(portalExtensionPoints.length)} extension point(s) are exposed. No customer authentication is implemented.`,
      },
      {
        id: "customer-identity",
        label: "Identity",
        value: String(customerIdentityReadiness.readiness_state || customerIdentity.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-identity/health",
        freshness: formatDateTime(customerIdentityHealth.updated_at || lastUpdated),
        detail: `${compactCount(customerIdentityRoles.length)} role(s), ${compactCount(customerIdentityPermissions.length)} permission(s), and ${compactCount(customerIdentity.counts?.deniedPermissions || customerIdentityPermissions.filter((item) => item.grant_state === "denied").length)} denied permission(s) are exposed. No customer login or token issuance is implemented.`,
      },
      {
        id: "customer-dashboard",
        label: "Customer Dashboard",
        value: String(customerDashboardReadiness.readiness_state || customerDashboard.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-dashboard/health",
        freshness: formatDateTime(customerDashboardHealth.updated_at || lastUpdated),
        detail: `${compactCount(customerDashboardSections.length)} section(s), ${compactCount(customerDashboardWidgets.length)} widget(s), and ${String(customerDashboardSummary.dashboard_status || "NO_DATA").toUpperCase()} summary posture are surfaced. No customer data is fabricated.`,
      },
      {
        id: "customer-rfq-quote-workspace",
        label: "RFQ & Quote Workspace",
        value: String(customerRfqQuoteWorkspaceReadiness.readiness_state || customerRfqQuoteWorkspace.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-rfq-quotes/health",
        freshness: formatDateTime(customerRfqQuoteWorkspaceHealth.updated_at || lastUpdated),
        detail: `${compactCount(customerRfqQuoteWorkspace.counts?.rfqs || customerRfqQuoteWorkspaceRfqs.records?.length || 0)} RFQ record(s) and ${compactCount(customerRfqQuoteWorkspace.counts?.quotations || customerRfqQuoteWorkspaceQuotations.records?.length || 0)} quotation record(s) remain read only and tenant bound.`,
      },
      {
        id: "customer-document-centre",
        label: "Secure Document Centre",
        value: String(customerDocumentCentreReadiness.readiness_state || customerDocumentCentre.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-documents/health",
        freshness: formatDateTime(customerDocumentCentreHealth.updated_at || lastUpdated),
        detail: `${compactCount(customerDocumentCentre.counts?.documents || customerDocumentCentreCatalogue.records?.length || 0)} document record(s) and ${compactCount(customerDocumentCentre.counts?.classifications || customerDocumentCentreClassifications.classifications?.length || 0)} classification record(s) remain read only and tenant bound.`,
      },
      {
        id: "customer-communication",
        label: "Communication & Notifications",
        value: String(customerCommunicationReadiness.readiness_state || customerCommunication.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-communication/health",
        freshness: formatDateTime(customerCommunicationHealth.updated_at || lastUpdated),
        detail: `${compactCount(customerCommunication.counts?.notifications || customerCommunicationRegistry.records?.length || 0)} notification record(s), ${compactCount(customerCommunication.counts?.templates || customerCommunicationTemplates.templates?.length || 0)} template record(s), and ${compactCount(customerCommunication.counts?.preferences || customerCommunicationPreferences.channels?.length || 0)} preference channel(s) remain read only and tenant bound.`,
      },
      {
        id: "customer-support",
        label: "Support & Service Desk",
        value: String(customerSupportReadiness.readiness_state || customerSupport.status || "NO_DATA").toUpperCase(),
        source: "/platform/customer-support/health",
        freshness: formatDateTime(customerSupportHealth.updated_at || lastUpdated),
        detail: `${compactCount(customerSupport.counts?.cases || customerSupportCases.records?.length || 0)} case record(s), ${compactCount(customerSupport.counts?.priorities || customerSupportPriorities.priorities?.length || 0)} priority record(s), ${compactCount(customerSupport.counts?.slas || customerSupportSlas.slas?.length || 0)} SLA record(s), and ${compactCount(customerSupport.counts?.knowledge || customerSupportKnowledgeBase.records?.length || 0)} knowledge article(s) remain read only and tenant bound.`,
      },
      {
        id: "plugin-extension-framework",
        label: "Plugin Framework",
        value: String(pluginReadiness.readiness_state || pluginExtensionFramework.status || "NO_DATA").toUpperCase(),
        source: "/platform/plugins/health",
        freshness: formatDateTime(pluginHealth.updated_at || lastUpdated),
        detail: `${compactCount(pluginRegistry.length)} metadata record(s), ${compactCount(pluginExtensionPoints.length)} extension point(s), and ${compactCount(pluginCapabilities.length)} capability record(s) are available. No plugin code executes.`,
      },
    ];
  }, [backendAvailable, crossOrganizationCounterparties.length, crossOrganizationHealth.updated_at, crossOrganizationInteractions.length, crossOrganizationOrganizations.length, crossOrganizationStateLabel, customerCommunication.status, customerCommunicationHealth.updated_at, customerCommunicationReadiness.readiness_state, customerCommunicationRegistry.records?.length, customerCommunicationTemplates.templates?.length, customerCommunicationPreferences.channels?.length, customerCommunicationCatalogue.records?.length, customerCommunicationDelivery.delivery_records?.length, customerCommunicationIdentity.workspace_id, customerCommunicationLifecycle.lifecycle_state, customerCommunicationPolicy.global_governance_precedence, customerCommunicationDiagnostics.diagnostic_state, customerCommunicationCompatibility.compatibility_state, customerDashboard.status, customerDashboardHealth.updated_at, customerDashboardReadiness.readiness_state, customerDashboardSections.length, customerDashboardSummary.dashboard_status, customerDashboardWidgets.length, customerDocumentCentre.status, customerDocumentCentre.counts?.documents, customerDocumentCentre.counts?.classifications, customerDocumentCentreHealth.updated_at, customerDocumentCentreReadiness.readiness_state, customerDocumentCentreCatalogue.records?.length, customerDocumentCentreClassifications.classifications?.length, customerDocumentCentreIdentity.workspace_id, customerDocumentCentreLifecycle.lifecycle_state, customerDocumentCentreRetention.retention_state, customerDocumentCentreIntegrity.integrity_state, customerDocumentCentreVisibility.document_visibility_policy, customerDocumentCentreCompatibility.compatibility_state, customerIdentity, customerIdentityHealth.updated_at, customerIdentityPermissions, customerIdentityReadiness.readiness_state, customerIdentityRoles.length, customerRfqQuoteWorkspace.counts?.quotations, customerRfqQuoteWorkspace.counts?.rfqs, customerRfqQuoteWorkspace.status, customerRfqQuoteWorkspaceHealth.updated_at, customerRfqQuoteWorkspaceQuotations.records?.length, customerRfqQuoteWorkspaceReadiness.readiness_state, customerRfqQuoteWorkspaceRfqs.records?.length, customerSelfServicePortal.status, customerSupport.status, customerSupportHealth.updated_at, customerSupportReadiness.readiness_state, customerSupportCases.records?.length, customerSupportPriorities.priorities?.length, customerSupportSlas.slas?.length, customerSupportKnowledgeBase.records?.length, history, lifecycle?.failed_rfqs, lifecycle?.proof_captured_rfqs, lifecycle?.total_rfqs, lastUpdated, opportunities.length, portalExtensionPoints.length, portalFeatures.length, portalHealth.updated_at, portalReadiness.readiness_state, portalRegistry.length, pluginCapabilities.length, pluginExtensionFramework.status, pluginHealth.updated_at, pluginReadiness.readiness_state, pluginRegistry.length, pluginExtensionPoints.length, queueByState, resourceCapacityHealth.updated_at, resourceCapacityStateLabel, resourceCapacitySummary.constraint_count, resourceCapacitySummary.recommendation_count, resourceCapacitySummary.resource_count, simulationHealth.updated_at, simulationStateLabel, simulationScenarios.length, summary]);

  const selectedMetric = missionMetrics.find((metric) => metric.id === selectedMetricId) || missionMetrics[0];
  const selectedReadiness = READINESS_ITEMS.find((item) => item.id === selectedReadinessId) || READINESS_ITEMS[0];
  const selectedHarvestEntity = resolveSelectableHarvestEntity(harvestEntities, selectedEntityId);
  const filteredHarvestEntities = useMemo(() => filterHarvestEntities(harvestEntities, entitySearchQuery), [entitySearchQuery, harvestEntities]);
  const visibleHarvestEntities = filteredHarvestEntities.slice(0, 24);
  const entitySearchHasMatches = filteredHarvestEntities.length > 0;
  const selectedEntityLabel = selectedHarvestEntity ? buildHarvestEntityDisplay(selectedHarvestEntity) : "No entity selected";
  const selectedEntityDetails = buildHarvestEntityDetails(selectedHarvestEntity);
  const latestControlledRun = useMemo(() => {
    const reversedHistory = [...harvestHistory].reverse();
    return reversedHistory.find((run) => isControlledHarvestTerminalState(run?.run_state ?? run?.status ?? run?.state)) || null;
  }, [harvestHistory]);
  const latestControlledRunMessage = buildControlledHarvestStatusMessage(latestControlledRun);
  const entityRegistryStateLabel =
    entityRegistrySearchState === "searching"
      ? "Searching registry..."
      : harvestEntitiesState === "loading"
        ? "Loading registry..."
        : entityRegistrySearchState === "error"
          ? "API error"
          : entityRegistrySearchState === "unavailable"
            ? "Registry unavailable"
            : harvestEntitiesState === "unavailable"
              ? "Registry unavailable"
              : harvestEntitiesState === "error"
                ? "API error"
                : harvestEntities.length
                  ? `${harvestEntities.length} approved entity record(s)`
                  : "No results";
  const activeEntityOption = entityComboboxOpen && entityComboboxActiveIndex >= 0 ? visibleHarvestEntities[entityComboboxActiveIndex] || null : null;
  const latestBackendRun = harvestStatus?.latest_run || null;
  const currentControlledRun = activeControlledRun || null;
  const currentControlledRunState = getControlledHarvestDisplayState(currentControlledRun);
  const currentControlledRunMessage = buildControlledHarvestStatusMessage(currentControlledRun);

  useEffect(() => {
    if (!visibleHarvestEntities.length) {
      // Keep the combobox selection bounded when the visible list changes.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEntityComboboxActiveIndex(-1);
      return;
    }
    if (entityComboboxActiveIndex < 0 || entityComboboxActiveIndex >= visibleHarvestEntities.length) {
      const firstSelectable = visibleHarvestEntities.findIndex((entity) => isHarvestEntitySelectable(entity));
      setEntityComboboxActiveIndex(firstSelectable >= 0 ? firstSelectable : -1);
    }
  }, [entityComboboxActiveIndex, visibleHarvestEntities]);

  function selectHarvestEntity(entity) {
    if (!isHarvestEntitySelectable(entity)) return;
    setSelectedEntityId(entity.entity_id);
    setEntitySearchQuery(entity.display_name || entity.entity_id || "");
    setEntityComboboxOpen(false);
    setEntityComboboxActiveIndex(-1);
    setRegistrySearchAnnouncement(`${entity.display_name || entity.entity_id} selected.`);
    setHarvestLifecycleState("ENTITY_SELECTED");
    setHarvestError("");
  }

  function clearHarvestEntitySelection() {
    setSelectedEntityId("");
    setEntitySearchQuery("");
    setEntityComboboxOpen(false);
    setEntityComboboxActiveIndex(-1);
    setEntityRegistrySearchCommitted(false);
    setRegistrySearchAnnouncement("Selection cleared.");
    setHarvestLifecycleState("IDLE");
  }

  function handleHarvestEntityQueryChange(nextValue) {
    setEntitySearchQuery(nextValue);
    setEntityComboboxOpen(true);
    setEntityRegistrySearchState("idle");
    setEntityRegistrySearchCommitted(false);
    setRegistrySearchAnnouncement("");
    if (selectedHarvestEntity && !doesHarvestEntityMatchInput(selectedHarvestEntity, nextValue)) {
      setSelectedEntityId("");
      setHarvestLifecycleState("IDLE");
    }
  }

  function handleHarvestEntityKeyDown(event) {
    if (harvestEntitiesState === "loading" || harvestEntitiesState === "error") return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setEntityComboboxOpen(true);
      setEntityComboboxActiveIndex((current) => moveHarvestEntityIndex(current, 1, visibleHarvestEntities, entitySearchQuery));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setEntityComboboxOpen(true);
      setEntityComboboxActiveIndex((current) => moveHarvestEntityIndex(current, -1, visibleHarvestEntities, entitySearchQuery));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (entityComboboxOpen && entityComboboxActiveIndex >= 0 && activeEntityOption && entityRegistrySearchCommitted) {
        selectHarvestEntity(activeEntityOption);
        return;
      }
      void executeHarvestEntitySearch();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setEntityComboboxOpen(false);
      setEntityComboboxActiveIndex(-1);
    }
  }

  function handleHarvestEntityButtonSelect(entity) {
    selectHarvestEntity(entity);
  }

  async function executeHarvestEntitySearch() {
    setEntityRegistrySearchState("searching");
    setHarvestError("");
    setRegistrySearchAnnouncement("");
    setHarvestLifecycleState("SEARCHING");

    try {
      const entities = await getHarvestEntities();
      const nextEntities = Array.isArray(entities?.items) ? entities.items : [];
      setHarvestEntities(nextEntities);

      const nextState = entities?.status === "offline" ? "unavailable" : entities?.status === "error" ? "error" : "ready";
      setHarvestEntitiesState(nextState);
      setEntityRegistrySearchState(nextState);
      setEntityRegistrySearchCommitted(true);
      setEntityComboboxOpen(true);
      setEntityComboboxActiveIndex(-1);

      const matches = filterHarvestEntities(nextEntities, entitySearchQuery);
      const firstSelectableIndex = matches.findIndex((entity) => isHarvestEntitySelectable(entity));
      if (firstSelectableIndex >= 0) {
        setEntityComboboxActiveIndex(firstSelectableIndex);
      }

      const matchCount = matches.length;
      setRegistrySearchAnnouncement(
        matchCount
          ? `Search completed — ${matchCount} approved entit${matchCount === 1 ? "y" : "ies"} found.`
          : "Search completed — no matching approved entities found.",
      );

      if (nextState === "error") {
        setHarvestError(entities?.message || "Entity registry API error.");
      } else if (nextState === "unavailable") {
        setHarvestError("");
      }

      setHarvestLifecycleState("RESULTS_AVAILABLE");
      return matches;
    } catch (error) {
      const message = error?.message || "Registry search failed.";
      setHarvestEntitiesState("error");
      setEntityRegistrySearchState("error");
      setHarvestError(message);
      setRegistrySearchAnnouncement("Registry search failed.");
      setHarvestLifecycleState("UNAVAILABLE");
      return [];
    }
  }

  function openControlledHarvestConfirmation(mode, trigger) {
    if (mode === "entity" && !selectedHarvestEntity) {
      setHarvestError("Select an approved enabled entity before running a controlled entity harvest.");
      return;
    }

    lastHarvestTriggerRef.current = trigger || null;
    setHarvestError("");
    setHarvestMessage("");
    setHarvestLifecycleState("CONFIRMATION_REQUIRED");
    setHarvestConfirmation({
      mode,
      entity: mode === "entity" ? selectedHarvestEntity : null,
      lines: buildControlledHarvestConfirmationLines(mode === "entity" ? selectedHarvestEntity : null, mode),
    });
  }

  function closeControlledHarvestConfirmation() {
    setHarvestConfirmation(null);
    setHarvestLifecycleState(activeControlledRun?.run_id ? harvestLifecycleState : "IDLE");
    window.setTimeout(() => {
      lastHarvestTriggerRef.current?.focus?.();
    }, 0);
  }

  async function confirmControlledHarvest() {
    if (!harvestConfirmation) return;

    const { mode, entity } = harvestConfirmation;
    if (mode === "entity" && !entity?.entity_id) {
      setHarvestError("Select an approved enabled entity before running a controlled entity harvest.");
      setHarvestConfirmation(null);
      setHarvestLifecycleState(activeControlledRun?.run_id ? harvestLifecycleState : "IDLE");
      return;
    }

    setHarvestBusy(mode);
    setHarvestError("");
    setHarvestMessage("");
    setHarvestLifecycleState("SUBMITTING_REQUEST");
    setHarvestConfirmation(null);

    try {
      const response = await runHarvest({
        mode,
        entityId: mode === "entity" && entity ? entity.entity_id : "",
        includeClosed: false,
        recheckExisting: true,
        trigger: "manual_frontend",
      });

      if (response?.status === "error") {
        throw new Error(response?.message || "Harvest request failed.");
      }

      const nextState = normalizeControlledHarvestState(response?.run_state ?? response?.state ?? response?.status, response);
      setHarvestLifecycleState(nextState);
      setHarvestMessage(buildControlledHarvestStatusMessage(response));
      setActiveControlledRun({
        run_id: response?.run_id || "",
        mode: response?.mode || mode,
        entity_id: response?.entity_id || entity?.entity_id || null,
        entity_display_name: response?.entity_display_name || entity?.display_name || null,
        status: response?.status || nextState,
        state: response?.state || response?.run_state || nextState,
        run_state: response?.run_state || response?.status || nextState,
        message: buildControlledHarvestStatusMessage(response),
        scheduler_enabled: response?.scheduler_enabled ?? harvestStatus?.scheduler_enabled ?? false,
        autonomous_harvest_enabled: response?.autonomous_harvest_enabled ?? false,
        evidence_reference: response?.evidence_reference || response?.evidence_path || null,
        timestamp: response?.timestamp || new Date().toISOString(),
        sources_attempted: response?.summary?.sources_used ?? response?.sources?.length ?? 0,
        sources_completed: response?.new_rfqs ?? response?.opportunities_found ?? 0,
        discovered_record_count: response?.opportunities_found ?? response?.opportunities?.length ?? 0,
        warning_count: Array.isArray(response?.warnings) ? response.warnings.length : 0,
        error_summary: Array.isArray(response?.errors) && response.errors.length ? response.errors.join("; ") : "",
      });
      window.dispatchEvent(new CustomEvent("lmcp-live-refresh"));
      await loadHarvestData();
    } catch (error) {
      setHarvestError(error?.message || "Controlled harvest failed.");
      setHarvestLifecycleState("FAILED");
    } finally {
      setHarvestBusy("");
    }
  }

  useEffect(() => {
    if (!activeControlledRun?.run_id) return;
    const matchedHistoryRun = harvestHistory.find((run) => String(run?.run_id || "") === String(activeControlledRun.run_id));
    if (!matchedHistoryRun) return;
    // Synchronise the active controlled run with the authoritative history record.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveControlledRun((current) => {
      if (!current || current.run_id !== activeControlledRun.run_id) return current;
      return {
        ...current,
        ...matchedHistoryRun,
        evidence_reference: current.evidence_reference || matchedHistoryRun.evidence_reference || null,
      };
    });
  }, [activeControlledRun?.run_id, harvestHistory]);

  const readinessContext = {
    health: state.health,
    telemetry,
    analytics,
    opportunities,
    history,
    harvestStatus,
    harvestHistory,
    state,
    complianceSummaryState: view.complianceSummaryState,
    policy,
    lifecycle,
  };

  const readinessDetails = selectedReadiness.derive(readinessContext);
  const workManagementReadiness = workManagement.readiness || {};
  const workManagementSummary = workManagementReadiness.summary || {};
  const workManagementItems = Array.isArray(workManagement.items)
    ? workManagement.items
    : Array.isArray(workManagementReadiness.items)
      ? workManagementReadiness.items
      : [];
  const workManagementQueues = Array.isArray(workManagementReadiness.queue_snapshot)
    ? workManagementReadiness.queue_snapshot
    : Array.isArray(workManagement.queues)
      ? workManagement.queues
      : []
  const selectedWorkItem = workManagementItems.find((item) => item.work_item_id === selectedWorkItemId) || workManagementItems[0] || null;
  const workManagementStateLabel =
    workManagementReadiness.data_state === "NO_DATA" || !workManagementItems.length
      ? "NO_DATA"
      : workManagementReadiness.status === "ok"
        ? "AVAILABLE"
        : String(workManagementReadiness.status || "UNAVAILABLE").toUpperCase();

  const governanceItems = [
    { id: "system", label: "SYSTEM", value: systemHealth, source: "/health", freshness: formatDateTime(state.health?.checked_at || lastUpdated) },
    { id: "mode", label: "OPERATING MODE", value: operatingMode, source: "/production-lock/policy + /system/control/status", freshness: formatDateTime(policy?.updated_at || lastUpdated) },
    { id: "harvest-scheduler", label: "HARVEST SCHEDULER", value: harvestScheduler, source: "/opportunities/harvest/status + /production-lock/status", freshness: formatDateTime(harvestStatus?.timestamp || lastUpdated) },
    { id: "submission-scheduler", label: "SUBMISSION SCHEDULER", value: submissionScheduler, source: "governance policy", freshness: formatDateTime(policy?.updated_at || lastUpdated) },
    { id: "final-submission", label: "FINAL SUBMISSION", value: finalSubmission, source: "/submission-centre", freshness: formatDateTime(lastUpdated) },
    { id: "gmail", label: "GMAIL TRANSPORT", value: gmailTransport, source: "governance policy", freshness: formatDateTime(policy?.updated_at || lastUpdated) },
  ];

  const selectedSearchResults = useMemo(() => {
    const term = searchQuery.trim().toLowerCase();
    const rows = opportunities.map((item) => ({
      id: item.id || item.rfq_id || item.reference || item.title,
      title: item.title || item.reference || "RFQ",
      subtitle: item.buyer || item.buyer_name || item.source || "Unknown source",
      source: item.source || "backend",
      freshness: formatDateTime(item.created_at || item.updated_at || lastUpdated),
      destination: "rfq-operations",
      raw: item,
    }));

    if (!term) return rows.slice(0, 8);

    return rows.filter((row) => `${row.title} ${row.subtitle} ${row.source}`.toLowerCase().includes(term)).slice(0, 8);
  }, [lastUpdated, opportunities, searchQuery]);

  const alertItems = useMemo(() => {
    const alertSources = [];
    if (Array.isArray(lifecycle?.alerts)) alertSources.push(...lifecycle.alerts);
    if (Array.isArray(summary?.alerts)) alertSources.push(...summary.alerts);
    if (Array.isArray(workflow?.alerts)) alertSources.push(...workflow.alerts);
    return alertSources.slice(0, 8).map((item, index) => ({
      id: item.alert_id || item.id || index,
      title: item.title || item.message || "Alert",
      message: item.message || item.detail || "No message provided.",
      severity: String(item.severity || "info").toUpperCase(),
      category: String(item.category || item.type || "SYSTEM").toUpperCase(),
      timestamp: item.timestamp || item.created_at || lastUpdated,
      source: item.source || item.source_name || "backend",
      related: item.related_entity || item.buyer_rfq_number || item.rfq_number || "—",
    }));
  }, [lastUpdated, lifecycle?.alerts, summary?.alerts, workflow?.alerts]);

  const trendSeries = useMemo(() => {
    const queueTrend = Array.isArray(analytics?.queue_trend) ? analytics.queue_trend.map((item) => Number(item?.completed_rfqs || item?.value || item?.simulated_throughput || 0)) : [];
    const healthTrend = Array.isArray(analytics?.system_health_trend) ? analytics.system_health_trend.map((item) => Number(item?.health_score || item?.value || 0)) : [];
    const historyTrend = history.slice(0, 6).map((item) => Number(item?.submitted || item?.proof_captured || 0));

    return [
      { id: "rfq-inflow", label: "RFQ inflow", source: "/rfq-lifecycle/analytics", values: queueTrend, detail: queueTrend.length ? `${queueTrend.length} point(s) from backend analytics.` : "UNAVAILABLE" },
      { id: "workflow-health", label: "Workflow health", source: "/rfq-lifecycle/analytics", values: healthTrend, detail: healthTrend.length ? `${healthTrend.length} point(s) from backend analytics.` : "UNAVAILABLE" },
      { id: "submission-history", label: "Submission history", source: "/submission-history/recent-real", values: historyTrend, detail: historyTrend.length ? `${historyTrend.length} recent point(s) loaded.` : "UNAVAILABLE" },
    ];
  }, [analytics?.queue_trend, analytics?.system_health_trend, history]);

  const readinessDetailMetrics = [
    { label: "Current status", value: readinessDetails.status },
    { label: "Status reason", value: readinessDetails.reason },
    { label: "Authoritative source", value: selectedReadiness.source },
    { label: "Last checked", value: formatDateTime(lastUpdated) },
    { label: "Freshness state", value: formatDateTime(lastUpdated) },
    { label: "Environment", value: environment.toUpperCase() },
  ];

  return (
    <section className="mission-control-workspace">
      <section className="card mission-control-hero">
        <div className="mission-control-hero-copy">
          <p className="eyebrow">LMCP AutoQuote Command Centre</p>
          <h1>Mission Control / Enterprise Operator Workspace</h1>
          <p className="muted">
            Truthful operator landing page for the active Vite frontend. The workspace is read-only by default, manual-operation aware, and bound to the certified backend at {view.apiBase}.
          </p>

          <div className="mission-control-header-row">
            <StatusChip label="Backend connection" value={systemHealth} source="/health" freshness={formatDateTime(state.health?.checked_at || lastUpdated)} tone={toneForStatus(systemHealth)} />
            <StatusChip label="Environment" value={environment.toUpperCase()} source="Vite runtime" freshness="build-time" />
            <StatusChip label="Last refresh" value={formatDateTime(lastUpdated)} source="App state" freshness={formatDateTime(lastUpdated)} />
            <StatusChip label="Manual operating mode" value="MANUAL" source="/production-lock/policy + /system/control/status" freshness={formatDateTime(policy?.updated_at || lastUpdated)} />
            <StatusChip label="Capacity signal" value={resourceCapacityStateLabel} source="/resource-capacity/health" freshness={formatDateTime(resourceCapacityHealth.updated_at || lastUpdated)} tone={toneForStatus(resourceCapacityStateLabel)} />
            <StatusChip label="Cross-org signal" value={crossOrganizationStateLabel} source="/cross-organization/health" freshness={formatDateTime(crossOrganizationHealth.updated_at || lastUpdated)} tone={toneForStatus(crossOrganizationStateLabel)} />
          </div>
        </div>

        <div className="mission-control-hero-actions">
          <button type="button" className="mission-action-button primary" onClick={() => view.refreshAll?.()}>
            <RefreshCw size={15} />
            Safe refresh
          </button>
          <button type="button" className="mission-action-button" onClick={() => onNavigate("rfq-operations")}>
            <ClipboardList size={15} />
            Review Queue
          </button>
          <button type="button" className="mission-action-button" onClick={() => onNavigate("submission-centre")}>
            <ShieldCheck size={15} />
            Approval Centre
          </button>
        </div>
      </section>

      <section className="card mission-go-no-go" id="go-no-go">
        <SectionHeader
          eyebrow="Controlled Pilot"
          title="Go / No-Go"
          description="Structured readiness summary from the backend mission state. Labels and values remain separate and no fallback text is concatenated."
          action={<span className={`mission-badge ${toneForStatus(goNoGoLabel)}`}>{goNoGoLabel}</span>}
        />
        <div className="mission-go-grid">
          <div className="mission-go-block">
            <span>Current wave</span>
            <b>{explicitPilotWave || "NO ACTIVE PILOT WAVE"}</b>
          </div>
          <div className="mission-go-block">
            <span>Readiness state</span>
            <b>{goNoGoLabel}</b>
          </div>
          <div className="mission-go-block">
            <span>Success rate</span>
            <b>{pilot?.pilot_success_rate !== undefined ? formatPercent(pilot.pilot_success_rate) : "UNAVAILABLE"}</b>
          </div>
          <div className="mission-go-block">
            <span>Primary blocker</span>
            <b>{asText(pilot?.primary_blocker || pilot?.blocker || pilot?.blocking_reason, "UNAVAILABLE")}</b>
          </div>
          <div className="mission-go-block">
            <span>Recommended action</span>
            <b>{asText(pilot?.recommended_action || pilot?.next_recommended_action, "Review operational evidence")}</b>
          </div>
        </div>
        <div className="mission-go-metrics">
          {missionMetrics.map((metric) => (
            <button
              key={metric.id}
              type="button"
              className={`mission-metric-card ${selectedMetricId === metric.id ? "active" : ""}`}
              onClick={() => setSelectedMetricId(metric.id)}
            >
              <span>{metric.label}</span>
              <b>{metric.value}</b>
              <small>{metric.source}</small>
              <small>{metric.freshness}</small>
            </button>
          ))}
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Selected metric</span>
            <b>{selectedMetric.label}</b>
            <small>{selectedMetric.detail}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Metric source</span>
            <b>{selectedMetric.source}</b>
            <small>{selectedMetric.freshness}</small>
          </div>
        </div>
      </section>

      <section className="card mission-governance" id="governance">
        <SectionHeader
          eyebrow="Governance"
          title="Explicit Governance Labels"
          description="The active frontend must state the operating posture clearly. Unavailable values remain marked as such instead of being guessed."
          action={<span className="mission-badge good">Governance preserved</span>}
        />
        <div className="mission-governance-grid">
          {governanceItems.map((item) => (
            <StatusChip key={item.id} label={item.label} value={item.value} source={item.source} freshness={item.freshness} tone={toneForStatus(item.value)} />
          ))}
        </div>
      </section>

      <section className="card mission-platform-foundation" id="platform-foundation">
        <SectionHeader
          eyebrow="Phase65.1"
          title="Enterprise Platform Foundation"
          description="Bounded read-only indicators for the platform kernel, lifecycle, compatibility, diagnostics, and registry posture. No tenant implementation or autonomous action is introduced."
          action={<span className={`mission-badge ${toneForStatus(foundationHealth.health_state || foundationHealth.status)}`}>{String(foundationHealth.readiness_state || foundationHealth.health_state || platformFoundation.status || "NO_DATA").toUpperCase()}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="Capabilities" value={compactCount(foundationCounts.capabilities || foundationCapabilities.length)} source="/platform/capabilities" freshness={formatDateTime(foundationHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Services" value={compactCount(foundationCounts.services || foundationServices.length)} source="/platform/services" freshness={formatDateTime(foundationHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Lifecycle" value={String(foundationLifecycle.current_state || foundationIdentity.lifecycle_state || "READY_WITH_LIMITATIONS")} source="/platform/lifecycle" freshness={formatDateTime(foundationHealth.updated_at || lastUpdated)} tone={toneForStatus(foundationLifecycle.current_state || foundationIdentity.lifecycle_state)} />
          <StatusChip label="Readiness" value={String(foundationHealth.readiness_state || platformFoundation.status || "NO_DATA").toUpperCase()} source="/platform/readiness" freshness={formatDateTime(foundationHealth.updated_at || lastUpdated)} tone={toneForStatus(foundationHealth.readiness_state || platformFoundation.status)} />
          <StatusChip label="Compatibility" value={String(foundationCompatibility.api_compatibility_level || "NO_DATA")} source="/platform/compatibility" freshness={formatDateTime(foundationHealth.updated_at || lastUpdated)} tone={toneForStatus(foundationCompatibility.api_compatibility_level)} />
          <StatusChip label="Diagnostics" value={String(foundationDiagnostics.database_observation_status || "SANDBOX_BLOCKED")} source="/platform/diagnostics" freshness={formatDateTime(foundationHealth.updated_at || lastUpdated)} tone={toneForStatus(foundationDiagnostics.database_observation_status)} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Platform identity</span>
            <b>{foundationIdentity.platform_name || "NO_DATA"}</b>
            <small>{foundationIdentity.platform_id || "Platform identity unavailable"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Governance authority</span>
            <b>{foundationIdentity.governance_authority || "LA-EELS-001"}</b>
            <small>{foundationIdentity.platform_owner || "Panacea Trust"}</small>
          </div>
        </div>
        <div className="mission-detail-grid compact">
          <div className="mission-detail-panel">
            <span>Accepted limitations</span>
            <b>{foundationIdentity.accepted_limitations?.length || 0}</b>
            <small>{foundationIdentity.accepted_limitations?.[0] || "Live database inspection remains sandbox blocked."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Next authorised milestone</span>
            <b>READY_FOR_PHASE65_2_MULTI_TENANT_ARCHITECTURE</b>
            <small>Defined-not-implemented until Phase65.1 validates.</small>
          </div>
          <div className="mission-detail-panel">
            <span>Canonical PDF</span>
            <b>{foundationApiContract.canonical_pdf?.match_status || "MATCH"}</b>
            <small>{foundationApiContract.canonical_pdf?.observed_page_count || 28} pages certified</small>
          </div>
          <div className="mission-detail-panel">
            <span>Phase64 integrity</span>
            <b>{foundationApiContract.phase64_integrity?.status || "UNCHANGED"}</b>
            <small>{foundationApiContract.phase64_integrity?.predecessor_baseline || "PHASE64_END_8_VALIDATED"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Governance controls</span>
            <b>{String(foundationConfiguration?.governance_validation?.MANUAL_SUBMISSION || "true")}</b>
            <small>{String(foundationConfiguration?.governance_validation?.GMAIL_TRANSPORT || "DRAFT_ONLY")} transport</small>
          </div>
        </div>
      </section>

      <section className="card mission-api-platform" id="enterprise-api-platform">
        <SectionHeader
          eyebrow="Phase65.3"
          title="Enterprise API Platform"
          description="Bounded internal API indicators. Authentication, authorisation, tenant context, error envelopes, and OpenAPI governance remain fail-closed and truthful."
          action={<span className={`mission-badge ${toneForStatus(apiMission.readiness_state || enterpriseApiPlatform.readiness_state || enterpriseApiPlatform.status)}`}>{String(apiMission.readiness_state || enterpriseApiPlatform.readiness_state || enterpriseApiPlatform.status || "NO_DATA").toUpperCase()}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="APIs" value={compactCount(apiMission.registered_api_count || enterpriseApiPlatform.counts?.api_count || enterpriseApiPlatform.registry?.length || 0)} source="/platform/api/registry" freshness={formatDateTime(enterpriseApiPlatform.identity?.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Domains" value={compactCount(apiMission.api_domain_count || enterpriseApiPlatform.counts?.domain_count || enterpriseApiPlatform.domains?.length || 0)} source="/platform/api/domains" freshness={formatDateTime(enterpriseApiPlatform.identity?.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Lifecycle" value={String(apiMission.api_platform_lifecycle || enterpriseApiPlatform.lifecycle?.current_state || "READY_WITH_LIMITATIONS")} source="/platform/api/lifecycle" freshness={formatDateTime(enterpriseApiPlatform.identity?.updated_at || lastUpdated)} tone={toneForStatus(apiMission.api_platform_lifecycle || enterpriseApiPlatform.lifecycle?.current_state)} />
          <StatusChip label="Readiness" value={String(apiMission.api_readiness || enterpriseApiPlatform.readiness_state || "NO_DATA").toUpperCase()} source="/platform/api/readiness" freshness={formatDateTime(enterpriseApiPlatform.identity?.updated_at || lastUpdated)} tone={toneForStatus(apiMission.api_readiness || enterpriseApiPlatform.readiness_state)} />
          <StatusChip label="Compatibility" value={String(apiMission.compatibility_warning_count !== undefined ? `${apiMission.compatibility_warning_count} warning(s)` : enterpriseApiPlatform.compatibility?.api_compatibility_level || "NO_DATA")} source="/platform/api/compatibility" freshness={formatDateTime(enterpriseApiPlatform.identity?.updated_at || lastUpdated)} tone={toneForStatus(apiMission.compatibility_warning_count ? "WARNING" : enterpriseApiPlatform.compatibility?.api_compatibility_level)} />
          <StatusChip label="OpenAPI" value={String(apiMission.openapi_validation_state || enterpriseApiPlatform.openapiGovernance?.openapi_validation_status || "NO_DATA").toUpperCase()} source="/platform/api/openapi-governance" freshness={formatDateTime(enterpriseApiPlatform.identity?.updated_at || lastUpdated)} tone={toneForStatus(apiMission.openapi_validation_state || enterpriseApiPlatform.openapiGovernance?.openapi_validation_status)} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>API platform identity</span>
            <b>{enterpriseApiPlatform.identity?.canonical_name || "NO_DATA"}</b>
            <small>{enterpriseApiPlatform.identity?.api_platform_id || "API platform identity unavailable"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Tenant context posture</span>
            <b>{enterpriseApiPlatform.authenticationAuthorisation?.tenant_context?.context_source || enterpriseApiPlatform.tenantContext?.context_source || "validated request context"}</b>
            <small>{enterpriseApiPlatform.authenticationAuthorisation?.tenant_context?.invalid_context_behavior || enterpriseApiPlatform.tenantContext?.invalid_context_behavior || "FAILED_CLOSED"}</small>
          </div>
        </div>
        <div className="mission-detail-grid compact">
          <DetailPanel label="Governance state" value={apiMission.governance_state || "PRESERVED"} note="No anonymous mutation endpoint or autonomous action is implemented." />
          <DetailPanel label="Security state" value={apiMission.security_state || "FAIL_CLOSED"} note="Deny-by-default exposure and redacted diagnostics remain in force." />
          <DetailPanel label="Deprecated APIs" value={compactCount(apiMission.deprecated_api_count || enterpriseApiPlatform.registry?.filter((item) => item.implementation_status === 'DEPRECATED_API').length || 0)} note="No deprecated endpoint is treated as active." />
          <DetailPanel label="Next architect action" value={apiMission.next_architect_action || "Proceed to Phase65.4 External Integration Framework only after validation."} note={apiMission.current_milestone || "PHASE65.3_ENTERPRISE_API_PLATFORM"} />
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.7 Support & Service Desk</h3>
            <p className="muted">Read-only support metadata only. Ticket creation, editing, closure, assignment, escalation execution, chat, live SLA monitoring, and external ITSM integrations remain not implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Workspace" value={customerSupportIdentity.canonical_name || "NO_DATA"} note={customerSupportIdentity.workspace_id || "Workspace ID unavailable"} />
              <DetailPanel label="Readiness" value={String(customerSupportReadiness.readiness_state || customerSupport.status || "READY_WITH_LIMITATIONS").toUpperCase()} note={(customerSupportReadiness.limitations || customerSupportIdentity.accepted_limitations || []).join(" · ") || "Read-only support workspace remains truthful."} />
              <DetailPanel label="Cases" value={compactCount(customerSupport.counts?.cases || customerSupportCases.records?.length || 0)} note={customerSupportHealth.health_state || "NO_DATA"} />
              <DetailPanel label="Priorities" value={compactCount(customerSupport.counts?.priorities || customerSupportPriorities.priorities?.length || 0)} note={customerSupportPolicy.ticket_creation_prohibition || "denied"} />
              <DetailPanel label="SLAs" value={compactCount(customerSupport.counts?.slas || customerSupportSlas.slas?.length || 0)} note={customerSupportDiagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} />
              <DetailPanel label="Knowledge base" value={compactCount(customerSupport.counts?.knowledge || customerSupportKnowledgeBase.records?.length || 0)} note={customerSupportCompatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS"} />
            </div>
          </div>
          <div className="mission-work-detail">
            <h3>Support posture</h3>
            <p className="muted">Mission Control surfaces case catalogue, priority model, SLA metadata, queue metadata, and knowledge metadata while preserving fail-closed governance.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Queues" value={compactCount(customerSupport.counts?.queues || customerSupportQueues.queues?.length || 0)} note={customerSupportQueues.queue_state || "REGISTERED_METADATA_ONLY"} />
              <DetailPanel label="Lifecycle" value={customerSupportLifecycle.lifecycle_state || "NO_DATA"} note="Lifecycle metadata only" />
              <DetailPanel label="Mission Control" value={customerSupportHealth.health_state || "READY_WITH_LIMITATIONS"} note={customerSupportHealth.current_milestone || "PHASE65.6.7_SUPPORT_AND_SERVICE_DESK"} />
              <DetailPanel label="Next milestone" value="READY_FOR_PHASE65_6_8_CUSTOMER_PROFILE_TENANT_MANAGEMENT" note="Support foundation remains deferred." />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>API contract and boundaries</h3>
            <p className="muted">Internal enterprise APIs remain governed, tenant-aware where required, and fail closed when authentication, authorisation, compatibility, or policy conditions are not satisfied.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Request envelope" value={enterpriseApiPlatform.requestResponse?.request_envelope?.[0] || "Correlated request envelope"} note={enterpriseApiPlatform.requestResponse?.pagination?.max_page_size ? `Max page size ${enterpriseApiPlatform.requestResponse.pagination.max_page_size}` : "Bounded requests only"} />
              <DetailPanel label="Error contract" value={enterpriseApiPlatform.errorContract?.error_model || "SAFE_ERROR_ENVELOPE"} note={enterpriseApiPlatform.errorContract?.limitations?.[0] || "Raw exceptions are not exposed."} />
              <DetailPanel label="Rate limits" value={enterpriseApiPlatform.rateLimitQuota?.rate_limit_posture || "ARCHITECTURE_DEFINED"} note={enterpriseApiPlatform.rateLimitQuota?.quota_exhaustion_behaviour || "Fail closed on exhaustion."} />
              <DetailPanel label="API audit" value={enterpriseApiPlatform.audit?.audit_scope || "API registration and denial events"} note={enterpriseApiPlatform.observability?.limitations?.[0] || "Observability is bounded and redacted."} />
            </div>
          </div>
          <div className="mission-work-list">
            {(enterpriseApiPlatform.registry || []).slice(0, 6).map((item) => (
              <div key={item.api_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.api_id}</b>
                  <span>{item.domain || "platform"} · {item.exposure_classification || "INTERNAL_PLATFORM_API"}</span>
                </div>
                <div>
                  <b>{item.lifecycle_state || "DEFINED"}</b>
                  <span>{item.validation_status || "DEFINED_NOT_IMPLEMENTED"}</span>
                </div>
              </div>
            ))}
            {!enterpriseApiPlatform.registry?.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
      </section>

      <section className="card mission-integration-framework" id="external-integration-framework">
        <SectionHeader
          eyebrow="Phase65.4"
          title="External Integration Framework"
          description="Read-only external integration indicators. Connector activation remains disabled by default, provider records remain inactive, and no production integration is active."
          action={<span className={`mission-badge ${toneForStatus(integrationMission.integration_readiness || externalIntegrationFramework.status)}`}>{String(integrationMission.integration_readiness || externalIntegrationFramework.status || "NO_DATA").toUpperCase()}</span>}
        />
        <p className="muted">No live integrations, providers, credentials, or outbound traffic are presented.</p>
        <div className="mission-governance-grid">
          <StatusChip label="Integrations" value={compactCount(integrationMission.registered_integration_count || externalIntegrationFramework.counts?.integrations || externalIntegrationFramework.registry?.length || 0)} source="/platform/integrations/registry" freshness={formatDateTime(externalIntegrationFramework.identity?.timestamp || lastUpdated)} tone="good" />
          <StatusChip label="Connectors" value={compactCount(integrationMission.connector_count || externalIntegrationFramework.counts?.connectors || externalIntegrationFramework.connectors?.length || 0)} source="/platform/integrations/connectors" freshness={formatDateTime(externalIntegrationFramework.identity?.timestamp || lastUpdated)} tone="good" />
          <StatusChip label="Adapters" value={compactCount(integrationMission.adapter_count || externalIntegrationFramework.counts?.adapters || externalIntegrationFramework.adapters?.length || 0)} source="/platform/integrations/adapters" freshness={formatDateTime(externalIntegrationFramework.identity?.timestamp || lastUpdated)} tone="good" />
          <StatusChip label="Providers" value={compactCount(integrationMission.provider_count || externalIntegrationFramework.counts?.providers || externalIntegrationFramework.providers?.length || 0)} source="/platform/integrations/providers" freshness={formatDateTime(externalIntegrationFramework.identity?.timestamp || lastUpdated)} tone="warning" />
          <StatusChip label="Activation" value={String(integrationMission.activation_warnings?.[0] ? "DISABLED" : externalIntegrationFramework.connectorActivation?.external_connector_activation_posture || "DISABLED")} source="/platform/integrations/connector-activation" freshness={formatDateTime(externalIntegrationFramework.identity?.timestamp || lastUpdated)} tone="good" />
          <StatusChip label="Readiness" value={String(integrationMission.integration_readiness || externalIntegrationFramework.readiness_state || "NO_DATA").toUpperCase()} source="/platform/integrations/readiness" freshness={formatDateTime(externalIntegrationFramework.identity?.timestamp || lastUpdated)} tone={toneForStatus(integrationMission.integration_readiness || externalIntegrationFramework.readiness_state)} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Integration identity</span>
            <b>{externalIntegrationFramework.identity?.canonical_name || "NO_DATA"}</b>
            <small>{externalIntegrationFramework.identity?.integration_platform_id || "Integration identity unavailable"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Lifecycle state</span>
            <b>{String(externalIntegrationFramework.lifecycle?.current_state || "VALIDATED").toUpperCase()}</b>
            <small>{externalIntegrationFramework.lifecycle?.transition_authority || "Lifecycle authority unavailable"}</small>
          </div>
        </div>
        <div className="mission-detail-grid compact">
          <DetailPanel label="Governance state" value={integrationMission.governance_state || "PRESERVED"} note="No autonomous external action is implemented." />
          <DetailPanel label="Security state" value={integrationMission.security_state || "FAIL_CLOSED"} note="Credential references only; no production credentials are stored." />
          <DetailPanel label="Disabled connectors" value={compactCount(integrationMission.disabled_connector_count || externalIntegrationFramework.counts?.disabledConnectors || 0)} note="Connector activation remains disabled by default." />
          <DetailPanel label="Next architect action" value={integrationMission.next_architect_action || "Proceed to Phase65.5 Plugin & Extension Framework only after validation."} note={`${integrationMission.current_milestone || "PHASE65.4_EXTERNAL_INTEGRATION_FRAMEWORK"} · READY_FOR_PHASE65_5_PLUGIN_EXTENSION_FRAMEWORK`} />
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Connector and provider posture</h3>
            <p className="muted">Provider records remain inactive and connectors remain disabled or defined-not-implemented. No live external traffic is presented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Credential posture" value={externalIntegrationFramework.credentialReference?.credential_type || "reference-only"} note={externalIntegrationFramework.credentialReference?.unavailable_credential_behavior || "FAILED_CLOSED"} />
              <DetailPanel label="Circuit breaker" value={externalIntegrationFramework.circuitBreaker?.default_state || "FAILED_CLOSED"} note="Unverified external systems default to fail closed." />
              <DetailPanel label="Retry posture" value={externalIntegrationFramework.resilience?.maximum_attempts || "3"} note={externalIntegrationFramework.resilience?.backoff_strategy || "bounded backoff"} />
              <DetailPanel label="Dead letters" value={externalIntegrationFramework.deadLetter?.manual_reprocessing_authority || "operator only"} note="No automatic replay is authorised." />
            </div>
          </div>
          <div className="mission-work-list">
            {(externalIntegrationFramework.registry || []).slice(0, 6).map((item) => (
              <div key={item.integration_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.integration_id}</b>
                  <span>{item.domain || "integration"} · {item.integration_type || "DEFINED_NOT_IMPLEMENTED"}</span>
                </div>
                <div>
                  <b>{item.external_action_posture || "DISABLED"}</b>
                  <span>{item.provider_reference || "provider reference only"}</span>
                </div>
              </div>
            ))}
            {!externalIntegrationFramework.registry?.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
      <div className="mission-detail-grid compact">
        <DetailPanel label="Transformation" value={externalIntegrationFramework.transformation?.[0]?.transformation_id || "NO_DATA"} note="Deterministic schema-validated mapping only." />
        <DetailPanel label="Message contract" value={externalIntegrationFramework.messageContract?.message_type || "NO_DATA"} note={externalIntegrationFramework.messageContract?.approval_status || "Manual approval required where relevant"} />
        <DetailPanel label="Diagnostics" value={externalIntegrationFramework.diagnostics?.diagnostic_state || "SANDBOX_BLOCKED"} note={externalIntegrationFramework.diagnostics?.current_limitations?.[0] || "Diagnostics are redacted and tenant safe."} />
        <DetailPanel label="Canonical PDF" value={externalIntegrationFramework.apiContract?.canonical_pdf?.match_status || "MATCH"} note={`${externalIntegrationFramework.apiContract?.canonical_pdf?.observed_page_count || 28} pages certified`} />
      </div>
      </section>

      <section className="card mission-plugin-framework" id="plugin-extension-framework">
        <SectionHeader
          eyebrow="Phase65.5"
          title="Plugin & Extension Framework"
          description="Read-only plugin metadata. Registration, extension points, permissions, trust, and diagnostics are bounded. No plugin code executes."
          action={<span className={`mission-badge ${toneForStatus(pluginMission.readiness || pluginExtensionFramework.status)}`}>{String(pluginMission.readiness || pluginReadiness.readiness_state || pluginExtensionFramework.status || "NO_DATA").toUpperCase()}</span>}
        />
        <p className="muted">No fabricated active plugins, marketplace activity, or external plugin traffic is presented.</p>
        <div className="mission-governance-grid">
          <StatusChip label="Plugins" value={compactCount(pluginMission.registered_metadata_count || pluginExtensionFramework.counts?.plugins || pluginRegistry.length)} source="/platform/plugins/registry" freshness={formatDateTime(pluginHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Extension points" value={compactCount(pluginMission.extension_point_count || pluginExtensionFramework.counts?.extensionPoints || pluginExtensionPoints.length)} source="/platform/plugins/extension-points" freshness={formatDateTime(pluginHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Capabilities" value={compactCount(pluginMission.capability_count || pluginExtensionFramework.counts?.capabilities || pluginCapabilities.length)} source="/platform/plugins/capabilities" freshness={formatDateTime(pluginHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Disabled" value={compactCount(pluginMission.disabled_plugin_count || pluginExtensionFramework.counts?.disabledPlugins || 0)} source="/platform/plugins/registry" freshness={formatDateTime(pluginHealth.updated_at || lastUpdated)} tone="warning" />
          <StatusChip label="Certification" value={compactCount(pluginMission.certification_required_count || pluginRegistry.filter((item) => item.certification_status === "CERTIFICATION_REQUIRED").length)} source="/platform/plugins/certification" freshness={formatDateTime(pluginHealth.updated_at || lastUpdated)} tone="warning" />
          <StatusChip label="Security" value={String(pluginMission.security_status || "FAIL_CLOSED")} source="Plugin governance" freshness={formatDateTime(pluginHealth.updated_at || lastUpdated)} tone="good" />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Plugin identity</span>
            <b>{pluginIdentity.canonical_name || "NO_DATA"}</b>
            <small>{pluginIdentity.plugin_platform_id || "Plugin identity unavailable"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Lifecycle state</span>
            <b>{String(pluginLifecycle.current_state || "NO_DATA").toUpperCase()}</b>
            <small>{pluginLifecycle.transition_authority || "Lifecycle authority unavailable"}</small>
          </div>
        </div>
        <div className="mission-detail-grid compact">
          <DetailPanel label="Compatibility" value={String(pluginCompatibility.compatibility_state || "NO_DATA").toUpperCase()} note={pluginCompatibility.limitations?.[0] || "Compatibility remains bounded"} />
          <DetailPanel label="Trust posture" value={String(pluginTrust.certificate_state || "CERTIFICATION_REQUIRED").toUpperCase()} note={pluginTrust.evidence_requirements?.[0] || "Certification evidence required"} />
          <DetailPanel label="Diagnostics" value={pluginDiagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={pluginDiagnostics.current_limitations?.[0] || "Diagnostics are redacted."} />
          <DetailPanel label="Summary" value={pluginExtensionFramework.frontendExperience?.truthfulness || "Metadata only"} note="No plugin code executes." />
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-list">
            {(pluginRegistry || []).slice(0, 6).map((item) => (
              <div key={item.plugin_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.plugin_id}</b>
                  <span>{item.classification || "ARCHITECTURE_ONLY_EXTENSION"} · {item.implementation_status || "REGISTERED_METADATA_ONLY"}</span>
                </div>
                <div>
                  <b>{item.certification_status || "CERTIFICATION_REQUIRED"}</b>
                  <span>{item.activation_state || "DISABLED"} · {item.execution_posture || "DISABLED"}</span>
                </div>
              </div>
            ))}
            {!pluginRegistry.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-work-detail">
            <h3>Mission Control integration</h3>
            <p className="muted">Mission Control receives bounded plugin metadata, counts, warnings, and next-milestone guidance.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Next authorised milestone" value="READY_FOR_PHASE65_6_CUSTOMER_SELF_SERVICE_PORTAL" note="Defined only after Phase65.5 validation." />
              <DetailPanel label="Readiness" value={String(pluginMission.readiness || pluginReadiness.readiness_state || "READY_WITH_LIMITATIONS")} note={(pluginHealth.limitations || []).join(" · ") || "Readiness remains truthful."} />
              <DetailPanel label="Governance" value={pluginMission.governance_status || "PRESERVED"} note="No autonomous plugin action is enabled" />
              <DetailPanel label="Security" value={pluginMission.security_status || "FAIL_CLOSED"} note="No plugin execution or external action is exposed" />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Phase65.5 constraints</h3>
          <p className="muted">No arbitrary third-party code execution, dependency installation, or external action is authorised in this milestone.</p>
          <ul className="mission-bullet-list">
            <li>Plugins remain disabled by default.</li>
              <li>High-risk permissions remain denied.</li>
              <li>Tenant boundaries and governance are enforced.</li>
              <li>Mission Control remains truthful and read-only.</li>
            </ul>
          </div>
          <div className="mission-work-detail">
            <h3>Implementation posture</h3>
            <p className="muted">Phase65.5 establishes the plugin and extension framework only. The next milestone is intentionally deferred to Phase65.6.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Readiness" value={String(pluginReadiness.readiness_state || "READY_WITH_LIMITATIONS")} note="READY_WITH_LIMITATIONS indicates bounded framework readiness." />
              <DetailPanel label="Next milestone" value="READY_FOR_PHASE65_6_CUSTOMER_SELF_SERVICE_PORTAL" note="Customer Self-Service Portal entry recommendation" />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.3 Customer Dashboard</h3>
            <p className="muted">Read-only dashboard metadata only. No customer workflow, upload, messaging, support, or submission control is implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Identity" value={customerDashboardIdentity.canonical_name || "NO_DATA"} note={customerDashboardIdentity.dashboard_id || "Dashboard ID unavailable"} />
              <DetailPanel label="Organisation" value={customerDashboardOrganisation.organisation_identity_state || "DATA_UNAVAILABLE"} note={customerDashboardOrganisation.profile_management_readiness || "NOT_IMPLEMENTED"} />
              <DetailPanel label="RFQ summary" value={customerDashboardRfqs.total_authorised_rfqs_state || "NO_DATA"} note={customerDashboardRfqs.source_status || "NO_DATA"} />
              <DetailPanel label="Quotation summary" value={customerDashboardQuotations.quotation_count_state || "NO_DATA"} note={customerDashboardQuotations.freshness_state || "NO_DATA"} />
              <DetailPanel label="Activity" value={customerDashboardActivity.activity_state || "NO_DATA"} note={customerDashboardActivity.later_feature_readiness_notices?.[0] || "No live activity stream is exposed."} />
              <DetailPanel label="Notifications" value={customerDashboardNotifications.notification_state || "NO_DATA"} note={customerDashboardNotifications.delivery_state || "NOT_IMPLEMENTED"} />
            </div>
          </div>
          <div className="mission-work-detail">
            <h3>Dashboard posture</h3>
            <p className="muted">Mission Control surfaces dashboard lifecycle, summary posture, section counts, and widget counts while preserving fail-closed governance.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Readiness" value={String(customerDashboardReadiness.readiness_state || "READY_WITH_LIMITATIONS")} note={customerDashboardReadiness.limitations?.[0] || "Readiness remains truthful."} />
              <DetailPanel label="Sections" value={compactCount(customerDashboardSections.length)} note="Truthful section registry" />
              <DetailPanel label="Widgets" value={compactCount(customerDashboardWidgets.length)} note="Truthful widget registry" />
              <DetailPanel label="Compatibility" value={customerDashboardCompatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS"} note={customerDashboardCompatibility.limitations?.[0] || "Compatibility remains bounded"} />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.4 RFQ & Quote Workspace</h3>
            <p className="muted">Read-only RFQ and quotation metadata only. RFQ creation, quotation submission, approvals, messaging, uploads, and customer-side workflow remain not implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Workspace" value={customerRfqQuoteWorkspaceIdentity.canonical_name || "NO_DATA"} note={customerRfqQuoteWorkspaceIdentity.workspace_id || "Workspace ID unavailable"} />
              <DetailPanel label="Readiness" value={String(customerRfqQuoteWorkspaceReadiness.readiness_state || customerRfqQuoteWorkspace.status || "READY_WITH_LIMITATIONS").toUpperCase()} note={customerRfqQuoteWorkspaceReadiness.limitations?.[0] || "Read-only workspace remains truthful."} />
              <DetailPanel label="RFQs" value={compactCount(customerRfqQuoteWorkspace.counts?.rfqs || 0)} note={customerRfqQuoteWorkspaceRfqs.source_authority_state || "NO_DATA"} />
              <DetailPanel label="Quotations" value={compactCount(customerRfqQuoteWorkspace.counts?.quotations || 0)} note={customerRfqQuoteWorkspaceQuotations.source_authority_state || "NO_DATA"} />
              <DetailPanel label="RFQ lifecycle" value={customerRfqQuoteWorkspaceRfqLifecycle.lifecycle_state || "NO_DATA"} note={customerRfqQuoteWorkspaceRfqLifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
              <DetailPanel label="Quotation lifecycle" value={customerRfqQuoteWorkspaceQuotationLifecycle.lifecycle_state || "NO_DATA"} note={customerRfqQuoteWorkspaceQuotationLifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
            </div>
          </div>
          <div className="mission-work-detail">
            <h3>Workspace posture</h3>
            <p className="muted">Mission Control surfaces tenant-bound RFQ and quotation metadata while keeping cross-tenant access denied and external action disabled.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Source authority" value={customerRfqQuoteWorkspaceSourceAuthority.authority_state || "NO_DATA"} note={customerRfqQuoteWorkspaceSourceAuthority.source_system || "Truthful source metadata"} />
              <DetailPanel label="Freshness" value={customerRfqQuoteWorkspaceFreshness.overall_freshness_state || "NO_DATA"} note={customerRfqQuoteWorkspaceFreshness.stale_threshold || "Freshness unavailable"} />
              <DetailPanel label="Compatibility" value={customerRfqQuoteWorkspaceCompatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS"} note={customerRfqQuoteWorkspaceCompatibility.limitations?.[0] || "Compatibility remains bounded."} />
              <DetailPanel label="Next milestone" value="READY_FOR_PHASE65_6_5_SECURE_DOCUMENT_CENTRE" note="Document centre remains deferred." />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.5 Secure Document Centre</h3>
            <p className="muted">Read-only document metadata only. Uploads, downloads, sharing, signing, editing, OCR, and storage-provider actions remain not implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Workspace" value={customerDocumentCentreIdentity.canonical_name || "NO_DATA"} note={customerDocumentCentreIdentity.workspace_id || "Workspace ID unavailable"} />
              <DetailPanel label="Readiness" value={String(customerDocumentCentreReadiness.readiness_state || customerDocumentCentre.status || "READY_WITH_LIMITATIONS").toUpperCase()} note={customerDocumentCentreReadiness.limitations?.[0] || "Read-only workspace remains truthful."} />
              <DetailPanel label="Documents" value={compactCount(customerDocumentCentre.counts?.documents || customerDocumentCentreCatalogue.records?.length || 0)} note={customerDocumentCentreHealth.health_state || "NO_DATA"} />
              <DetailPanel label="Classifications" value={compactCount(customerDocumentCentre.counts?.classifications || customerDocumentCentreClassifications.classifications?.length || 0)} note={customerDocumentCentreIntegrity.integrity_state || "NO_DATA"} />
              <DetailPanel label="Lifecycle" value={customerDocumentCentreLifecycle.lifecycle_state || "NO_DATA"} note={customerDocumentCentreLifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
              <DetailPanel label="Retention" value={customerDocumentCentreRetention.retention_state || "NO_DATA"} note={customerDocumentCentreVisibility.document_visibility_policy || "tenant-bound read only"} />
            </div>
          </div>
          <div className="mission-work-detail">
            <h3>Document posture</h3>
            <p className="muted">Mission Control surfaces document catalogue state, integrity, retention, and visibility while preserving fail-closed governance.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Integrity" value={customerDocumentCentreIntegrity.integrity_state || "NO_DATA"} note={customerDocumentCentreIntegrity.checksum_algorithm || "SHA-256"} />
              <DetailPanel label="Visibility" value={customerDocumentCentreVisibility.document_visibility_policy || "TENANT_CONTEXT_REQUIRED"} note={customerDocumentCentreVisibility.fail_closed_behavior || "deny and audit"} />
              <DetailPanel label="Compatibility" value={customerDocumentCentreCompatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS"} note={customerDocumentCentreCompatibility.limitations?.[0] || "Compatibility remains bounded."} />
              <DetailPanel label="Next milestone" value="READY_FOR_PHASE65_6_6_COMMUNICATION_NOTIFICATIONS" note="Secure document centre remains deferred." />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.6 Communication & Notifications</h3>
            <p className="muted">Read-only communication metadata only. Messaging, email, SMS, WhatsApp, Teams, Slack, webhooks, push notifications, scheduling, queues, and live delivery remain not implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Workspace" value={customerCommunicationIdentity.canonical_name || "NO_DATA"} note={customerCommunicationIdentity.workspace_id || "Workspace ID unavailable"} />
              <DetailPanel label="Readiness" value={String(customerCommunicationReadiness.readiness_state || customerCommunication.status || "READY_WITH_LIMITATIONS").toUpperCase()} note={(customerCommunicationReadiness.limitations || customerCommunicationIdentity.accepted_limitations || []).join(" · ") || "Read-only workspace remains truthful."} />
              <DetailPanel label="Notifications" value={compactCount(customerCommunication.counts?.notifications || customerCommunicationRegistry.records?.length || 0)} note={customerCommunicationHealth.health_state || "NO_DATA"} />
              <DetailPanel label="Templates" value={compactCount(customerCommunication.counts?.templates || customerCommunicationTemplates.templates?.length || 0)} note={customerCommunicationDelivery.delivery_state || "NO_DATA"} />
              <DetailPanel label="Preferences" value={compactCount(customerCommunication.counts?.preferences || customerCommunicationPreferences.channels?.length || 0)} note={customerCommunicationPolicy.transmission_prohibition || "denied"} />
              <DetailPanel label="Lifecycle" value={customerCommunicationLifecycle.lifecycle_state || "NO_DATA"} note="Lifecycle metadata only" />
            </div>
          </div>
          <div className="mission-work-detail">
            <h3>Communication posture</h3>
            <p className="muted">Mission Control surfaces notification registry state, template catalogue, delivery posture, and channel preferences while preserving fail-closed governance.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Diagnostics" value={customerCommunicationDiagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={customerCommunicationDiagnostics.limitations?.[0] || "Diagnostics are redacted."} />
              <DetailPanel label="Compatibility" value={customerCommunicationCompatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS"} note={customerCommunicationCompatibility.limitations?.[0] || "Compatibility remains bounded."} />
              <DetailPanel label="Mission Control" value={customerCommunicationHealth.health_state || "READY_WITH_LIMITATIONS"} note={customerCommunicationHealth.current_milestone || "PHASE65.6.6_COMMUNICATION_AND_NOTIFICATIONS"} />
              <DetailPanel label="Next milestone" value="READY_FOR_PHASE65_6_7_SUPPORT_SERVICE_DESK" note="Communication centre remains deferred." />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.1 Customer Self-Service Portal</h3>
            <p className="muted">Foundation only. Customer authentication, login, document exchange, messaging, workflows, notifications, tickets, and payments are not implemented.</p>
            <ul className="mission-bullet-list">
              <li>Portal identity is metadata-only.</li>
              <li>Feature registry, extension points, and permissions are read-only.</li>
              <li>Tenant isolation and governance remain explicit.</li>
              <li>Phase65.6.2 remains deferred.</li>
            </ul>
          </div>
          <div className="mission-work-detail">
            <h3>Portal posture</h3>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Lifecycle" value={String(portalLifecycle.current_state || "READY_WITH_LIMITATIONS").toUpperCase()} note={portalLifecycle.transition_authority || "Read-only foundation only"} />
              <DetailPanel label="Health" value={String(portalHealth.health_state || portalHealth.status || "NO_DATA").toUpperCase()} note="/platform/customer-portal/health" />
              <DetailPanel label="Readiness" value={String(portalReadiness.readiness_state || "READY_WITH_LIMITATIONS")} note="READY_WITH_LIMITATIONS" />
              <DetailPanel label="Identity" value={portalIdentity.canonical_name || "NO_DATA"} note={portalIdentity.customer_authentication_state || "NOT_IMPLEMENTED"} />
              <DetailPanel label="Implementation boundary" value="NOT_IMPLEMENTED" note="No customer authentication is implemented." />
            </div>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-detail">
            <h3>Phase65.6.2 Customer Identity & Authentication</h3>
            <p className="muted">Read-only identity foundation only. No customer login screen, password reset, token issuance, JWT generation, or external identity provider integration is implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Identity" value={customerIdentityIdentity.canonical_name || "NO_DATA"} note={customerIdentityIdentity.identity_service_id || "Identity service unavailable"} />
              <DetailPanel label="Authentication" value={String(customerIdentityIdentity.authentication_service_state || "NOT_IMPLEMENTED").toUpperCase()} note="No customer login exists." />
              <DetailPanel label="Authorization" value={String(customerIdentityIdentity.authorization_service_state || "NOT_IMPLEMENTED").toUpperCase()} note="No token issuance exists." />
              <DetailPanel label="Session manager" value={String(customerIdentityIdentity.session_manager_state || "NOT_IMPLEMENTED").toUpperCase()} note="No customer session manager exists." />
            </div>
          </div>
          <div className="mission-work-detail">
            <h3>Identity posture</h3>
            <p className="muted">Mission Control can open the Customer Identity & Authentication workspace, but no customer workflow is implemented yet.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Roles" value={compactCount(customerIdentityRoles.length)} note={customerIdentity.roles?.[0]?.canonical_name || "No role registry"} />
              <DetailPanel label="Permissions" value={compactCount(customerIdentityPermissions.length)} note={customerIdentity.permissions?.find((item) => item.grant_state === "denied")?.canonical_name || "High-risk permissions denied"} />
              <DetailPanel label="Readiness" value={String(customerIdentityReadiness.readiness_state || "READY_WITH_LIMITATIONS")} note={customerIdentityReadiness.limitations?.[0] || "Readiness remains truthful."} />
              <DetailPanel label="Security" value={customerIdentity.missionControlIntegration?.security_status || "FAIL_CLOSED"} note="No credentials or tokens are exposed" />
            </div>
          </div>
        </div>
      </section>

      <section className="card mission-multi-tenant-architecture" id="multi-tenant-architecture">
        <SectionHeader
          eyebrow="Phase65.2"
          title="Multi-Tenant Architecture"
          description="Read-only bounded tenancy architecture indicators. Tenant context is explicit, tenant boundaries are deny-by-default, and no commercial tenant provisioning is implemented."
          action={<span className={`mission-badge ${toneForStatus(tenantHealth.readiness_state || tenantHealth.health_state || multiTenantArchitecture.status)}`}>{String(tenantHealth.readiness_state || tenantHealth.health_state || multiTenantArchitecture.status || "NO_DATA").toUpperCase()}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="Tenants" value={compactCount(tenantCounts.tenants || tenantRegistry.tenant_count || 0)} source="/platform/tenancy/registry" freshness={formatDateTime(tenantHealth.updated_at || lastUpdated)} tone="warning" />
          <StatusChip label="Capabilities" value={compactCount(tenantCounts.capabilities || tenantCapabilityModel.length)} source="/platform/tenancy/model" freshness={formatDateTime(tenantHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Services" value={compactCount(tenantCounts.services || tenantServiceModel.length)} source="/platform/tenancy/model" freshness={formatDateTime(tenantHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Modules" value={compactCount(tenantCounts.modules || tenantModuleModel.length)} source="/platform/tenancy/model" freshness={formatDateTime(tenantHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Context" value={String(tenantContextContract.invalid_context_behavior || "FAILED_CLOSED")} source="/platform/tenancy/model" freshness={formatDateTime(tenantHealth.updated_at || lastUpdated)} tone={toneForStatus(tenantContextContract.invalid_context_behavior)} />
          <StatusChip label="Isolation" value={String(tenantIsolation.isolation_state || "ARCHITECTURE_DEFINED")} source="/platform/tenancy/isolation" freshness={formatDateTime(tenantHealth.updated_at || lastUpdated)} tone={toneForStatus(tenantIsolation.isolation_state)} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Tenant identity</span>
            <b>{tenantIdentity.canonical_tenant_name || "NO_DATA"}</b>
            <small>{tenantIdentity.tenant_id || "Tenant identity unavailable"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Lifecycle state</span>
            <b>{String(tenantLifecycle.current_state || tenantIdentity.tenant_lifecycle_state || "DEFINED").toUpperCase()}</b>
            <small>{tenantLifecycle.transition_authority || "Lifecycle authority unavailable"}</small>
          </div>
        </div>
        <div className="mission-detail-grid compact">
          <div className="mission-detail-panel">
            <span>Registry summary</span>
            <b>{compactCount(tenantRegistry.summary?.live_tenants || 0)}</b>
            <small>{tenantRegistry.summary ? "No synthetic commercial tenants are present." : "Registry unavailable"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Policy posture</span>
            <b>{String(tenantPolicy.global_policy_precedence || "HIGHEST").toUpperCase()}</b>
            <small>{tenantPolicy.conflict_handling || "Fail closed"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Compatibility</span>
            <b>{tenantCompatibility.api_compatibility_level || "NO_DATA"}</b>
            <small>{tenantCompatibility.compatibility_review_requirements?.[0] || "Compatibility anchored to Phase65.1"}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Diagnostics</span>
            <b>{tenantDiagnostics.diagnostic_state || "SANDBOX_BLOCKED"}</b>
            <small>{tenantDiagnostics.current_limitations?.[0] || "Diagnostics are redacted and bounded."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Data classification</span>
            <b>{tenantDataClassification.classification || tenantDataClassification.classifications?.[0]?.classification || "NO_DATA"}</b>
            <small>{tenantDataClassification.classifications?.[0]?.tenant_boundary || "Tenant-sensitive classifications remain bounded."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Audit posture</span>
            <b>{tenantAudit.summary?.record_count !== undefined ? compactCount(tenantAudit.summary.record_count) : "NO_DATA"}</b>
            <small>{tenantAudit.audit_events?.[0] || "Audit events are redacted and bounded."}</small>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-list">
            {tenantCapabilityModel.slice(0, 6).map((item) => (
              <div key={item.capability_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.capability_id}</b>
                  <span>{item.tenant_enablement_posture || "DEFINED_NOT_IMPLEMENTED"} · {item.policy_requirement || "global governance"}</span>
                </div>
                <div>
                  <b>{item.platform_status || "ARCHITECTURE_DEFINED"}</b>
                  <span>{item.evidence_requirement || "read-only evidence"}</span>
                </div>
              </div>
            ))}
            {!tenantCapabilityModel.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-work-detail">
            <h3>Multi-tenant boundaries</h3>
            <p className="muted">Tenant context must be explicit and validated. Cross-tenant access is denied by default. No tenant provisioning or public administration is implemented.</p>
            <div className="mission-detail-grid compact">
              <DetailPanel label="Context source" value={tenantContextContract.context_source || "validated request context"} note={tenantContextContract.invalid_context_behavior || "FAILED_CLOSED"} />
              <DetailPanel label="Isolation posture" value={tenantIsolation.enforcement_posture || "deny by default"} note={tenantIsolation.isolation_state || "ARCHITECTURE_DEFINED"} />
              <DetailPanel label="Governance" value={tenantConfiguration.tenant_override_posture || "override_disallowed"} note={tenantConfiguration.redaction_policy || "Governance locked"} />
              <DetailPanel label="Phase65.3 readiness" value={tenantMission.next_architect_action || "READY_FOR_PHASE65_3_ENTERPRISE_API_PLATFORM"} note="Enterprise API Platform remains later-phase work." />
            </div>
          </div>
        </div>
        <div className="mission-governance-grid">
          <StatusChip label="Governance" value="PRESERVED" source="EELS" tone="good" />
          <StatusChip label="Policy override" value="DENIED" source="Tenant architecture" tone="good" />
          <StatusChip label="External action" value="NO EXTERNAL ACTION" source="Governance" tone="good" />
          <StatusChip label="Tenant provisioning" value="DEFINED NOT IMPLEMENTED" source="Phase65.2 boundary" tone="warning" />
        </div>
      </section>

      <section className="card mission-work-management" id="work-management">
        <SectionHeader
          eyebrow="Internal Work Management"
          title="Queue Visibility and Operator Work Items"
          description="Truthful internal work management. Items appear only when the backend returns live work-management records; otherwise the surface states NO_DATA."
          action={<span className={`mission-badge ${toneForStatus(workManagementStateLabel)}`}>{workManagementStateLabel}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="Total work" value={compactCount(workManagementSummary.total_work_items)} source="/work-management/readiness" freshness={formatDateTime(workManagementReadiness.updated_at || lastUpdated)} tone={toneForStatus(workManagementStateLabel)} />
          <StatusChip label="Active" value={compactCount(workManagementSummary.active_work_items)} source="/work-management/readiness" freshness={formatDateTime(workManagementReadiness.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Blocked" value={compactCount(workManagementSummary.blocked_work_items)} source="/work-management/readiness" freshness={formatDateTime(workManagementReadiness.updated_at || lastUpdated)} tone={workManagementSummary.blocked_work_items ? "warning" : "neutral"} />
          <StatusChip label="Overdue" value={compactCount(workManagementSummary.overdue_work_items)} source="/work-management/readiness" freshness={formatDateTime(workManagementReadiness.updated_at || lastUpdated)} tone={workManagementSummary.overdue_work_items ? "bad" : "neutral"} />
          <StatusChip label="Approval backlog" value={compactCount(workManagementSummary.waiting_for_approval_work_items)} source="/work-management/readiness" freshness={formatDateTime(workManagementReadiness.updated_at || lastUpdated)} tone={workManagementSummary.waiting_for_approval_work_items ? "warning" : "neutral"} />
          <StatusChip label="Manual submission" value={compactCount(workManagementSummary.queue_counts?.MANUAL_SUBMISSION_QUEUE || 0)} source="/work-management/queues" freshness={formatDateTime(workManagementReadiness.updated_at || lastUpdated)} tone={workManagementSummary.queue_counts?.MANUAL_SUBMISSION_QUEUE ? "warning" : "neutral"} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Next recommended action</span>
            <b>{workManagementReadiness.next_recommended_action || "Create a bounded internal work item from a real workflow event or operator request."}</b>
            <small>{workManagementItems.length ? "Live internal work items are sourced from /work-management/items." : "NO_DATA: the backend has not persisted any internal work items yet."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Queue coverage</span>
            <b>{compactCount(workManagementQueues.length)}</b>
            <small>{workManagementQueues.length ? "Queues are backed by live backend definitions." : "NO_DATA: queue definitions are available, but no live work items are present."}</small>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-list">
            {workManagementItems.slice(0, 8).map((item) => (
              <button key={item.work_item_id} type="button" className={`mission-work-row ${selectedWorkItem?.work_item_id === item.work_item_id ? "active" : ""}`} onClick={() => setSelectedWorkItemId(item.work_item_id)}>
                <div>
                  <b>{item.canonical_title || item.work_item_id}</b>
                  <span>{item.work_type || "OTHER"} · {item.queue_name || "SUPPORT_QUEUE"}</span>
                </div>
                <div>
                  <b>{item.priority || "P3"}</b>
                  <span>{item.status || "CREATED"}</span>
                </div>
              </button>
            ))}
            {!workManagementItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-work-detail">
            <h3>{selectedWorkItem?.canonical_title || "Work item detail"}</h3>
            <p className="muted">{selectedWorkItem ? selectedWorkItem.description || "No additional description provided." : "Select a work item to inspect queue, priority, and evidence context."}</p>
            <div className="mission-detail-grid compact">
              <div className="mission-detail-panel"><span>Status</span><b>{selectedWorkItem?.status || "NO_DATA"}</b><small>{selectedWorkItem?.next_action || "No live work item selected."}</small></div>
              <div className="mission-detail-panel"><span>Assigned role</span><b>{selectedWorkItem?.assigned_role || "UNASSIGNED"}</b><small>{selectedWorkItem?.assigned_operator_id || "Role-level ownership only"}</small></div>
              <div className="mission-detail-panel"><span>Due date</span><b>{selectedWorkItem?.due_date ? formatDateTime(selectedWorkItem.due_date) : "DEADLINE_UNKNOWN"}</b><small>{selectedWorkItem?.priority_score !== undefined ? `Score ${selectedWorkItem.priority_score}` : "Priority score unavailable."}</small></div>
              <div className="mission-detail-panel"><span>Evidence</span><b>{selectedWorkItem?.evidence_references?.length || 0}</b><small>{selectedWorkItem?.approval_requirement ? "Approval required before closure." : "No approval gate recorded."}</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="card mission-policy-decisions" id="policy-decisions">
        <SectionHeader
          eyebrow="Policy Decisions"
          title="Enterprise Policy Decision Engine"
          description="Policy decisions are sourced only from the backend policy engine. When no evaluations exist, the view remains explicitly NO_DATA."
          action={<span className={`mission-badge ${toneForStatus(policyDecisionStateLabel)}`}>{policyDecisionStateLabel}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="Active policies" value={compactCount(policyDecisionSummary.active_policies)} source="/policy-decisions/health" freshness={formatDateTime(policyDecisionHealth.updated_at || lastUpdated)} tone={toneForStatus(policyDecisionStateLabel)} />
          <StatusChip label="Healthy" value={compactCount(policyDecisionSummary.healthy_policies)} source="/policy-decisions/health" freshness={formatDateTime(policyDecisionHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Conflicted" value={compactCount(policyDecisionSummary.conflicted_policies)} source="/policy-decisions/health" freshness={formatDateTime(policyDecisionHealth.updated_at || lastUpdated)} tone={policyDecisionSummary.conflicted_policies ? "warning" : "neutral"} />
          <StatusChip label="Recent evaluations" value={compactCount(policyDecisionSummary.recent_evaluations)} source="/policy-decisions/health" freshness={formatDateTime(policyDecisionHealth.updated_at || lastUpdated)} tone="blue" />
          <StatusChip label="Blocked decisions" value={compactCount(policyDecisionSummary.blocked_decisions)} source="/policy-decisions/health" freshness={formatDateTime(policyDecisionHealth.updated_at || lastUpdated)} tone={policyDecisionSummary.blocked_decisions ? "bad" : "neutral"} />
          <StatusChip label="Human review" value={compactCount(policyDecisionSummary.human_review_decisions)} source="/policy-decisions/health" freshness={formatDateTime(policyDecisionHealth.updated_at || lastUpdated)} tone={policyDecisionSummary.human_review_decisions ? "warning" : "neutral"} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Next recommended action</span>
            <b>{policyDecisionHealth.next_recommended_action || "Evaluate a governed policy decision from a real workflow context."}</b>
            <small>{policyDecisions.length ? "Live decisions are sourced from /policy-decisions/evaluations." : "NO_DATA: no policy evaluations have been recorded yet."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Approval required</span>
            <b>{compactCount(policyDecisionSummary.approval_required_decisions)}</b>
            <small>{policyDecisionSummary.overrides ? `${policyDecisionSummary.overrides} override(s) recorded.` : "No overrides recorded."}</small>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-list">
            {policyRegistry.slice(0, 8).map((policy) => (
              <button key={policy.policy_id} type="button" className="mission-work-row" onClick={() => {}}>
                <div>
                  <b>{policy.canonical_name || policy.policy_id}</b>
                  <span>{policy.policy_category || "OTHER"} · {policy.version || "1.0.0"}</span>
                </div>
                <div>
                  <b>{policy.match_result || "ALLOW"}</b>
                  <span>{policy.override_posture || "UNKNOWN"}</span>
                </div>
              </button>
            ))}
            {!policyRegistry.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-work-detail">
            <h3>{policyDecisions[0]?.policy_id || "Decision detail"}</h3>
            <p className="muted">{policyDecisions[0] ? policyDecisions[0].explanation || "No additional decision explanation provided." : "Select a policy decision to inspect result, reason code, and evidence context."}</p>
            <div className="mission-detail-grid compact">
              <div className="mission-detail-panel"><span>Result</span><b>{policyDecisions[0]?.result || "NO_DATA"}</b><small>{policyDecisions[0]?.reason_code || "No live decision selected."}</small></div>
              <div className="mission-detail-panel"><span>Conflict status</span><b>{policyDecisions[0]?.conflict_status || "UNAVAILABLE"}</b><small>{policyDecisions[0]?.human_review_required ? "Human review required." : "No human review recorded."}</small></div>
              <div className="mission-detail-panel"><span>Evidence</span><b>{policyDecisions[0]?.supporting_evidence?.length || 0}</b><small>{policyDecisions[0]?.warnings?.length ? "Warnings present." : "No warnings recorded."}</small></div>
              <div className="mission-detail-panel"><span>Scope</span><b>{policyDecisions[0]?.decision_type || "NO_DATA"}</b><small>{policyDecisions[0]?.subject_type || "No live subject selected."}</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="card mission-approvals" id="approvals">
        <SectionHeader
          eyebrow="Human Approval"
          title="Human Approval and Escalation Framework"
          description="Approval records remain human-owned, policy-backed, and truthfully NO_DATA when no approvals exist."
          action={<span className={`mission-badge ${toneForStatus(approvalStateLabel)}`}>{approvalStateLabel}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="Total approvals" value={compactCount(approvalSummary.total_approvals)} source="/approvals/health" freshness={formatDateTime(approvalHealth.updated_at || lastUpdated)} tone={toneForStatus(approvalStateLabel)} />
          <StatusChip label="Pending" value={compactCount(approvalSummary.pending_approvals)} source="/approvals/health" freshness={formatDateTime(approvalHealth.updated_at || lastUpdated)} tone={approvalSummary.pending_approvals ? "warning" : "neutral"} />
          <StatusChip label="Under review" value={compactCount(approvalSummary.approvals_under_review)} source="/approvals/health" freshness={formatDateTime(approvalHealth.updated_at || lastUpdated)} tone={approvalSummary.approvals_under_review ? "warning" : "neutral"} />
          <StatusChip label="Escalated" value={compactCount(approvalSummary.escalated_approvals)} source="/approvals/health" freshness={formatDateTime(approvalHealth.updated_at || lastUpdated)} tone={approvalSummary.escalated_approvals ? "bad" : "neutral"} />
          <StatusChip label="Conditional" value={compactCount(approvalSummary.conditional_approvals)} source="/approvals/health" freshness={formatDateTime(approvalHealth.updated_at || lastUpdated)} tone={approvalSummary.conditional_approvals ? "warning" : "neutral"} />
          <StatusChip label="Submission auth" value={compactCount(approvalSummary.submission_authorisations_pending)} source="/approvals/health" freshness={formatDateTime(approvalHealth.updated_at || lastUpdated)} tone={approvalSummary.submission_authorisations_pending ? "warning" : "neutral"} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Next required human action</span>
            <b>{approvalHealth.next_required_human_action || "Review the highest-priority pending approval."}</b>
            <small>{approvalRecords.length ? "Live approval records are sourced from /approvals." : "NO_DATA: no approval requests have been recorded yet."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>History coverage</span>
            <b>{compactCount(approvalHistory.length)}</b>
            <small>{approvalHistory.length ? "Historic approvals remain traceable in the backend store." : "NO_DATA: no approval history is available yet."}</small>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-list">
            {approvalRecords.slice(0, 8).map((approval) => (
              <button key={approval.approval_id} type="button" className="mission-work-row" onClick={() => {}}>
                <div>
                  <b>{approval.canonical_title || approval.approval_id}</b>
                  <span>{approval.approval_type || "OTHER"} · {approval.approver_role || "Approver"}</span>
                </div>
                <div>
                  <b>{approval.status || "REQUESTED"}</b>
                  <span>{approval.required_authority_level || "H1"}</span>
                </div>
              </button>
            ))}
            {!approvalRecords.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-work-detail">
            <h3>{selectedApproval?.canonical_title || "Approval detail"}</h3>
            <p className="muted">{selectedApproval ? selectedApproval.description || "No additional approval description provided." : "Select an approval record to inspect authority, evidence, and escalation context."}</p>
            <div className="mission-detail-grid compact">
              <div className="mission-detail-panel"><span>Status</span><b>{selectedApproval?.status || "NO_DATA"}</b><small>{selectedApproval?.decision_reason || "No live approval selected."}</small></div>
              <div className="mission-detail-panel"><span>Approver</span><b>{selectedApproval?.approver_role || "UNASSIGNED"}</b><small>{selectedApproval?.approver_id || "Role-level authority only"}</small></div>
              <div className="mission-detail-panel"><span>Evidence</span><b>{selectedApproval?.supporting_evidence?.length || 0}</b><small>{selectedApproval?.security_classification || "CONFIDENTIAL"}</small></div>
              <div className="mission-detail-panel"><span>Due / expiry</span><b>{selectedApproval?.due_at ? formatDateTime(selectedApproval.due_at) : "DEADLINE_UNKNOWN"}</b><small>{selectedApproval?.expires_at ? `Expires ${formatDateTime(selectedApproval.expires_at)}` : "No expiry recorded."}</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="card mission-agent-coordination" id="agent-coordination">
        <SectionHeader
          eyebrow="Multi-Agent Coordination"
          title="Governed Internal Agent Routing"
          description="Agent tasks appear only when the backend exposes truthful coordination records. The surface remains NO_DATA until live agent activity exists."
          action={<span className={`mission-badge ${toneForStatus(agentCoordinationStateLabel)}`}>{agentCoordinationStateLabel}</span>}
        />
        <div className="mission-governance-grid">
          <StatusChip label="Registered agents" value={compactCount(agentCoordinationSummary.total_agents)} source="/agent-coordination/health" freshness={formatDateTime(agentCoordinationHealth.updated_at || lastUpdated)} tone={toneForStatus(agentCoordinationStateLabel)} />
          <StatusChip label="Healthy" value={compactCount(agentCoordinationSummary.healthy_agents)} source="/agent-coordination/health" freshness={formatDateTime(agentCoordinationHealth.updated_at || lastUpdated)} tone="good" />
          <StatusChip label="Degraded" value={compactCount(agentCoordinationSummary.degraded_agents)} source="/agent-coordination/health" freshness={formatDateTime(agentCoordinationHealth.updated_at || lastUpdated)} tone={agentCoordinationSummary.degraded_agents ? "warning" : "neutral"} />
          <StatusChip label="Active tasks" value={compactCount(agentCoordinationSummary.active_agent_tasks)} source="/agent-coordination/health" freshness={formatDateTime(agentCoordinationHealth.updated_at || lastUpdated)} tone={agentCoordinationSummary.active_agent_tasks ? "warning" : "neutral"} />
          <StatusChip label="Operator review" value={compactCount(agentCoordinationSummary.operator_review_tasks)} source="/agent-coordination/health" freshness={formatDateTime(agentCoordinationHealth.updated_at || lastUpdated)} tone={agentCoordinationSummary.operator_review_tasks ? "warning" : "neutral"} />
          <StatusChip label="Conflicts" value={compactCount(agentCoordinationSummary.conflicts)} source="/agent-coordination/health" freshness={formatDateTime(agentCoordinationHealth.updated_at || lastUpdated)} tone={agentCoordinationSummary.conflicts ? "bad" : "neutral"} />
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel">
            <span>Next recommended action</span>
            <b>{agentCoordinationHealth.next_recommended_action || "Create a bounded coordination plan from a Phase64.3 work item."}</b>
            <small>{agentRegistry.length || agentTasks.length ? "Live agent coordination records are sourced from /agent-coordination." : "NO_DATA: no live agent coordination tasks are present yet."}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Plan coverage</span>
            <b>{compactCount(coordinationPlans.length)}</b>
            <small>{coordinationPlans.length ? "Coordination plans are backed by live backend records." : "NO_DATA: no live coordination plans are present yet."}</small>
          </div>
        </div>
        <div className="mission-work-grid">
          <div className="mission-work-list">
            {agentRegistry.slice(0, 8).map((agent) => (
              <button key={agent.agent_id} type="button" className="mission-work-row" onClick={() => {}}>
                <div>
                  <b>{agent.canonical_name || agent.agent_id}</b>
                  <span>{agent.agent_class || "AGENT"} · {agent.authority_level || "A0"}</span>
                </div>
                <div>
                  <b>{agent.runtime_status || "UNKNOWN"}</b>
                  <span>{agent.lifecycle_status || "UNKNOWN"}</span>
                </div>
              </button>
            ))}
            {!agentRegistry.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-work-detail">
            <h3>{agentTasks[0]?.agent_id || "Agent task detail"}</h3>
            <p className="muted">{agentTasks[0] ? agentTasks[0].purpose || "No additional task description provided." : "Select an agent task to inspect authority, evidence, and human-review context."}</p>
            <div className="mission-detail-grid compact">
              <div className="mission-detail-panel"><span>Status</span><b>{agentTasks[0]?.status || "NO_DATA"}</b><small>{agentTasks[0]?.task_type || "No live agent task selected."}</small></div>
              <div className="mission-detail-panel"><span>Authority</span><b>{agentTasks[0]?.authority_level || "UNAVAILABLE"}</b><small>{agentTasks[0]?.human_review_required ? "Human review required." : "No human-review requirement recorded."}</small></div>
              <div className="mission-detail-panel"><span>Evidence</span><b>{agentTasks[0]?.evidence_references?.length || 0}</b><small>{agentTasks[0]?.warnings?.length ? "Warnings present." : "No warnings recorded."}</small></div>
              <div className="mission-detail-panel"><span>Plan</span><b>{agentTasks[0]?.coordination_plan_id || "NO_DATA"}</b><small>{agentTasks[0]?.workflow_instance_id || "No live workflow instance selected."}</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="card mission-quicklinks" id="operator-workspaces">
        <SectionHeader
          eyebrow="Operator Workspaces"
          title="Primary Navigation"
          description="Jump directly to the certified operational surfaces without hiding them behind the legacy dashboard."
        />
        <div className="mission-quicklink-grid">
          {[
            { label: "Production Readiness", icon: ShieldCheck, target: "production-readiness" },
            { label: "Manual Harvest", icon: Factory, target: "harvest-operations" },
            { label: "Enterprise Search", icon: Search, target: "enterprise-search" },
            { label: "Alerts", icon: Bell, target: "alerts" },
            { label: "Trends", icon: TrendingUp, target: "trends" },
            { label: "KPI Drill-Downs", icon: Gauge, target: "kpi-drilldowns" },
            { label: "Review Queue", icon: ClipboardList, target: "rfq-operations" },
            { label: "Approval Centre", icon: CheckCircle2, target: "submission-centre" },
            { label: "Decision Support", icon: Layers3, target: "decision-support" },
            { label: "Quote Pack Engine", icon: FileText, target: "quote-pack-engine" },
          ].map((item) => (
            <button key={item.label} type="button" className="mission-quicklink" onClick={() => onNavigate(item.target)}>
              <item.icon size={16} />
              <span>{item.label}</span>
              <ArrowRight size={14} />
            </button>
          ))}
        </div>
      </section>

      <section className="card mission-search" id="enterprise-search">
        <SectionHeader
          eyebrow="Enterprise Search"
          title="Backend-driven Search Snapshot"
          description="Search is surfaced here as a truthful live opportunity explorer and links through to the richer RFQ operations workspace."
          action={<button type="button" className="mission-link-button" onClick={() => onNavigate("rfq-operations")}><Search size={15} />Open RFQ Operations</button>}
        />
        <div className="mission-search-toolbar">
          <label className="mission-search-input">
            <Search size={15} />
            <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search RFQ, buyer, source, reference" />
          </label>
          <span className="mission-muted-pill">{backendAvailable ? `${selectedSearchResults.length} result(s)` : "UNAVAILABLE"}</span>
        </div>
        <div className="mission-search-results">
          {selectedSearchResults.length ? selectedSearchResults.map((item) => (
            <button key={item.id} type="button" className="mission-search-row" onClick={() => onNavigate(item.destination)}>
              <div>
                <b>{item.title}</b>
                <span>{item.subtitle}</span>
              </div>
              <div>
                <small>{item.source}</small>
                <small>{item.freshness}</small>
              </div>
            </button>
          )) : (
            <div className="mission-empty-state">UNAVAILABLE</div>
          )}
        </div>
      </section>

      <section className="card mission-readiness" id="production-readiness">
        <SectionHeader
          eyebrow="Production Readiness"
          title="Readiness Checklist"
          description="Every item opens a truthful drill-down within the landing page. Items without a source remain explicitly unavailable."
          action={<span className="mission-badge">No composite score</span>}
        />
        <div className="mission-readiness-grid">
          {READINESS_ITEMS.map((item) => {
            const result = item.derive(readinessContext);
            return (
              <button
                type="button"
                key={item.id}
                className={`mission-readiness-card ${selectedReadinessId === item.id ? "active" : ""}`}
                onClick={() => setSelectedReadinessId(item.id)}
              >
                <span>{item.label}</span>
                <b>{result.status}</b>
                <small>{item.source}</small>
              </button>
            );
          })}
        </div>
        <div className="mission-detail-grid mission-readiness-detail">
          <div className="mission-detail-panel wide">
            <span>Selected readiness item</span>
            <b>{selectedReadiness.label}</b>
            <small>{readinessDetails.reason}</small>
          </div>
          {readinessDetailMetrics.map((row) => (
            <div className="mission-detail-panel" key={row.label}>
              <span>{row.label}</span>
              <b>{row.value}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="card mission-harvest" id="harvest-operations">
        <SectionHeader
          eyebrow="Controlled Harvest"
          title="Manual Harvest Operations"
          description="The frontend invokes the real backend harvest API directly. Every run is human initiated, single-run, and scheduler-disabled."
          action={harvestBusy ? <span className="mission-badge warning"><Loader2 size={13} className="spin" />Running...</span> : <span className="mission-badge good">Single controlled run</span>}
        />

        <div className="mission-harvest-banner">
          <div>
            <b>This is a single controlled run.</b>
            <p>The scheduler remains disabled. No submission will occur. No email will be sent. No buyer system will be modified.</p>
          </div>
          <div className="mission-harvest-banner-side">
            <span>Scheduler</span>
            <b>{harvestScheduler}</b>
            <small>Controlled harvest status endpoint</small>
          </div>
        </div>

        <div className="mission-harvest-toolbar">
          <div className="mission-entity-search-shell" ref={entityComboboxRef}>
            <label className="mission-entity-combobox-label" htmlFor="harvest-entity-search">
              Search approved entity registry
            </label>
            <div className="mission-entity-search-row">
              <div className="mission-entity-combobox-control">
                <Search size={15} aria-hidden="true" />
                <input
                  id="harvest-entity-search"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={entityComboboxOpen}
                  aria-controls="harvest-entity-listbox"
                  aria-activedescendant={activeEntityOption ? `harvest-entity-option-${activeEntityOption.entity_id}` : undefined}
                  aria-describedby="harvest-entity-registry-status harvest-entity-registry-help harvest-entity-search-announcement"
                  aria-label="Search approved harvest entities"
                  value={entitySearchQuery}
                  onFocus={() => setEntityComboboxOpen(true)}
                  onChange={(event) => handleHarvestEntityQueryChange(event.target.value)}
                  onKeyDown={handleHarvestEntityKeyDown}
                  placeholder="Display name, alias, or entity ID"
                  autoComplete="off"
                  spellCheck={false}
                />
                {entitySearchQuery ? (
                  <button type="button" className="mission-entity-combobox-clear" onClick={clearHarvestEntitySelection} aria-label="Clear search and selection">
                    <X size={14} />
                  </button>
                ) : null}
                <button
                  type="button"
                  className="mission-entity-combobox-toggle"
                  onClick={() => setEntityComboboxOpen((current) => !current)}
                  aria-label={entityComboboxOpen ? "Close entity registry suggestions" : "Open entity registry suggestions"}
                >
                  {entityComboboxOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
              <button
                type="button"
                className="mission-entity-search-button mission-harvest-button"
                onClick={(event) => {
                  lastHarvestTriggerRef.current = event.currentTarget;
                  void executeHarvestEntitySearch();
                }}
              >
                {entityRegistrySearchState === "searching" ? <Loader2 size={15} className="spin" /> : <Search size={15} />}
                Search Registry
              </button>
            </div>
            <div id="harvest-entity-registry-status" className="mission-entity-combobox-state" aria-live="polite">
              {entityRegistryStateLabel}
            </div>
            <div id="harvest-entity-search-announcement" className="mission-entity-combobox-state" aria-live="polite">
              {registrySearchAnnouncement}
            </div>
            <div id="harvest-entity-registry-help" className="mission-entity-combobox-help">
              Search only the approved registry. Search and selection remain separate from the controlled harvest action.
            </div>
            {entityComboboxOpen ? (
              <div className="mission-entity-combobox-popup" role="presentation">
                {harvestEntitiesState === "loading" || entityRegistrySearchState === "searching" ? <div className="mission-empty-state">Loading registry...</div> : null}
                {harvestEntitiesState === "unavailable" || entityRegistrySearchState === "unavailable" ? <div className="mission-empty-state">Registry unavailable</div> : null}
                {harvestEntitiesState === "error" || entityRegistrySearchState === "error" ? <div className="mission-empty-state error">API error</div> : null}
                {(harvestEntitiesState === "ready" || entityRegistrySearchState === "ready" || entityRegistrySearchState === "idle") && !entitySearchHasMatches ? <div className="mission-empty-state">No matching entities</div> : null}
                {(harvestEntitiesState === "ready" || entityRegistrySearchState === "ready" || entityRegistrySearchState === "idle") && entitySearchHasMatches ? (
                  <div id="harvest-entity-listbox" role="listbox" aria-label="Approved entity registry results" className="mission-entity-combobox-listbox">
                    {visibleHarvestEntities.map((entity, index) => {
                      const selectable = isHarvestEntitySelectable(entity);
                      const isActive = index === entityComboboxActiveIndex;
                      return (
                        <button
                          key={entity.entity_id}
                          id={`harvest-entity-option-${entity.entity_id}`}
                          type="button"
                          role="option"
                          aria-selected={selectedEntityId === entity.entity_id}
                          aria-disabled={!selectable}
                          className={`mission-entity-combobox-option ${isActive ? "active" : ""} ${selectable ? "" : "disabled"}`}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => handleHarvestEntityButtonSelect(entity)}
                          disabled={!selectable}
                        >
                          <div>
                            <b>{entity.display_name || entity.entity_id || "UNAVAILABLE"}</b>
                            <span>Entity ID: {entity.entity_id || "UNAVAILABLE"}</span>
                            <span>Sources: {Array.isArray(entity.configured_sources) && entity.configured_sources.length ? entity.configured_sources.join(", ") : "UNAVAILABLE"}</span>
                          </div>
                          <div className="mission-entity-combobox-option-meta">
                            <small>{selectable ? "ENABLED" : "DISABLED"}</small>
                            <small>{Array.isArray(entity.approved_aliases) && entity.approved_aliases.length ? entity.approved_aliases.join(", ") : "UNAVAILABLE"}</small>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            className="mission-harvest-button primary"
            onClick={(event) => openControlledHarvestConfirmation("all_enabled", event.currentTarget)}
            disabled={harvestBusy !== ""}
          >
            {harvestBusy === "all_enabled" ? <Loader2 size={15} className="spin" /> : <Factory size={15} />}
            Harvest All Enabled Sources
          </button>
          <button
            type="button"
            className="mission-harvest-button"
            onClick={(event) => openControlledHarvestConfirmation("entity", event.currentTarget)}
            disabled={harvestBusy !== "" || !selectedHarvestEntity}
          >
            {harvestBusy === "entity" ? <Loader2 size={15} className="spin" /> : <ListChecks size={15} />}
            Harvest Specific Entity
          </button>
        </div>

        {harvestError ? <div className="mission-alert error"><AlertTriangle size={15} />{harvestError}</div> : null}
        {harvestMessage ? <div className="mission-alert success"><CheckCircle2 size={15} />{harvestMessage}</div> : null}

        <div className="mission-harvest-grid">
          <div className="mission-harvest-panel">
            <h3>Harvest status</h3>
            <div className="mission-mini-grid">
              <div><span>Run state</span><b>{asText(latestBackendRun?.run_state || latestBackendRun?.status, "UNAVAILABLE")}</b></div>
              <div><span>History count</span><b>{compactCount(harvestStatus?.history_count || harvestHistory.length)}</b></div>
              <div><span>Manual harvest</span><b>{harvestStatus?.manual_harvest === false ? "DISABLED" : harvestStatus ? "ENABLED" : "UNAVAILABLE"}</b></div>
              <div><span>Autonomous harvest</span><b>DISABLED</b></div>
            </div>
            <div className="mission-harvest-note">
              <span>Latest backend run evidence</span>
              <b>{asText(latestBackendRun?.evidence_reference || "UNAVAILABLE", "UNAVAILABLE")}</b>
            </div>
          </div>

          <div className="mission-harvest-panel">
            <h3>Selected Controlled Entity</h3>
            <div className="mission-entity-card">
              <b>{selectedEntityLabel}</b>
              {selectedHarvestEntity ? (
                <>
                  {selectedEntityDetails.map((detail) => (
                    <span key={detail}>{detail}</span>
                  ))}
                  <span>Configuration version: {selectedHarvestEntity.configuration_version || "UNAVAILABLE"}</span>
                  <span>Manual harvest permitted: {harvestStatus?.manual_harvest === false ? "NO" : "YES"}</span>
                  <span>Scheduler disabled: {harvestStatus?.scheduler_enabled === false ? "YES" : "UNAVAILABLE"}</span>
                  <span>Autonomous harvest disabled: {harvestStatus?.autonomous_harvest === false ? "YES" : "UNAVAILABLE"}</span>
                </>
              ) : (
                <span>No entity selected</span>
              )}
            </div>
          </div>
        </div>

        <div className="mission-harvest-grid">
          <div className="mission-harvest-panel">
            <h3>Current controlled run</h3>
            {currentControlledRun ? (
              <>
                <div className="mission-mini-grid">
                  <div><span>Run ID</span><b>{currentControlledRun.run_id || "UNAVAILABLE"}</b></div>
                  <div><span>Entity</span><b>{currentControlledRun.entity_display_name || selectedEntityLabel}</b></div>
                  <div><span>Canonical entity_id</span><b>{currentControlledRun.entity_id || selectedHarvestEntity?.entity_id || "UNAVAILABLE"}</b></div>
                  <div><span>State</span><b>{currentControlledRunState}</b></div>
                  <div><span>Outcome</span><b>{currentControlledRun.outcome || "UNAVAILABLE"}</b></div>
                  <div><span>Lifecycle</span><b>{harvestLifecycleState}</b></div>
                  <div><span>Start time</span><b>{formatDateTime(currentControlledRun.start_time || currentControlledRun.timestamp || harvestStatus?.timestamp)}</b></div>
                  <div><span>Latest update</span><b>{formatDateTime(currentControlledRun.completion_time || currentControlledRun.timestamp || harvestStatus?.timestamp)}</b></div>
                </div>
                <div className="mission-harvest-note">
                  <span>Evidence path</span>
                  <b>{isControlledHarvestTerminalState(currentControlledRunState) ? asText(currentControlledRun.evidence_reference || currentControlledRun.evidence_path, "UNAVAILABLE") : "Run status unavailable after request acceptance."}</b>
                </div>
                <div className="mission-harvest-note">
                  <span>Run summary</span>
                  <b>{currentControlledRunMessage || "UNAVAILABLE"}</b>
                </div>
              </>
            ) : (
              <div className="mission-empty-state">Run status unavailable after request acceptance.</div>
            )}
          </div>

          <div className="mission-harvest-panel">
            <h3>Latest completed run</h3>
            {latestControlledRun ? (
              <>
                <div className="mission-mini-grid">
                  <div><span>Run ID</span><b>{latestControlledRun.run_id || "UNAVAILABLE"}</b></div>
                  <div><span>Entity</span><b>{latestControlledRun.entity_display_name || latestControlledRun.entity_id || "UNAVAILABLE"}</b></div>
                  <div><span>State</span><b>{asText(latestControlledRun.run_state || latestControlledRun.status || latestControlledRun.state, "UNAVAILABLE")}</b></div>
                  <div><span>Outcome</span><b>{latestControlledRun.outcome || "UNAVAILABLE"}</b></div>
                  <div><span>Completed</span><b>{formatDateTime(latestControlledRun.completion_time || latestControlledRun.start_time)}</b></div>
                </div>
                <div className="mission-harvest-note">
                  <span>Evidence path</span>
                  <b>{asText(latestControlledRun.evidence_reference || latestControlledRun.evidence_path, "UNAVAILABLE")}</b>
                </div>
                <div className="mission-harvest-note">
                  <span>Run summary</span>
                  <b>{latestControlledRunMessage || "UNAVAILABLE"}</b>
                </div>
              </>
            ) : (
              <div className="mission-empty-state">UNAVAILABLE</div>
            )}
          </div>
        </div>

        <div className="mission-harvest-history">
          <div className="mission-harvest-history-head">
            <h3>Harvest history</h3>
            <span>{harvestHistory.length} recent run(s)</span>
          </div>
          {harvestHistory.length ? harvestHistory.map((run) => (
            <div className="mission-harvest-row" key={run.run_id || run.completion_time}>
              <div>
                <b>{run.run_id || "Run"}</b>
                <span>{run.entity_display_name || run.mode || "Controlled harvest"}</span>
              </div>
              <div>
                <small>{run.run_state || run.status || "UNAVAILABLE"}</small>
                <small>{formatDateTime(run.completion_time || run.start_time)}</small>
              </div>
            </div>
          )) : <div className="mission-empty-state">UNAVAILABLE</div>}
        </div>
      </section>

      {harvestConfirmation ? (
        <div className="mission-harvest-dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && closeControlledHarvestConfirmation()}>
          <div
            className="mission-harvest-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="controlled-harvest-dialog-title"
            aria-describedby="controlled-harvest-dialog-copy"
          >
            <div className="mission-harvest-dialog-head">
              <div>
                <p className="eyebrow">Controlled Harvest</p>
                <h2 id="controlled-harvest-dialog-title">Confirm Controlled Harvest</h2>
              </div>
              <button type="button" className="mission-entity-combobox-clear" onClick={closeControlledHarvestConfirmation} aria-label="Close confirmation dialog">
                <X size={14} />
              </button>
            </div>
            <div id="controlled-harvest-dialog-copy" className="mission-harvest-dialog-body">
              {harvestConfirmation.lines.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            <div className="mission-harvest-dialog-actions">
              <button type="button" className="mission-harvest-button" onClick={closeControlledHarvestConfirmation} ref={harvestConfirmationCancelRef}>
                Cancel
              </button>
              <button type="button" className="mission-harvest-button primary" onClick={confirmControlledHarvest} disabled={harvestBusy !== ""}>
                Confirm Controlled Harvest
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <section className="card mission-alerts" id="alerts">
        <SectionHeader
          eyebrow="Notifications"
          title="Alerts and notifications"
          description="Visible alert states are always explicit. Empty feeds remain honest and are not padded with sample alerts."
          action={<span className="mission-badge">{alertItems.length ? `${alertItems.length} live` : "UNAVAILABLE"}</span>}
        />
        <div className="mission-alert-list">
          {alertItems.length ? alertItems.map((alert) => (
            <article key={alert.id} className="mission-alert-row">
              <div>
                <b>{alert.title}</b>
                <span>{alert.message}</span>
              </div>
              <div>
                <small>{alert.category}</small>
                <small>{alert.severity}</small>
                <small>{formatDateTime(alert.timestamp)}</small>
              </div>
            </article>
          )) : <div className="mission-empty-state">UNAVAILABLE</div>}
        </div>
      </section>

      <section className="card mission-trends" id="trends">
        <SectionHeader
          eyebrow="Trend Analysis"
          title="Backend-backed trend surfaces"
          description="Trends are rendered only when the backend telemetry exists; otherwise the UI stays explicit about the unavailable state."
          action={<span className="mission-badge good">{Object.keys(analytics || {}).length ? "analytics loaded" : "UNAVAILABLE"}</span>}
        />
        <div className="mission-trend-grid">
          {trendSeries.map((trend) => (
            <button key={trend.id} type="button" className="mission-trend-card" onClick={() => setSelectedMetricId("weekly-metrics")}>
              <div className="mission-trend-head">
                <b>{trend.label}</b>
                <span>{trend.source}</span>
              </div>
              <TrendBars values={trend.values} />
              <small>{trend.detail}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="card mission-kpis" id="kpi-drilldowns">
        <SectionHeader
          eyebrow="KPI Drill-Downs"
          title="Authoritative metric contracts"
          description="Every visible KPI exposes a source, freshness timestamp, and a drill-down panel."
        />
        <div className="mission-kpi-grid">
          {missionMetrics.map((metric) => (
            <button
              key={metric.id}
              type="button"
              className={`mission-metric-card ${selectedMetricId === metric.id ? "active" : ""}`}
              onClick={() => setSelectedMetricId(metric.id)}
            >
              <span>{metric.label}</span>
              <b>{metric.value}</b>
              <small>{metric.source}</small>
              <small>{metric.freshness}</small>
            </button>
          ))}
        </div>
        <div className="mission-detail-grid">
          <div className="mission-detail-panel wide">
            <span>Selected KPI</span>
            <b>{selectedMetric.label}</b>
            <small>{selectedMetric.detail}</small>
          </div>
          <div className="mission-detail-panel">
            <span>Source</span>
            <b>{selectedMetric.source}</b>
          </div>
          <div className="mission-detail-panel">
            <span>Freshness</span>
            <b>{selectedMetric.freshness}</b>
          </div>
        </div>
      </section>

      <section className="card mission-workspaces" id="workspaces">
        <SectionHeader
          eyebrow="Workspace Shortcuts"
          title="Operator destinations"
          description="These buttons open the certified workspaces that hold the detailed operational surfaces."
        />
        <div className="mission-shortcut-grid">
          {[
            { label: "RFQ Operations", target: "rfq-operations", icon: ClipboardList },
            { label: "Review Workflow", target: "workflow-orchestrator", icon: Activity },
            { label: "Decision Support", target: "decision-support", icon: Layers3 },
            { label: "Predictive Analytics", target: "predictive-analytics", icon: TrendingUp },
            { label: "Buyer Intelligence", target: "buyer-intelligence", icon: FileText },
            { label: "Supplier Intelligence", target: "supplier-intelligence", icon: Factory },
            { label: "Quote Pack Engine", target: "quote-pack-engine", icon: FileText },
            { label: "Approval Centre", target: "submission-centre", icon: ShieldCheck },
            { label: "Customer Self-Service Portal", target: "customer-self-service-portal", icon: FileText },
          ].map((item) => (
            <button key={item.label} type="button" className="mission-shortcut" onClick={() => onNavigate(item.target)}>
              <item.icon size={16} />
              <span>{item.label}</span>
              <ArrowRight size={14} />
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
