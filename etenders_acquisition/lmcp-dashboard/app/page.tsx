"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";
const APP_ENV = process.env.NEXT_PUBLIC_APP_ENV || "development";

type Dashboard = {
  generated_at: string;
  rfq_status: {
    rfqs_created: number;
    dispatch_ready: number;
    rfqs_sent: number;
    rfqs_blocked_dry_run: number;
  };
  response_status: {
    mailbox_messages_checked: number;
    matched_supplier_responses: number;
    quotes_ingested: number;
  };
  commercial_position: {
    total_target_value: number;
    total_quoted_value: number;
    total_variance: number;
    total_variance_pct: number;
  };
  adjudication_status: {
    total_decisions: number;
    recommended_awards: number;
    recommended_negotiations: number;
    held_for_review: number;
  };
  action_status: {
    actions_ready: number;
    actions_sent: number;
    actions_blocked_dry_run: number;
  };
  supplier_decisions: Array<{
    supplier_name: string;
    decision: string;
    final_score: number;
    target_total: number;
    quoted_total: number;
    variance: number;
    variance_pct: number;
    reason: string;
  }>;
};

type HealthPayload = {
  status?: string;
  environment?: string;
  timestamp?: string;
};

type VisibilitySnapshot = {
  dryRun: Record<string, any> | null;
  lifecycleStatus: Record<string, any> | null;
  lifecycleTelemetry: Record<string, any> | null;
  recentRfqs: Array<Record<string, any>>;
  guardSummary: Record<string, any> | null;
  operationalHealth: Record<string, any> | null;
  reviewQueue: Record<string, any> | null;
  rehearsalLatest: Record<string, any> | null;
  rehearsalHistory: Array<Record<string, any>>;
  readinessLatest: Record<string, any> | null;
  readinessHistory: Array<Record<string, any>>;
  pilotEvidenceLatest: Record<string, any> | null;
  pilotEvidenceHistory: Array<Record<string, any>>;
  governanceReview: Record<string, any> | null;
  cadenceLatest: Record<string, any> | null;
  cadenceHistory: Array<Record<string, any>>;
  reviewBoardLatest: Record<string, any> | null;
  reviewBoardHistory: Array<Record<string, any>>;
  recurringCyclesLatest: Record<string, any> | null;
  recurringCyclesHistory: Array<Record<string, any>>;
  exceptionsLatest: Record<string, any> | null;
  exceptionsHistory: Array<Record<string, any>>;
  remediationLatest: Record<string, any> | null;
  remediationHistory: Array<Record<string, any>>;
  progressionLatest: Record<string, any> | null;
  progressionHistory: Array<Record<string, any>>;
  operationsSummaryLatest: Record<string, any> | null;
  operationsSummaryHistory: Array<Record<string, any>>;
  declarationLatest: Record<string, any> | null;
  declarationHistory: Array<Record<string, any>>;
  finalLatest: Record<string, any> | null;
  finalHistory: Array<Record<string, any>>;
  operationalPilotLatest: Record<string, any> | null;
  operationalPilotHistory: Array<Record<string, any>>;
  operationalIntelligenceLatest: Record<string, any> | null;
  operationalIntelligenceHistory: Array<Record<string, any>>;
  executiveCommandLatest: Record<string, any> | null;
  executiveCommandHistory: Array<Record<string, any>>;
  governanceIndexLatest: Record<string, any> | null;
  governanceIndexHistory: Array<Record<string, any>>;
  productionOperationalizationLatest: Record<string, any> | null;
  productionOperationalizationHistory: Array<Record<string, any>>;
  releaseGovernanceLatest: Record<string, any> | null;
  releaseGovernanceHistory: Array<Record<string, any>>;
  activationLatest: Record<string, any> | null;
  activationHistory: Array<Record<string, any>>;
  supervisionCommandLatest: Record<string, any> | null;
  supervisionCommandHistory: Array<Record<string, any>>;
  operationsAuditLatest: Record<string, any> | null;
  operationsAuditHistory: Array<Record<string, any>>;
  incidentGovernanceLatest: Record<string, any> | null;
  incidentGovernanceHistory: Array<Record<string, any>>;
  continuityGovernanceLatest: Record<string, any> | null;
  continuityGovernanceHistory: Array<Record<string, any>>;
  runtimeRemediationLatest: Record<string, any> | null;
  runtimeRemediationHistory: Array<Record<string, any>>;
  distributedOrchestrationLatest: Record<string, any> | null;
  distributedOrchestrationHistory: Array<Record<string, any>>;
  operatorSessionsLatest: Record<string, any> | null;
  operatorSessionsHistory: Array<Record<string, any>>;
  intakeLatest: Record<string, any> | null;
  intakeHistory: Array<Record<string, any>>;
  physicalSubmissionLatest: Record<string, any> | null;
  physicalSubmissionHistory: Array<Record<string, any>>;
  modalityLatest: Record<string, any> | null;
  modalityHistory: Array<Record<string, any>>;
  signatureLatest: Record<string, any> | null;
  signatureHistory: Array<Record<string, any>>;
  complianceLatest: Record<string, any> | null;
  complianceHistory: Array<Record<string, any>>;
  returnableLatest: Record<string, any> | null;
  returnableHistory: Array<Record<string, any>>;
  packagingLatest: Record<string, any> | null;
  packagingHistory: Array<Record<string, any>>;
  deadlineLatest: Record<string, any> | null;
  deadlineHistory: Array<Record<string, any>>;
  stabilityLatest: Record<string, any> | null;
  stabilityHistory: Array<Record<string, any>>;
  warnings: string[];
};

function money(value: number) {
  return `R${Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function buildErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Unknown error";
}

function getNumber(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function getString(value: unknown, fallback = "-") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function getBooleanBadge(value: unknown) {
  if (value === true) return { label: "Yes", tone: "ok" as const };
  if (value === false) return { label: "No", tone: "error" as const };
  return { label: "Unknown", tone: "neutral" as const };
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

function sumRecordValues(value: unknown): number {
  if (!value || typeof value !== "object") return 0;
  return Object.values(value as Record<string, unknown>).reduce<number>(
    (total, entry) => total + getNumber(entry, 0),
    0,
  );
}

export default function Home() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [visibilityError, setVisibilityError] = useState("");
  const [backendHealth, setBackendHealth] = useState<HealthPayload | null>(null);
  const [backendReachable, setBackendReachable] = useState(false);
  const [backendMessage, setBackendMessage] = useState("Checking backend");
  const [visibility, setVisibility] = useState<VisibilitySnapshot>({
    dryRun: null,
    lifecycleStatus: null,
    lifecycleTelemetry: null,
    recentRfqs: [],
    guardSummary: null,
    operationalHealth: null,
    reviewQueue: null,
    rehearsalLatest: null,
    rehearsalHistory: [],
    readinessLatest: null,
    readinessHistory: [],
    pilotEvidenceLatest: null,
    pilotEvidenceHistory: [],
    governanceReview: null,
    cadenceLatest: null,
    cadenceHistory: [],
    reviewBoardLatest: null,
    reviewBoardHistory: [],
    recurringCyclesLatest: null,
    recurringCyclesHistory: [],
    exceptionsLatest: null,
    exceptionsHistory: [],
    remediationLatest: null,
    remediationHistory: [],
    progressionLatest: null,
    progressionHistory: [],
    operationsSummaryLatest: null,
    operationsSummaryHistory: [],
    declarationLatest: null,
    declarationHistory: [],
    finalLatest: null,
    finalHistory: [],
    operationalPilotLatest: null,
    operationalPilotHistory: [],
    operationalIntelligenceLatest: null,
    operationalIntelligenceHistory: [],
    executiveCommandLatest: null,
    executiveCommandHistory: [],
    governanceIndexLatest: null,
    governanceIndexHistory: [],
    productionOperationalizationLatest: null,
    productionOperationalizationHistory: [],
    releaseGovernanceLatest: null,
    releaseGovernanceHistory: [],
    activationLatest: null,
    activationHistory: [],
    supervisionCommandLatest: null,
    supervisionCommandHistory: [],
    operationsAuditLatest: null,
    operationsAuditHistory: [],
    incidentGovernanceLatest: null,
    incidentGovernanceHistory: [],
    continuityGovernanceLatest: null,
    continuityGovernanceHistory: [],
    runtimeRemediationLatest: null,
    runtimeRemediationHistory: [],
    distributedOrchestrationLatest: null,
    distributedOrchestrationHistory: [],
    operatorSessionsLatest: null,
    operatorSessionsHistory: [],
    intakeLatest: null,
    intakeHistory: [],
    physicalSubmissionLatest: null,
    physicalSubmissionHistory: [],
    modalityLatest: null,
    modalityHistory: [],
    signatureLatest: null,
    signatureHistory: [],
    complianceLatest: null,
    complianceHistory: [],
    returnableLatest: null,
    returnableHistory: [],
    packagingLatest: null,
    packagingHistory: [],
    deadlineLatest: null,
    deadlineHistory: [],
    stabilityLatest: null,
    stabilityHistory: [],
    warnings: [],
  });

  async function loadDashboard() {
    const data = await fetchJson<Dashboard>("/dashboard");
    setDashboard(data);
  }

  async function loadBackendHealth() {
    try {
      const data = await fetchJson<HealthPayload>("/health");
      setBackendHealth(data);
      setBackendReachable(true);
      setBackendMessage(data.status || "reachable");
    } catch (err) {
      setBackendHealth(null);
      setBackendReachable(false);
      setBackendMessage(buildErrorMessage(err));
    }
  }

  async function loadVisibility() {
    const requests = [
      { key: "dryRun", path: "/rfq-lifecycle/upload-dry-run/status" },
      { key: "lifecycleStatus", path: "/rfq-lifecycle/status" },
      { key: "lifecycleTelemetry", path: "/rfq-lifecycle/telemetry" },
      { key: "recentRfqs", path: "/rfq-lifecycle/items?limit=8" },
      { key: "guardSummary", path: "/go-live-guards/summary?limit=8" },
      { key: "operationalHealth", path: "/telemetry/operational-health" },
      { key: "reviewQueue", path: "/telemetry/review-queue" },
      { key: "rehearsalLatest", path: "/rfq-lifecycle/rehearsals/latest" },
      { key: "rehearsalHistory", path: "/rfq-lifecycle/rehearsals/history?limit=8" },
      { key: "readinessLatest", path: "/rfq-lifecycle/rehearsals/readiness" },
      { key: "readinessHistory", path: "/rfq-lifecycle/rehearsals/readiness/history?limit=8" },
      { key: "pilotEvidenceLatest", path: "/rfq-lifecycle/pilot-evidence/latest" },
      { key: "pilotEvidenceHistory", path: "/rfq-lifecycle/pilot-evidence/history?limit=8" },
      { key: "governanceReview", path: "/rfq-lifecycle/pilot-evidence/governance-review" },
      { key: "cadenceLatest", path: "/rfq-lifecycle/cadence/latest" },
      { key: "cadenceHistory", path: "/rfq-lifecycle/cadence/history?limit=8" },
      { key: "reviewBoardLatest", path: "/rfq-lifecycle/review-board/latest" },
      { key: "reviewBoardHistory", path: "/rfq-lifecycle/review-board/history?limit=8" },
      { key: "recurringCyclesLatest", path: "/rfq-lifecycle/recurring-cycles/latest" },
      { key: "recurringCyclesHistory", path: "/rfq-lifecycle/recurring-cycles/history?limit=8" },
      { key: "exceptionsLatest", path: "/rfq-lifecycle/exceptions/latest" },
      { key: "exceptionsHistory", path: "/rfq-lifecycle/exceptions/history?limit=8" },
      { key: "remediationLatest", path: "/rfq-lifecycle/remediation/latest" },
      { key: "remediationHistory", path: "/rfq-lifecycle/remediation/history?limit=8" },
      { key: "progressionLatest", path: "/rfq-lifecycle/progression/latest" },
      { key: "progressionHistory", path: "/rfq-lifecycle/progression/history?limit=8" },
      { key: "operationsSummaryLatest", path: "/rfq-lifecycle/operations-summary/latest" },
      { key: "operationsSummaryHistory", path: "/rfq-lifecycle/operations-summary/history?limit=8" },
      { key: "declarationLatest", path: "/rfq-lifecycle/declaration/latest" },
      { key: "declarationHistory", path: "/rfq-lifecycle/declaration/history?limit=8" },
      { key: "finalLatest", path: "/rfq-lifecycle/final-readiness/latest" },
      { key: "finalHistory", path: "/rfq-lifecycle/final-readiness/history?limit=8" },
      { key: "operationalPilotLatest", path: "/rfq-lifecycle/operational-pilot/latest" },
      { key: "operationalPilotHistory", path: "/rfq-lifecycle/operational-pilot/history?limit=8" },
      { key: "operationalIntelligenceLatest", path: "/rfq-lifecycle/operational-intelligence/latest" },
      { key: "operationalIntelligenceHistory", path: "/rfq-lifecycle/operational-intelligence/history?limit=8" },
      { key: "executiveCommandLatest", path: "/rfq-lifecycle/executive-command/latest" },
      { key: "executiveCommandHistory", path: "/rfq-lifecycle/executive-command/history?limit=8" },
      { key: "governanceIndexLatest", path: "/rfq-lifecycle/governance-index/latest" },
      { key: "governanceIndexHistory", path: "/rfq-lifecycle/governance-index/history?limit=8" },
      { key: "productionOperationalizationLatest", path: "/rfq-lifecycle/production-governance/latest" },
      { key: "productionOperationalizationHistory", path: "/rfq-lifecycle/production-governance/history?limit=8" },
      { key: "releaseGovernanceLatest", path: "/rfq-lifecycle/release-governance/latest" },
      { key: "releaseGovernanceHistory", path: "/rfq-lifecycle/release-governance/history?limit=8" },
      { key: "activationLatest", path: "/rfq-lifecycle/activation-governance/latest" },
      { key: "activationHistory", path: "/rfq-lifecycle/activation-governance/history?limit=8" },
      { key: "supervisionCommandLatest", path: "/rfq-lifecycle/supervision-command/latest" },
      { key: "supervisionCommandHistory", path: "/rfq-lifecycle/supervision-command/history?limit=8" },
      { key: "operationsAuditLatest", path: "/rfq-lifecycle/operations-audit/latest" },
      { key: "operationsAuditHistory", path: "/rfq-lifecycle/operations-audit/history?limit=8" },
      { key: "incidentGovernanceLatest", path: "/rfq-lifecycle/incident-governance/latest" },
      { key: "incidentGovernanceHistory", path: "/rfq-lifecycle/incident-governance/history?limit=8" },
      { key: "continuityGovernanceLatest", path: "/rfq-lifecycle/continuity-governance/latest" },
      { key: "continuityGovernanceHistory", path: "/rfq-lifecycle/continuity-governance/history?limit=8" },
      { key: "runtimeRemediationLatest", path: "/rfq-lifecycle/runtime-remediation/latest" },
      { key: "runtimeRemediationHistory", path: "/rfq-lifecycle/runtime-remediation/history?limit=8" },
      { key: "distributedOrchestrationLatest", path: "/rfq-lifecycle/distributed-orchestration/latest" },
      { key: "distributedOrchestrationHistory", path: "/rfq-lifecycle/distributed-orchestration/history?limit=8" },
      { key: "operatorSessionsLatest", path: "/rfq-lifecycle/operator-sessions/latest" },
      { key: "operatorSessionsHistory", path: "/rfq-lifecycle/operator-sessions/history?limit=8" },
      { key: "intakeLatest", path: "/rfq-lifecycle/intake/latest" },
      { key: "intakeHistory", path: "/rfq-lifecycle/intake/history?limit=8" },
      { key: "physicalSubmissionLatest", path: "/rfq-lifecycle/physical-submission/latest" },
      { key: "physicalSubmissionHistory", path: "/rfq-lifecycle/physical-submission/history?limit=8" },
      { key: "modalityLatest", path: "/rfq-lifecycle/submission-modality/latest" },
      { key: "modalityHistory", path: "/rfq-lifecycle/submission-modality/history?limit=8" },
      { key: "signatureLatest", path: "/rfq-lifecycle/signature-governance/latest" },
      { key: "signatureHistory", path: "/rfq-lifecycle/signature-governance/history?limit=8" },
      { key: "complianceLatest", path: "/rfq-lifecycle/compliance-governance/latest" },
      { key: "complianceHistory", path: "/rfq-lifecycle/compliance-governance/history?limit=8" },
      { key: "returnableLatest", path: "/rfq-lifecycle/returnable-governance/latest" },
      { key: "returnableHistory", path: "/rfq-lifecycle/returnable-governance/history?limit=8" },
      { key: "packagingLatest", path: "/rfq-lifecycle/packaging-governance/latest" },
      { key: "packagingHistory", path: "/rfq-lifecycle/packaging-governance/history?limit=8" },
      { key: "deadlineLatest", path: "/rfq-lifecycle/deadline-governance/latest" },
      { key: "deadlineHistory", path: "/rfq-lifecycle/deadline-governance/history?limit=8" },
      { key: "stabilityLatest", path: "/rfq-lifecycle/stability/latest" },
      { key: "stabilityHistory", path: "/rfq-lifecycle/stability/history?limit=8" },
    ] as const;

    const settled = await Promise.allSettled(
      requests.map(async (request) => ({ key: request.key, data: await fetchJson<Record<string, any>>(request.path) })),
    );

    const next: VisibilitySnapshot = {
      dryRun: null,
      lifecycleStatus: null,
      lifecycleTelemetry: null,
      recentRfqs: [],
      guardSummary: null,
      operationalHealth: null,
      reviewQueue: null,
      rehearsalLatest: null,
      rehearsalHistory: [],
      readinessLatest: null,
      readinessHistory: [],
      pilotEvidenceLatest: null,
      pilotEvidenceHistory: [],
      governanceReview: null,
      cadenceLatest: null,
      cadenceHistory: [],
      reviewBoardLatest: null,
      reviewBoardHistory: [],
      recurringCyclesLatest: null,
      recurringCyclesHistory: [],
      exceptionsLatest: null,
      exceptionsHistory: [],
      remediationLatest: null,
      remediationHistory: [],
      progressionLatest: null,
      progressionHistory: [],
      operationsSummaryLatest: null,
      operationsSummaryHistory: [],
      declarationLatest: null,
      declarationHistory: [],
      finalLatest: null,
      finalHistory: [],
      operationalPilotLatest: null,
      operationalPilotHistory: [],
      operationalIntelligenceLatest: null,
      operationalIntelligenceHistory: [],
      executiveCommandLatest: null,
      executiveCommandHistory: [],
      governanceIndexLatest: null,
      governanceIndexHistory: [],
      productionOperationalizationLatest: null,
      productionOperationalizationHistory: [],
      releaseGovernanceLatest: null,
      releaseGovernanceHistory: [],
      activationLatest: null,
      activationHistory: [],
      supervisionCommandLatest: null,
      supervisionCommandHistory: [],
      operationsAuditLatest: null,
      operationsAuditHistory: [],
      incidentGovernanceLatest: null,
      incidentGovernanceHistory: [],
      continuityGovernanceLatest: null,
      continuityGovernanceHistory: [],
      runtimeRemediationLatest: null,
      runtimeRemediationHistory: [],
      distributedOrchestrationLatest: null,
      distributedOrchestrationHistory: [],
      operatorSessionsLatest: null,
      operatorSessionsHistory: [],
      intakeLatest: null,
      intakeHistory: [],
      physicalSubmissionLatest: null,
      physicalSubmissionHistory: [],
      modalityLatest: null,
      modalityHistory: [],
      signatureLatest: null,
      signatureHistory: [],
      complianceLatest: null,
      complianceHistory: [],
      returnableLatest: null,
      returnableHistory: [],
      packagingLatest: null,
      packagingHistory: [],
      deadlineLatest: null,
      deadlineHistory: [],
      stabilityLatest: null,
      stabilityHistory: [],
      warnings: [],
    };

    const warnings: string[] = [];
    for (const result of settled) {
      if (result.status === "rejected") {
        warnings.push(buildErrorMessage(result.reason));
        continue;
      }
      const { key, data } = result.value;
      if (key === "recentRfqs") {
        const items = data.items;
        next.recentRfqs = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "dryRun") {
        next.dryRun = data;
      } else if (key === "lifecycleStatus") {
        next.lifecycleStatus = data;
      } else if (key === "lifecycleTelemetry") {
        next.lifecycleTelemetry = data;
      } else if (key === "guardSummary") {
        next.guardSummary = data;
      } else if (key === "operationalHealth") {
        next.operationalHealth = data;
      } else if (key === "reviewQueue") {
        next.reviewQueue = data;
      } else if (key === "rehearsalLatest") {
        next.rehearsalLatest = data;
      } else if (key === "rehearsalHistory") {
        const runs = data.runs;
        next.rehearsalHistory = Array.isArray(runs) ? runs.slice(0, 8) : [];
      } else if (key === "readinessLatest") {
        next.readinessLatest = data;
      } else if (key === "readinessHistory") {
        const runs = data.runs;
        next.readinessHistory = Array.isArray(runs) ? runs.slice(0, 8) : [];
      } else if (key === "pilotEvidenceLatest") {
        next.pilotEvidenceLatest = data;
      } else if (key === "pilotEvidenceHistory") {
        const packs = data.packs;
        next.pilotEvidenceHistory = Array.isArray(packs) ? packs.slice(0, 8) : [];
      } else if (key === "governanceReview") {
        next.governanceReview = data;
      } else if (key === "cadenceLatest") {
        next.cadenceLatest = data;
      } else if (key === "cadenceHistory") {
        const checkpoints = data.checkpoints;
        next.cadenceHistory = Array.isArray(checkpoints) ? checkpoints.slice(0, 8) : [];
      } else if (key === "reviewBoardLatest") {
        next.reviewBoardLatest = data;
      } else if (key === "reviewBoardHistory") {
        const sessions = data.review_board_history;
        next.reviewBoardHistory = Array.isArray(sessions) ? sessions.slice(0, 8) : [];
      } else if (key === "recurringCyclesLatest") {
        next.recurringCyclesLatest = data;
      } else if (key === "recurringCyclesHistory") {
        const cycles = data.cycle_history;
        next.recurringCyclesHistory = Array.isArray(cycles) ? cycles.slice(0, 8) : [];
      } else if (key === "exceptionsLatest") {
        next.exceptionsLatest = data;
      } else if (key === "exceptionsHistory") {
        const exceptions = data.classification_history;
        next.exceptionsHistory = Array.isArray(exceptions) ? exceptions.slice(0, 8) : [];
      } else if (key === "remediationLatest") {
        next.remediationLatest = data;
      } else if (key === "remediationHistory") {
        const actions = data.remediation_actions;
        next.remediationHistory = Array.isArray(actions) ? actions.slice(0, 8) : [];
      } else if (key === "progressionLatest") {
        next.progressionLatest = data;
      } else if (key === "progressionHistory") {
        const decisions = data.progression_decision_history;
        next.progressionHistory = Array.isArray(decisions) ? decisions.slice(0, 8) : [];
      } else if (key === "operationsSummaryLatest") {
        next.operationsSummaryLatest = data;
      } else if (key === "operationsSummaryHistory") {
        const items = data.institutional_operational_summary_history;
        next.operationsSummaryHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "declarationLatest") {
        next.declarationLatest = data;
      } else if (key === "declarationHistory") {
        const items = data.declaration_history;
        next.declarationHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "finalLatest") {
        next.finalLatest = data;
      } else if (key === "finalHistory") {
        const items = data.final_readiness_history;
        next.finalHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "operationalPilotLatest") {
        next.operationalPilotLatest = data;
      } else if (key === "operationalPilotHistory") {
        const items = data.execution_governance_history;
        next.operationalPilotHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "operationalIntelligenceLatest") {
        next.operationalIntelligenceLatest = data;
      } else if (key === "operationalIntelligenceHistory") {
        const items = data.operational_intelligence_history;
        next.operationalIntelligenceHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "executiveCommandLatest") {
        next.executiveCommandLatest = data;
      } else if (key === "executiveCommandHistory") {
        const items = data.executive_intelligence_history;
        next.executiveCommandHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "governanceIndexLatest") {
        next.governanceIndexLatest = data;
      } else if (key === "governanceIndexHistory") {
        const items = data.executive_governance_index_history;
        next.governanceIndexHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "productionOperationalizationLatest") {
        next.productionOperationalizationLatest = data;
      } else if (key === "productionOperationalizationHistory") {
        const items = data.production_governance_history;
        next.productionOperationalizationHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "releaseGovernanceLatest") {
        next.releaseGovernanceLatest = data;
      } else if (key === "releaseGovernanceHistory") {
        const items = data.release_governance_history;
        next.releaseGovernanceHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "activationLatest") {
        next.activationLatest = data;
      } else if (key === "activationHistory") {
        const items = data.activation_governance_history;
        next.activationHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "supervisionCommandLatest") {
        next.supervisionCommandLatest = data;
      } else if (key === "supervisionCommandHistory") {
        const items = data.supervision_governance_history;
        next.supervisionCommandHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "operationsAuditLatest") {
        next.operationsAuditLatest = data;
      } else if (key === "operationsAuditHistory") {
        const items = data.operations_audit_history;
        next.operationsAuditHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "incidentGovernanceLatest") {
        next.incidentGovernanceLatest = data;
      } else if (key === "incidentGovernanceHistory") {
        const items = data.incident_governance_history;
        next.incidentGovernanceHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "continuityGovernanceLatest") {
        next.continuityGovernanceLatest = data;
      } else if (key === "continuityGovernanceHistory") {
        const items = data.continuity_governance_history;
        next.continuityGovernanceHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "runtimeRemediationLatest") {
        next.runtimeRemediationLatest = data;
      } else if (key === "runtimeRemediationHistory") {
        const items = data.runtime_remediation_history;
        next.runtimeRemediationHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "distributedOrchestrationLatest") {
        next.distributedOrchestrationLatest = data;
      } else if (key === "distributedOrchestrationHistory") {
        const items = data.distributed_orchestration_history;
        next.distributedOrchestrationHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "operatorSessionsLatest") {
        next.operatorSessionsLatest = data;
      } else if (key === "operatorSessionsHistory") {
        const items = data.operator_session_history;
        next.operatorSessionsHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "intakeLatest") {
        next.intakeLatest = data;
      } else if (key === "intakeHistory") {
        const items = data.intake_decision_history;
        next.intakeHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "physicalSubmissionLatest") {
        next.physicalSubmissionLatest = data;
      } else if (key === "physicalSubmissionHistory") {
        const items = data.physical_submission_decision_history;
        next.physicalSubmissionHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "modalityLatest") {
        next.modalityLatest = data;
      } else if (key === "modalityHistory") {
        const items = data.modality_decision_history;
        next.modalityHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "signatureLatest") {
        next.signatureLatest = data;
      } else if (key === "signatureHistory") {
        const items = data.signature_governance_decision_history;
        next.signatureHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "complianceLatest") {
        next.complianceLatest = data;
      } else if (key === "complianceHistory") {
        const items = data.compliance_governance_decision_history;
        next.complianceHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "returnableLatest") {
        next.returnableLatest = data;
      } else if (key === "returnableHistory") {
        const items = data.returnable_governance_history;
        next.returnableHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "packagingLatest") {
        next.packagingLatest = data;
      } else if (key === "packagingHistory") {
        const items = data.packaging_governance_history;
        next.packagingHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "deadlineLatest") {
        next.deadlineLatest = data;
      } else if (key === "deadlineHistory") {
        const items = data.deadline_governance_history;
        next.deadlineHistory = Array.isArray(items) ? items.slice(0, 8) : [];
      } else if (key === "stabilityLatest") {
        next.stabilityLatest = data;
      } else if (key === "stabilityHistory") {
        const cycles = data.cycles;
        next.stabilityHistory = Array.isArray(cycles) ? cycles.slice(0, 8) : [];
      }
    }

    next.warnings = warnings;
    setVisibility(next);
    setVisibilityError(
      warnings.length ? `Some operational visibility endpoints were unavailable: ${warnings.join("; ")}` : "",
    );
  }

  async function loadAll() {
    await Promise.all([loadDashboard(), loadBackendHealth(), loadVisibility()]);
  }

  async function refreshAll() {
    setRefreshing(true);
    try {
      await loadAll();
    } catch (err) {
      setError(buildErrorMessage(err));
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshAll();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        Loading LMCP AutoQuote dashboard...
      </main>
    );
  }

  const cp = dashboard?.commercial_position;
  const lifecycleCounts = visibility.lifecycleStatus?.queue_by_lifecycle_state || {};
  const lifecycleTelemetry = visibility.lifecycleTelemetry || {};
  const workerHeartbeat = lifecycleTelemetry.worker_heartbeat || {};
  const queueBacklog = lifecycleTelemetry.queue_backlog || {};
  const guardSummary = visibility.guardSummary?.summary || {};
  const dryRunStatus = visibility.dryRun || {};
  const operationalHealth = visibility.operationalHealth || {};
  const reviewQueue = visibility.reviewQueue || {};
  const taskTimeouts = lifecycleTelemetry.task_timeout_detection || {};
  const autoRecoveryHooks = lifecycleTelemetry.auto_recovery_hooks || {};
  const retryCount = getNumber(visibility.lifecycleStatus?.throughput?.retried, 0);
  const queuedForRetry = getNumber(lifecycleCounts.READY_FOR_RETRY, 0);
  const deadQueues = Array.isArray(queueBacklog.isolated_dead_queues) ? queueBacklog.isolated_dead_queues : [];
  const reviewBoardWarnings = Array.isArray(visibility.reviewBoardLatest?.warnings) ? visibility.reviewBoardLatest.warnings : [];
  const recurringCycleWarnings = Array.isArray(visibility.recurringCyclesLatest?.warnings) ? visibility.recurringCyclesLatest.warnings : [];
  const exceptionWarnings = Array.isArray(visibility.exceptionsLatest?.warnings) ? visibility.exceptionsLatest.warnings : [];
  const progressionLatest = visibility.progressionLatest || {};
  const progressionHistory = Array.isArray(visibility.progressionHistory) ? visibility.progressionHistory : [];
  const progressionWarnings = Array.isArray(progressionLatest.warnings) ? progressionLatest.warnings : [];
  const operationsSummaryLatest = visibility.operationsSummaryLatest || {};
  const operationsSummaryHistory = Array.isArray(visibility.operationsSummaryHistory) ? visibility.operationsSummaryHistory : [];
  const operationsSummaryWarnings = Array.isArray(operationsSummaryLatest.warnings) ? operationsSummaryLatest.warnings : [];
  const declarationLatest = visibility.declarationLatest || {};
  const declarationHistory = Array.isArray(visibility.declarationHistory) ? visibility.declarationHistory : [];
  const declarationWarnings = Array.isArray(declarationLatest.warnings) ? declarationLatest.warnings : [];
  const finalLatest = visibility.finalLatest || {};
  const finalHistory = Array.isArray(visibility.finalHistory) ? visibility.finalHistory : [];
  const finalWarnings = Array.isArray(finalLatest.warnings) ? finalLatest.warnings : [];
  const operationalPilotLatest = visibility.operationalPilotLatest || {};
  const operationalPilotHistory = Array.isArray(visibility.operationalPilotHistory) ? visibility.operationalPilotHistory : [];
  const operationalPilotWarnings = Array.isArray(operationalPilotLatest.warnings) ? operationalPilotLatest.warnings : [];
  const operationalIntelligenceLatest = visibility.operationalIntelligenceLatest || {};
  const operationalIntelligenceHistory = Array.isArray(visibility.operationalIntelligenceHistory) ? visibility.operationalIntelligenceHistory : [];
  const operationalIntelligenceWarnings = Array.isArray(operationalIntelligenceLatest.warnings) ? operationalIntelligenceLatest.warnings : [];
  const executiveCommandLatest = visibility.executiveCommandLatest || {};
  const executiveCommandHistory = Array.isArray(visibility.executiveCommandHistory) ? visibility.executiveCommandHistory : [];
  const executiveCommandWarnings = Array.isArray(executiveCommandLatest.warnings) ? executiveCommandLatest.warnings : [];
  const executiveCommandScore = getNumber(executiveCommandLatest.executive_governance_score, 0);
  const executiveCommandStatus = getString(executiveCommandLatest.executive_governance_status, "watch");
  const executiveCommandGrade = getString(executiveCommandLatest.executive_governance_grade, "blocked");
  const executiveCommandForecast = executiveCommandLatest.latest_executive_intelligence || {};
  const executiveCommandHistorySummary = executiveCommandLatest.executive_intelligence_history_summary || {};
  const executiveRiskIndicators = executiveCommandLatest.institutional_risk_indicators || {};
  const executiveSaturationIndicators = executiveCommandLatest.procurement_saturation_indicators || {};
  const executiveReadinessIndicators = executiveCommandLatest.strategic_readiness_indicators || {};
  const executiveForecastingIndicators = executiveCommandLatest.operational_forecasting_indicators || {};
  const governanceIndexLatest = visibility.governanceIndexLatest || {};
  const governanceIndexHistory = Array.isArray(visibility.governanceIndexHistory) ? visibility.governanceIndexHistory : [];
  const governanceIndexWarnings = Array.isArray(governanceIndexLatest.warnings) ? governanceIndexLatest.warnings : [];
  const governanceIndexStatus = getString(governanceIndexLatest.executive_governance_index_status, "watch");
  const governanceIndexAuthority = getString(governanceIndexLatest.executive_governance_index_authority, "WATCH");
  const governanceIndexScore = getNumber(governanceIndexLatest.executive_governance_index_score, 0);
  const governanceIndexGrade = getString(governanceIndexLatest.executive_governance_index_grade, "blocked");
  const governanceIndexActivation = governanceIndexLatest.activation_readiness || {};
  const governanceIndexSupervision = governanceIndexLatest.supervision_readiness || {};
  const governanceIndexAudit = governanceIndexLatest.audit_completeness || {};
  const governanceIndexIncident = governanceIndexLatest.incident_severity || {};
  const governanceIndexContinuity = governanceIndexLatest.continuity_readiness || {};
  const governanceIndexRelease = governanceIndexLatest.release_authority || {};
  const governanceIndexIntelligence = governanceIndexLatest.operational_intelligence || {};
  const governanceIndexInstitutional = governanceIndexLatest.institutional_rollout_readiness || {};
  const governanceIndexDegradation = governanceIndexLatest.governance_degradation_indicators || {};
  const governanceIndexEscalation = governanceIndexLatest.executive_escalation_indicators || {};
  const governanceIndexHistorySummary = governanceIndexLatest.executive_governance_index_history_summary || {};
  const productionOperationalizationLatest = visibility.productionOperationalizationLatest || {};
  const productionOperationalizationHistory = Array.isArray(visibility.productionOperationalizationHistory) ? visibility.productionOperationalizationHistory : [];
  const productionOperationalizationWarnings = Array.isArray(productionOperationalizationLatest.warnings) ? productionOperationalizationLatest.warnings : [];
  const productionReadinessScore = getNumber(productionOperationalizationLatest.production_readiness_score, 0);
  const productionReadinessStatus = getString(productionOperationalizationLatest.production_readiness_status, "watch");
  const productionReadinessGrade = getString(productionOperationalizationLatest.production_readiness_grade, "blocked");
  const productionSegmentation = productionOperationalizationLatest.production_runtime_segmentation || {};
  const productionAccess = productionOperationalizationLatest.operator_access_governance || {};
  const productionObservability = productionOperationalizationLatest.production_observability_governance || {};
  const productionBackup = productionOperationalizationLatest.backup_restore_governance || {};
  const productionDisasterRecovery = productionOperationalizationLatest.disaster_recovery_governance || {};
  const productionHighAvailability = productionOperationalizationLatest.high_availability_governance || {};
  const productionAuditRetention = productionOperationalizationLatest.audit_retention_governance || {};
  const productionDeployment = productionOperationalizationLatest.deployment_readiness_governance || {};
  const productionRiskIndicators = productionOperationalizationLatest.deployment_risk_indicators || {};
  const productionAccessRiskIndicators = productionOperationalizationLatest.operator_access_risk_indicators || {};
  const productionHAIndicators = productionOperationalizationLatest.ha_readiness_indicators || {};
  const productionRecoveryIndicators = productionOperationalizationLatest.recovery_readiness_indicators || {};
  const distributedOrchestrationLatest = visibility.distributedOrchestrationLatest || {};
  const distributedOrchestrationHistory = Array.isArray(visibility.distributedOrchestrationHistory) ? visibility.distributedOrchestrationHistory : [];
  const distributedOrchestrationWarnings = Array.isArray(distributedOrchestrationLatest.warnings) ? distributedOrchestrationLatest.warnings : [];
  const distributedOrchestrationStatus = getString(distributedOrchestrationLatest.distributed_orchestration_status, "watch");
  const distributedOrchestrationAuthority = getString(distributedOrchestrationLatest.distributed_orchestration_authority, "WATCH");
  const distributedOrchestrationScore = getNumber(distributedOrchestrationLatest.distributed_orchestration_score, 0);
  const distributedOrchestrationGrade = getString(distributedOrchestrationLatest.distributed_orchestration_grade, "blocked");
  const distributedOrchestrationRecoveryState = getString(distributedOrchestrationLatest.recovery_state, "unresolved-blocked");
  const distributedOrchestrationBlockers = Array.isArray(distributedOrchestrationLatest.unresolved_blockers) ? distributedOrchestrationLatest.unresolved_blockers : [];
  const distributedOrchestrationRationale = distributedOrchestrationLatest.recovery_rationale || {};
  const distributedOrchestrationBlockerSources = Array.isArray(distributedOrchestrationLatest.blocker_sources) ? distributedOrchestrationLatest.blocker_sources : [];
  const distributedOrchestrationQueue = distributedOrchestrationLatest.queue_partition_readiness || {};
  const distributedOrchestrationWorker = distributedOrchestrationLatest.worker_shard_readiness || {};
  const distributedOrchestrationAutoscaling = distributedOrchestrationLatest.autoscaling_readiness || {};
  const distributedOrchestrationFailover = distributedOrchestrationLatest.failover_orchestration_readiness || {};
  const distributedOrchestrationSupervision = distributedOrchestrationLatest.distributed_supervision_coverage || {};
  const distributedOrchestrationWorkload = distributedOrchestrationLatest.workload_saturation_indicators || {};
  const distributedOrchestrationDegradation = distributedOrchestrationLatest.orchestration_degradation_indicators || {};
  const distributedOrchestrationRecoveryHistory = Array.isArray(distributedOrchestrationLatest.recovery_state_history) ? distributedOrchestrationLatest.recovery_state_history : [];
  const releaseGovernanceLatest = visibility.releaseGovernanceLatest || {};
  const releaseGovernanceHistory = Array.isArray(visibility.releaseGovernanceHistory) ? visibility.releaseGovernanceHistory : [];
  const releaseGovernanceWarnings = Array.isArray(releaseGovernanceLatest.warnings) ? releaseGovernanceLatest.warnings : [];
  const releaseGovernanceStatus = getString(releaseGovernanceLatest.release_governance_status, "watch");
  const releaseGovernanceAuthority = getString(releaseGovernanceLatest.release_governance_authority, "WATCH");
  const releaseGovernanceScore = getNumber(releaseGovernanceLatest.release_governance_score, 0);
  const releaseGovernanceGrade = getString(releaseGovernanceLatest.release_governance_grade, "blocked");
  const releaseLatest = releaseGovernanceLatest.latest_release_governance || {};
  const releaseDeploymentRisk = releaseGovernanceLatest.deployment_risk_indicators || {};
  const releaseOperational = releaseGovernanceLatest.operational_release_indicators || {};
  const releaseReadiness = releaseGovernanceLatest.release_readiness_indicators || {};
  const releaseAuthorityIndicators = releaseGovernanceLatest.release_authority_indicators || {};
  const releaseHistorySummary = releaseGovernanceLatest.release_governance_history_summary || {};
  const releaseSummaryComponents = releaseGovernanceLatest.summary_components || {};
  const activationLatest = visibility.activationLatest || {};
  const activationHistory = Array.isArray(visibility.activationHistory) ? visibility.activationHistory : [];
  const activationWarnings = Array.isArray(activationLatest.warnings) ? activationLatest.warnings : [];
  const activationStatus = getString(activationLatest.activation_governance_status, "watch");
  const activationAuthority = getString(activationLatest.activation_governance_authority, "WATCH");
  const activationScore = getNumber(activationLatest.activation_governance_score, 0);
  const activationGrade = getString(activationLatest.activation_governance_grade, "blocked");
  const activationLatestRollout = activationLatest.latest_rollout_validation || {};
  const activationLatestRelease = activationLatest.latest_release_certification || {};
  const activationHistorySummary = activationLatest.activation_governance_history_summary || {};
  const activationTenant = activationLatest.tenant_activation_readiness || {};
  const activationOperator = activationLatest.operator_certification_readiness || {};
  const activationSupervision = activationLatest.supervision_assignment_readiness || {};
  const activationSegmentation = activationLatest.staged_rollout_segmentation || {};
  const activationThroughput = activationLatest.throughput_expansion_readiness || {};
  const activationFreeze = activationLatest.rollout_freeze_indicators || {};
  const activationEscalation = activationLatest.escalation_readiness || {};
  const activationSaturation = activationLatest.operator_saturation_indicators || {};
  const activationCoverage = activationLatest.supervision_coverage_indicators || {};
  const supervisionCommandLatest = visibility.supervisionCommandLatest || {};
  const supervisionCommandHistory = Array.isArray(visibility.supervisionCommandHistory) ? visibility.supervisionCommandHistory : [];
  const supervisionCommandWarnings = Array.isArray(supervisionCommandLatest.warnings) ? supervisionCommandLatest.warnings : [];
  const supervisionCommandStatus = getString(supervisionCommandLatest.supervision_command_status, "watch");
  const supervisionCommandAuthority = getString(supervisionCommandLatest.supervision_command_authority, "WATCH");
  const supervisionCommandScore = getNumber(supervisionCommandLatest.supervision_command_score, 0);
  const supervisionCommandGrade = getString(supervisionCommandLatest.supervision_command_grade, "blocked");
  const supervisionCommandOperators = Array.isArray(supervisionCommandLatest.active_supervised_operators) ? supervisionCommandLatest.active_supervised_operators : [];
  const supervisionCommandCoverage = supervisionCommandLatest.supervision_coverage || {};
  const supervisionCommandRfqOversight = supervisionCommandLatest.active_rfq_oversight || {};
  const supervisionCommandEscalation = supervisionCommandLatest.escalation_command_visibility || {};
  const supervisionCommandSaturation = supervisionCommandLatest.supervision_saturation || {};
  const supervisionCommandLapse = supervisionCommandLatest.supervision_lapse_indicators || {};
  const supervisionCommandWorkload = supervisionCommandLatest.operational_workload_visibility || {};
  const supervisionCommandSla = supervisionCommandLatest.supervision_sla_visibility || {};
  const supervisionCommandFreeze = supervisionCommandLatest.operational_freeze_indicators || {};
  const supervisionCommandHistorySummary = supervisionCommandLatest.supervision_governance_history_summary || {};
  const operationsAuditLatest = visibility.operationsAuditLatest || {};
  const operationsAuditHistory = Array.isArray(visibility.operationsAuditHistory) ? visibility.operationsAuditHistory : [];
  const operationsAuditWarnings = Array.isArray(operationsAuditLatest.warnings) ? operationsAuditLatest.warnings : [];
  const operationsAuditStatus = getString(operationsAuditLatest.operations_audit_status, "watch");
  const operationsAuditAuthority = getString(operationsAuditLatest.operations_audit_authority, "WATCH");
  const operationsAuditScore = getNumber(operationsAuditLatest.operations_audit_score, 0);
  const operationsAuditGrade = getString(operationsAuditLatest.operations_audit_grade, "blocked");
  const operationsAuditRetention = operationsAuditLatest.audit_retention_indicators || {};
  const operationsAuditCompleteness = operationsAuditLatest.audit_completeness_indicators || {};
  const operationsAuditRolloutActions = Array.isArray(operationsAuditLatest.supervised_rollout_actions) ? operationsAuditLatest.supervised_rollout_actions : [];
  const operationsAuditEscalations = Array.isArray(operationsAuditLatest.escalation_acknowledgements) ? operationsAuditLatest.escalation_acknowledgements : [];
  const operationsAuditFreezeHistory = Array.isArray(operationsAuditLatest.operational_freeze_history) ? operationsAuditLatest.operational_freeze_history : [];
  const operationsAuditOverrideHistory = Array.isArray(operationsAuditLatest.governance_override_history) ? operationsAuditLatest.governance_override_history : [];
  const operationsAuditOperatorAckHistory = Array.isArray(operationsAuditLatest.operator_acknowledgement_history) ? operationsAuditLatest.operator_acknowledgement_history : [];
  const operationsAuditSupervisionApprovalHistory = Array.isArray(operationsAuditLatest.supervision_approval_history) ? operationsAuditLatest.supervision_approval_history : [];
  const operationsAuditReleaseDecisionHistory = Array.isArray(operationsAuditLatest.release_decision_history) ? operationsAuditLatest.release_decision_history : [];
  const operationsAuditHistorySummary = operationsAuditLatest.operations_audit_history_summary || {};
  const operationsAuditLatestRollout = operationsAuditLatest.latest_rollout_validation || {};
  const operationsAuditLatestRelease = operationsAuditLatest.latest_release_certification || {};
  const incidentGovernanceLatest = visibility.incidentGovernanceLatest || {};
  const incidentGovernanceHistory = Array.isArray(visibility.incidentGovernanceHistory) ? visibility.incidentGovernanceHistory : [];
  const incidentGovernanceWarnings = Array.isArray(incidentGovernanceLatest.warnings) ? incidentGovernanceLatest.warnings : [];
  const incidentGovernanceStatus = getString(incidentGovernanceLatest.incident_governance_status, "watch");
  const incidentGovernanceAuthority = getString(incidentGovernanceLatest.incident_governance_authority, "WATCH");
  const incidentGovernanceScore = getNumber(incidentGovernanceLatest.incident_governance_score, 0);
  const incidentGovernanceGrade = getString(incidentGovernanceLatest.incident_governance_grade, "blocked");
  const incidentGovernanceHistorySummary = incidentGovernanceLatest.incident_governance_history_summary || {};
  const incidentGovernanceRetention = incidentGovernanceLatest.audit_retention_indicators || {};
  const incidentGovernanceCompleteness = incidentGovernanceLatest.audit_completeness_indicators || {};
  const incidentGovernanceIncidents = Array.isArray(incidentGovernanceLatest.operational_incidents) ? incidentGovernanceLatest.operational_incidents : [];
  const incidentGovernanceSupervisionFailures = Array.isArray(incidentGovernanceLatest.supervision_failures) ? incidentGovernanceLatest.supervision_failures : [];
  const incidentGovernanceEscalationFailures = Array.isArray(incidentGovernanceLatest.escalation_failures) ? incidentGovernanceLatest.escalation_failures : [];
  const incidentGovernanceRolloutAnomalies = Array.isArray(incidentGovernanceLatest.rollout_anomalies) ? incidentGovernanceLatest.rollout_anomalies : [];
  const incidentGovernanceBreaches = Array.isArray(incidentGovernanceLatest.governance_breach_indicators) ? incidentGovernanceLatest.governance_breach_indicators : [];
  const incidentGovernanceRecovery = incidentGovernanceLatest.operational_recovery_coordination || {};
  const incidentGovernanceFreeze = incidentGovernanceLatest.freeze_escalation_indicators || {};
  const incidentGovernanceRecoveryReadiness = incidentGovernanceLatest.recovery_readiness_indicators || {};
  const incidentGovernanceSeverity = Array.isArray(incidentGovernanceLatest.incident_severity_indicators) ? incidentGovernanceLatest.incident_severity_indicators : [];
  const incidentGovernanceHistoryHistory = Array.isArray(incidentGovernanceHistory) ? incidentGovernanceHistory : [];
  const continuityGovernanceLatest = visibility.continuityGovernanceLatest || {};
  const continuityGovernanceHistory = Array.isArray(visibility.continuityGovernanceHistory) ? visibility.continuityGovernanceHistory : [];
  const continuityGovernanceWarnings = Array.isArray(continuityGovernanceLatest.warnings) ? continuityGovernanceLatest.warnings : [];
  const continuityGovernanceStatus = getString(continuityGovernanceLatest.continuity_governance_status, "watch");
  const continuityGovernanceAuthority = getString(continuityGovernanceLatest.continuity_governance_authority, "WATCH");
  const continuityGovernanceScore = getNumber(continuityGovernanceLatest.continuity_governance_score, 0);
  const continuityGovernanceGrade = getString(continuityGovernanceLatest.continuity_governance_grade, "blocked");
  const continuityGovernanceHistorySummary = continuityGovernanceLatest.continuity_governance_history_summary || {};
  const continuityRecoveryDrill = Array.isArray(continuityGovernanceLatest.recovery_drill_readiness) ? continuityGovernanceLatest.recovery_drill_readiness : [];
  const continuityDrRehearsal = Array.isArray(continuityGovernanceLatest.disaster_recovery_rehearsal_status) ? continuityGovernanceLatest.disaster_recovery_rehearsal_status : [];
  const continuityOperatorFailover = Array.isArray(continuityGovernanceLatest.operator_failover_readiness) ? continuityGovernanceLatest.operator_failover_readiness : [];
  const continuitySupervision = Array.isArray(continuityGovernanceLatest.supervision_continuity_readiness) ? continuityGovernanceLatest.supervision_continuity_readiness : [];
  const continuityFreeze = Array.isArray(continuityGovernanceLatest.continuity_freeze_indicators) ? continuityGovernanceLatest.continuity_freeze_indicators : [];
  const continuityEscalation = Array.isArray(continuityGovernanceLatest.recovery_escalation_readiness) ? continuityGovernanceLatest.recovery_escalation_readiness : [];
  const continuityTiming = Array.isArray(continuityGovernanceLatest.recovery_timing_indicators) ? continuityGovernanceLatest.recovery_timing_indicators : [];
  const continuityRetention = continuityGovernanceLatest.audit_retention_indicators || {};
  const continuityCompleteness = continuityGovernanceLatest.audit_completeness_indicators || {};
  const runtimeRemediationLatest = visibility.runtimeRemediationLatest || {};
  const runtimeRemediationHistory = Array.isArray(visibility.runtimeRemediationHistory) ? visibility.runtimeRemediationHistory : [];
  const runtimeRemediationWarnings = Array.isArray(runtimeRemediationLatest.warnings) ? runtimeRemediationLatest.warnings : [];
  const runtimeRemediationStatus = getString(runtimeRemediationLatest.runtime_remediation_status, "watch");
  const runtimeRemediationAuthority = getString(runtimeRemediationLatest.runtime_remediation_authority, "WATCH");
  const runtimeRemediationScore = getNumber(runtimeRemediationLatest.remediation_readiness_score, 0);
  const runtimeRemediationGrade = getString(runtimeRemediationLatest.runtime_remediation_grade, "blocked");
  const runtimeRemediationClassifications = Array.isArray(runtimeRemediationLatest.remediation_classifications) ? runtimeRemediationLatest.remediation_classifications : [];
  const runtimeRemediationFindings = Array.isArray(runtimeRemediationLatest.endurance_degradation_findings) ? runtimeRemediationLatest.endurance_degradation_findings : [];
  const runtimeRemediationOpen = Array.isArray(runtimeRemediationLatest.open_remediation_tracking) ? runtimeRemediationLatest.open_remediation_tracking : [];
  const runtimeRemediationResolved = Array.isArray(runtimeRemediationLatest.resolved_remediation_history) ? runtimeRemediationLatest.resolved_remediation_history : [];
  const runtimeRemediationBlockers = Array.isArray(runtimeRemediationLatest.unresolved_remediation_blockers) ? runtimeRemediationLatest.unresolved_remediation_blockers : [];
  const runtimeRemediationEscalation = runtimeRemediationLatest.remediation_escalation_indicators || {};
  const runtimeRemediationRecovery = runtimeRemediationLatest.governance_recovery_tracking || {};
  const runtimeRemediationHistorySummary = runtimeRemediationLatest.remediation_governance_history || {};
  const runtimeRemediationRationale = Array.isArray(runtimeRemediationLatest.remediation_rationale_summary) ? runtimeRemediationLatest.remediation_rationale_summary : [];
  const operatorSessionsLatest = visibility.operatorSessionsLatest || {};
  const operatorSessionsHistory = Array.isArray(visibility.operatorSessionsHistory) ? visibility.operatorSessionsHistory : [];
  const operatorSessionWarnings = Array.isArray(operatorSessionsLatest.warnings) ? operatorSessionsLatest.warnings : [];
  const intakeLatest = visibility.intakeLatest || {};
  const intakeHistory = Array.isArray(visibility.intakeHistory) ? visibility.intakeHistory : [];
  const intakeWarnings = Array.isArray(intakeLatest.warnings) ? intakeLatest.warnings : [];
  const physicalSubmissionLatest = visibility.physicalSubmissionLatest || {};
  const physicalSubmissionHistory = Array.isArray(visibility.physicalSubmissionHistory) ? visibility.physicalSubmissionHistory : [];
  const physicalSubmissionWarnings = Array.isArray(physicalSubmissionLatest.warnings) ? physicalSubmissionLatest.warnings : [];
  const modalityLatest = visibility.modalityLatest || {};
  const modalityHistory = Array.isArray(visibility.modalityHistory) ? visibility.modalityHistory : [];
  const modalityWarnings = Array.isArray(modalityLatest.warnings) ? modalityLatest.warnings : [];
  const signatureLatest = visibility.signatureLatest || {};
  const signatureHistory = Array.isArray(visibility.signatureHistory) ? visibility.signatureHistory : [];
  const signatureWarnings = Array.isArray(signatureLatest.warnings) ? signatureLatest.warnings : [];
  const complianceLatest = visibility.complianceLatest || {};
  const complianceHistory = Array.isArray(visibility.complianceHistory) ? visibility.complianceHistory : [];
  const complianceWarnings = Array.isArray(complianceLatest.warnings) ? complianceLatest.warnings : [];
  const returnableLatest = visibility.returnableLatest || {};
  const returnableHistory = Array.isArray(visibility.returnableHistory) ? visibility.returnableHistory : [];
  const returnableWarnings = Array.isArray(returnableLatest.warnings) ? returnableLatest.warnings : [];
  const returnableMissingCount = Object.values(returnableLatest.latest_returnable_governance?.missing_annexure_indicators || {}).filter(Boolean).length;
  const packagingLatest = visibility.packagingLatest || {};
  const packagingHistory = Array.isArray(visibility.packagingHistory) ? visibility.packagingHistory : [];
  const packagingWarnings = Array.isArray(packagingLatest.warnings) ? packagingLatest.warnings : [];
  const deadlineLatest = visibility.deadlineLatest || {};
  const deadlineHistory = Array.isArray(visibility.deadlineHistory) ? visibility.deadlineHistory : [];
  const deadlineWarnings = Array.isArray(deadlineLatest.warnings) ? deadlineLatest.warnings : [];
  const warnings = [
    ...(Array.isArray(lifecycleTelemetry.warnings) ? lifecycleTelemetry.warnings : []),
    ...(visibility.warnings || []),
    ...(Array.isArray(visibility.rehearsalLatest?.warning_banners) ? visibility.rehearsalLatest.warning_banners : []),
    ...(Array.isArray(visibility.cadenceLatest?.warnings) ? visibility.cadenceLatest.warnings : []),
    ...recurringCycleWarnings,
    ...exceptionWarnings,
    ...progressionWarnings,
    ...operationsSummaryWarnings,
    ...declarationWarnings,
    ...finalWarnings,
    ...operationalPilotWarnings,
    ...operationalIntelligenceWarnings,
    ...executiveCommandWarnings,
    ...governanceIndexWarnings,
    ...productionOperationalizationWarnings,
    ...activationWarnings,
    ...supervisionCommandWarnings,
    ...operationsAuditWarnings,
    ...incidentGovernanceWarnings,
    ...continuityGovernanceWarnings,
    ...runtimeRemediationWarnings,
    ...operatorSessionWarnings,
    ...intakeWarnings,
    ...physicalSubmissionWarnings,
    ...modalityWarnings,
    ...signatureWarnings,
    ...complianceWarnings,
    ...returnableWarnings,
    ...packagingWarnings,
    ...deadlineWarnings,
    ...reviewBoardWarnings,
  ];

  const systemResilienceScore = getNumber(lifecycleTelemetry.system_resilience_score, 0);
  const dryRunLockStatus = getBooleanBadge(dryRunStatus.dry_run);
  const queueBacklogDetected = getBooleanBadge(queueBacklog.backlog_detected);
  const backendStatusTone = backendReachable ? "ok" : "error";
  const rehearsalLatest = visibility.rehearsalLatest || {};
  const rehearsalRun = rehearsalLatest.run || {};
  const rehearsalTimeline = Array.isArray(rehearsalLatest.timeline) ? rehearsalLatest.timeline : [];
  const rehearsalHistory = Array.isArray(visibility.rehearsalHistory) ? visibility.rehearsalHistory : [];
  const rehearsalHealth = rehearsalLatest.operational_health || {};
  const rehearsalArtifacts = rehearsalLatest.artifact_summary || {};
  const rehearsalDrills = rehearsalLatest.drill_outcomes || {};
  const readinessLatest = visibility.readinessLatest || {};
  const readinessMetrics = readinessLatest.metrics || {};
  const readinessTrend = readinessLatest.trend_summary || {};
  const readinessCadence = readinessLatest.cadence || {};
  const readinessThresholds = readinessLatest.thresholds || {};
  const readinessIndicators = readinessLatest.warning_threshold_indicators || {};
  const readinessHistory = Array.isArray(visibility.readinessHistory) ? visibility.readinessHistory : [];
  const pilotEvidenceLatest = visibility.pilotEvidenceLatest || {};
  const pilotEvidenceSummary = pilotEvidenceLatest.summary || {};
  const pilotEvidenceHistory = Array.isArray(visibility.pilotEvidenceHistory) ? visibility.pilotEvidenceHistory : [];
  const governanceReview = visibility.governanceReview || {};
  const cadenceLatest = visibility.cadenceLatest || {};
  const cadenceHistory = Array.isArray(visibility.cadenceHistory) ? visibility.cadenceHistory : [];
  const reviewBoardLatest = visibility.reviewBoardLatest || {};
  const reviewBoardHistory = Array.isArray(visibility.reviewBoardHistory) ? visibility.reviewBoardHistory : [];
  const recurringCyclesLatest = visibility.recurringCyclesLatest || {};
  const recurringCyclesHistory = Array.isArray(visibility.recurringCyclesHistory) ? visibility.recurringCyclesHistory : [];
  const exceptionsLatest = visibility.exceptionsLatest || {};
  const exceptionsHistory = Array.isArray(visibility.exceptionsHistory) ? visibility.exceptionsHistory : [];
  const cadence = cadenceLatest.cadence || {};
  const pilotCadence = cadence.pilot_cycle_cadence || {};
  const governanceCadence = cadence.governance_review_cadence || {};
  const cadenceStability = cadence.stability_trend_checkpoints || {};
  const cadenceWarnings = Array.isArray(cadenceLatest.warnings) ? cadenceLatest.warnings : [];
  const recurringCycleTrends = recurringCyclesLatest.recurring_cycle_trends || {};
  const recurringCompliance = recurringCyclesLatest.governance_compliance_summary || {};
  const recurringEndurance = recurringCyclesLatest.operational_endurance_indicators || {};
  const recurringStability = Array.isArray(recurringCyclesLatest.recurring_stability_snapshots) ? recurringCyclesLatest.recurring_stability_snapshots : [];
  const stabilityLatest = visibility.stabilityLatest || {};
  const stability = stabilityLatest.stability || {};
  const stabilityHistory = Array.isArray(visibility.stabilityHistory) ? visibility.stabilityHistory : [];
  const noGoIndicators = Array.isArray(governanceReview.no_go_indicators) ? governanceReview.no_go_indicators : [];
  const signOffChecklist = Array.isArray(governanceReview.operator_sign_off_checklist) ? governanceReview.operator_sign_off_checklist : [];
  const governanceChecklist = Array.isArray(governanceReview.governance_review_checklist) ? governanceReview.governance_review_checklist : [];
  const latestEvidenceLock = governanceReview.submission_lock_verification || {};
  const latestEvidenceDryRun = (governanceReview.evidence_sections || {}).dry_run_enforcement_verification || {};
  const pilotAuthorizationStatus = getString(governanceReview.pilot_authorization_status, "pending_review");
  const latestEvidencePack = governanceReview.latest_evidence_pack || {};
  const latestEvidencePackSummary = latestEvidencePack.summary || {};
  const latestEvidencePackCounts = latestEvidencePackSummary.summary_counts || {};
  const governanceHistory = governanceReview["PASS/WARN/FAIL_history"] || {};
  const readinessDrift = stability.readiness_drift || {};
  const cadenceDrift = stability.cadence_drift || {};
  const queueTrend = stability.queue_stability_trend || {};
  const workerTrend = stability.worker_stability_trend || {};
  const telemetryTrend = stability.telemetry_degradation || {};
  const retryTrend = stability.retry_escalation_trend || {};
  const dlqTrend = stability.dlq_frequency_trend || {};
  const operatorTrend = stability.operator_intervention_trend || {};
  const driftWarnings = Array.isArray(stability.drift_warnings) ? stability.drift_warnings : [];
  const cadenceCompliance = stability.cadence_compliance || {};
  const warningIndicators = stability.warning_indicators || {};
  const reviewBoardStatus = getString(reviewBoardLatest.review_board_status, "watch");
  const reviewBoardScore = getNumber(reviewBoardLatest.review_board_score, 0);
  const reviewBoardHistoryCadence = reviewBoardLatest.review_board_cadence || {};
  const reviewBoardSummary = reviewBoardLatest.institutional_review_summary || {};
  const reviewBoardOutstanding = Array.isArray(reviewBoardLatest.outstanding_governance_actions) ? reviewBoardLatest.outstanding_governance_actions : [];
  const reviewBoardExceptions = Array.isArray(reviewBoardLatest.unresolved_operational_exceptions) ? reviewBoardLatest.unresolved_operational_exceptions : [];
  const reviewBoardEscalation = reviewBoardLatest.escalation_review_tracking || {};
  const recurringCycleStatus = getString(recurringCyclesLatest.recurring_cycle_status, "watch");
  const recurringCycleScore = getNumber(recurringCyclesLatest.recurring_cycle_score, 0);
  const recurringCycleGrade = getString(recurringCyclesLatest.recurring_cycle_grade, "watch");
  const recurringCycleSummaryCounts = recurringCyclesLatest.summary_counts || {};
  const recurringCycleLatest = recurringCyclesLatest.latest_cycle || {};
  const exceptionSummary = exceptionsLatest.exception_summary || {};
  const remediationSummary = exceptionsLatest.remediation_status_summary || {};
  const riskIndicators = exceptionsLatest.operational_risk_indicators || {};
  const anomalySummary = exceptionsLatest.recurring_anomaly_summary || {};
  const unresolvedExceptions = Array.isArray(exceptionsLatest.unresolved_exception_tracking) ? exceptionsLatest.unresolved_exception_tracking : [];
  const resolvedExceptionHistory = Array.isArray(exceptionsLatest.resolved_exception_history) ? exceptionsLatest.resolved_exception_history : [];
  const classificationHistory = Array.isArray(exceptionsLatest.classification_history) ? exceptionsLatest.classification_history : [];
  const remediationLatest = visibility.remediationLatest || {};
  const remediationHistory = Array.isArray(visibility.remediationHistory) ? visibility.remediationHistory : [];
  const remediationActions = Array.isArray(remediationLatest.remediation_actions) ? remediationLatest.remediation_actions : [];
  const remediationSummaryData = remediationLatest.remediation_summary || {};
  const remediationClosureSummary = remediationLatest.operational_risk_closure_summary || {};
  const remediationHistorySummary = remediationLatest.remediation_governance_history || {};
  const remediationIndicators = remediationLatest.operational_risk_indicators || {};
  const remediationWarnings = Array.isArray(remediationLatest.warnings) ? remediationLatest.warnings : [];
  const progressionStatus = getString(progressionLatest.progression_status, "watch");
  const progressionDecision = getString(progressionLatest.progression_decision, "review_required");
  const progressionScore = getNumber(progressionLatest.progression_score, 0);
  const progressionGrade = getString(progressionLatest.progression_grade, "watch");
  const progressionSummary = progressionLatest.pilot_progression_summary || {};
  const progressionEligibility = progressionLatest.expansion_eligibility_indicators || {};
  const progressionBlockers = progressionLatest.unresolved_blocker_summary || {};
  const progressionRationale = progressionLatest.governance_rationale_summary || {};
  const progressionDecisionHistory = Array.isArray(progressionLatest.progression_decision_history) ? progressionLatest.progression_decision_history : [];
  const operationsSummary = operationsSummaryLatest.summary_components || {};
  const operationsWatchIndicators = operationsSummaryLatest.consolidated_watch_indicators || {};
  const operationsBlockers = operationsSummaryLatest.unresolved_blocker_summary || {};
  const operationsRecommendation = operationsSummaryLatest.governance_recommendation_summary || {};
  const operationsHistory = Array.isArray(operationsSummaryLatest.institutional_operational_summary_history) ? operationsSummaryLatest.institutional_operational_summary_history : [];
  const latestStabilityCycle = stabilityLatest.latest_cycle || {};
  const latestStabilityExport = stabilityLatest.latest_governance_export || {};

  const readinessWarnings = [
    ...(readinessIndicators.score_below_threshold ? ["Readiness score below threshold"] : []),
    ...(readinessIndicators.success_rate_below_threshold ? ["Rehearsal success rate below threshold"] : []),
    ...(readinessIndicators.retry_recovery_below_threshold ? ["Retry recovery below threshold"] : []),
    ...(readinessIndicators.rollback_below_threshold ? ["Rollback success below threshold"] : []),
    ...(readinessIndicators.queue_stability_below_threshold ? ["Queue stability below threshold"] : []),
    ...(readinessIndicators.worker_stability_below_threshold ? ["Worker stability below threshold"] : []),
    ...(readinessIndicators.telemetry_health_below_threshold ? ["Telemetry health below threshold"] : []),
    ...(readinessIndicators.dlq_escalation_above_threshold ? ["DLQ escalation frequency above threshold"] : []),
    ...(readinessIndicators.operator_intervention_above_threshold ? ["Operator intervention frequency above threshold"] : []),
    ...(driftWarnings.includes("readiness_drift_warning") ? ["Readiness drift warning"] : []),
    ...(driftWarnings.includes("cadence_drift_warning") ? ["Cadence drift warning"] : []),
    ...(driftWarnings.includes("queue_stability_warning") ? ["Queue stability drift warning"] : []),
    ...(driftWarnings.includes("worker_stability_warning") ? ["Worker stability drift warning"] : []),
    ...(driftWarnings.includes("telemetry_degradation_warning") ? ["Telemetry degradation warning"] : []),
    ...(driftWarnings.includes("retry_escalation_warning") ? ["Retry escalation warning"] : []),
    ...(driftWarnings.includes("dlq_frequency_warning") ? ["DLQ frequency warning"] : []),
    ...(driftWarnings.includes("operator_intervention_warning") ? ["Operator intervention warning"] : []),
    ...remediationWarnings,
  ];

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <div className="mx-auto max-w-7xl space-y-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">LMCP AutoQuote</h1>
              <StatusBadge label={APP_ENV === "staging" ? "Staging Command Centre" : "Command Centre"} tone="neutral" />
            </div>
            <p className="text-slate-400">Enterprise Procurement Workflow Dashboard</p>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
              <StatusBadge
                label={`Backend ${backendReachable ? "connected" : "unreachable"}`}
                tone={backendStatusTone}
              />
              <StatusBadge label={`Backend URL ${API_BASE}`} tone="neutral" />
              <StatusBadge
                label={`Frontend env ${backendHealth?.environment || APP_ENV}`}
                tone="neutral"
              />
              <StatusBadge
                label={`Telemetry ${systemResilienceScore >= 70 ? "healthy" : "watch"}`}
                tone={systemResilienceScore >= 70 ? "ok" : "error"}
              />
            </div>
          </div>

          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="rounded-xl bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh Workflow"}
          </button>
        </header>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card title="Target Value" value={money(cp?.total_target_value || 0)} />
          <Card title="Quoted Value" value={money(cp?.total_quoted_value || 0)} />
          <Card title="Improvement" value={money(Math.abs(cp?.total_variance || 0))} />
          <Card title="Variance" value={`${Number(cp?.total_variance_pct || 0).toFixed(2)}%`} />
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge
              label={backendReachable ? "API reachable" : "API not reachable"}
              tone={backendReachable ? "ok" : "error"}
            />
            <span className="text-sm text-slate-400">{backendMessage}</span>
            {backendHealth?.timestamp ? (
              <span className="text-sm text-slate-500">
                Health timestamp: {backendHealth.timestamp}
              </span>
            ) : null}
            <StatusBadge
              label={`Dry-run ${dryRunStatus.status || "unknown"}`}
              tone={dryRunStatus.status === "ok" ? "ok" : dryRunStatus.status === "not_run" ? "neutral" : "error"}
            />
            <StatusBadge
              label={`Submission locks ${getNumber(guardSummary.submission_locks, 0)}`}
              tone={getNumber(guardSummary.submission_locks, 0) > 0 ? "neutral" : "ok"}
            />
          </div>
        </section>

        {(error || visibilityError) ? (
          <section className="space-y-3 rounded-2xl border border-amber-700 bg-amber-950/50 p-5 text-amber-100">
            {error ? (
              <div>
                <h2 className="font-semibold">Workflow dashboard data unavailable</h2>
                <p className="mt-2 text-sm text-amber-200">{error}</p>
              </div>
            ) : null}
            {visibilityError ? (
              <div>
                <h2 className="font-semibold">Operational visibility partial</h2>
                <p className="mt-2 text-sm text-amber-200">{visibilityError}</p>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Staging Operational Visibility</h2>
              <p className="text-sm text-slate-400">
                Read-only dry-run and lifecycle telemetry. No submission controls are exposed.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only panel" : "Read-only panel"}
              tone="neutral"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MetricPanel
              title="Dry-Run Execution Status"
              tone={dryRunStatus.status === "ok" ? "ok" : "neutral"}
              summary={dryRunStatus.mode || "No dry-run status recorded"}
              items={[
                ["Status", getString(dryRunStatus.status)],
                ["Dry-run enabled", dryRunLockStatus.label],
                ["Selected RFQs", String(getNumber(dryRunStatus.selected_count, 0))],
                ["Ready count", String(getNumber(dryRunStatus.ready_count, 0))],
                ["Missing docs", String(getNumber(dryRunStatus.missing_documents_count, 0))],
                ["Operator action required", getBooleanBadge(dryRunStatus.operator_action_required).label],
              ]}
            />

            <MetricPanel
              title="RFQ Lifecycle State"
              tone="neutral"
              summary={`Total RFQs: ${getNumber(visibility.lifecycleStatus?.total_rfqs, 0)}`}
              items={[
                ["DISCOVERED", String(getNumber(lifecycleCounts.DISCOVERED, 0))],
                ["DOCUMENTS_PARSED", String(getNumber(lifecycleCounts.DOCUMENTS_PARSED, 0))],
                ["PRICED", String(getNumber(lifecycleCounts.PRICED, 0))],
                ["QUOTE_PACK_READY", String(getNumber(lifecycleCounts.QUOTE_PACK_READY, 0))],
                ["SUBMISSION_READY", String(getNumber(lifecycleCounts.SUBMISSION_READY, 0))],
                ["READY_FOR_RETRY", String(queuedForRetry)],
              ]}
            />

            <MetricPanel
              title="Queue Health"
              tone={queueBacklogDetected.tone}
              summary={`Backlog ${queueBacklog.total_backlog || 0}`}
              items={[
                ["Backlog detected", queueBacklogDetected.label],
                ["Broker queue depth", String(sumRecordValues(queueBacklog.broker_queue_depth))],
                ["Lifecycle queue depth", String(sumRecordValues(queueBacklog.lifecycle_queue_depth))],
                ["Stalled tasks", String(Array.isArray(lifecycleTelemetry.stalled_lifecycle_tasks) ? lifecycleTelemetry.stalled_lifecycle_tasks.length : 0)],
                ["Retry count", String(retryCount)],
                ["Dead queues", String(deadQueues.length)],
              ]}
            />

            <MetricPanel
              title="Worker Heartbeats"
              tone={getBooleanBadge(lifecycleTelemetry.worker_online).tone}
              summary={`${Array.isArray(workerHeartbeat.online_workers) ? workerHeartbeat.online_workers.length : 0} online worker(s)`}
              items={[
                ["Worker online", getBooleanBadge(lifecycleTelemetry.worker_online).label],
                ["Crash count", String(getNumber(lifecycleTelemetry.worker_crash_count, 0))],
                ["Restart count", String(getNumber(lifecycleTelemetry.worker_restart_count, 0))],
                ["Active workers", String(Array.isArray(workerHeartbeat.online_workers) ? workerHeartbeat.online_workers.length : 0)],
                ["Queue workers", String(workerHeartbeat.queue_workers ? Object.keys(workerHeartbeat.queue_workers).length : 0)],
                ["Heartbeat source", getString(workerHeartbeat.state_store, "sandbox")],
              ]}
            />

            <MetricPanel
              title="Retry and Dead-Letter Visibility"
              tone={warnings.length ? "error" : "ok"}
              summary={warnings.length ? `${warnings.length} warning(s)` : "No retry warnings"}
              items={[
                ["Retry pending", String(queuedForRetry)],
                ["Timed-out tasks", String(Array.isArray(taskTimeouts.timed_out_tasks) ? taskTimeouts.timed_out_tasks.length : 0)],
                ["Isolated dead queues", String(deadQueues.length)],
                ["Recovery hooks", String(Object.keys(autoRecoveryHooks).length)],
                ["Backlog warning threshold", String(getNumber(queueBacklog.warning_threshold, 0))],
                ["Warnings", String(warnings.length)],
              ]}
            />

            <MetricPanel
              title="Submission Lock Status"
              tone={getNumber(guardSummary.submission_locks, 0) > 0 ? "neutral" : "ok"}
              summary={`Locks: ${getNumber(guardSummary.submission_locks, 0)}`}
              items={[
                ["Submission locks", String(getNumber(guardSummary.submission_locks, 0))],
                ["Operator rejections", String(getNumber(guardSummary.operator_rejections, 0))],
                ["Paused sources", String(getNumber(guardSummary.paused_sources, 0))],
                ["Guard events", String(getNumber(guardSummary.guard_events, 0))],
                ["Latest guard update", getString(visibility.guardSummary?.updated_at, "n/a")],
                ["Dry-run enabled", dryRunLockStatus.label],
              ]}
            />

            <MetricPanel
              title="Telemetry Health"
              tone={systemResilienceScore >= 70 ? "ok" : "error"}
              summary={`System resilience ${systemResilienceScore.toFixed(2)}`}
              items={[
                ["Operational status", getString(operationalHealth.status, "unknown")],
                ["Review queue capacity", String(getNumber(reviewQueue.operator_capacity, 0))],
                ["Capacity remaining", String(getNumber(reviewQueue.operator_capacity_remaining, 0))],
                ["Capacity used", String(getNumber(reviewQueue.operator_capacity_used, 0))],
                ["Generated at", getString(lifecycleTelemetry.generated_at, "n/a")],
                ["Warnings", String(warnings.length)],
              ]}
            />
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Runtime Remediation Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only remediation governance for endurance WARN findings, escalation gaps, continuity instability, and governance recovery tracking.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only runtime remediation" : "Read-only runtime remediation"}
              tone="neutral"
            />
          </div>

          {runtimeRemediationWarnings.length ? (
            <div className="space-y-3">
              {runtimeRemediationWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Runtime remediation governance remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Runtime Remediation"
              tone={runtimeRemediationStatus === "ok" ? "ok" : runtimeRemediationStatus === "blocked" ? "error" : "neutral"}
              summary={`${runtimeRemediationGrade} • ${runtimeRemediationScore.toFixed(2)}`}
              items={[
                ["Status", runtimeRemediationStatus],
                ["Authority", runtimeRemediationAuthority],
                ["Score", runtimeRemediationScore.toFixed(2)],
                ["Grade", runtimeRemediationGrade],
                ["History", String(runtimeRemediationHistory.length)],
                ["Findings", String(runtimeRemediationClassifications.length)],
              ]}
            />

            <MetricPanel
              title="Endurance Findings"
              tone={runtimeRemediationFindings.length ? "error" : "ok"}
              summary={`${runtimeRemediationFindings.length} endurance finding(s)`}
              items={[
                ["Degradation findings", String(runtimeRemediationFindings.length)],
                ["Open remediation", String(runtimeRemediationOpen.length)],
                ["Resolved remediation", String(runtimeRemediationResolved.length)],
                ["Blockers", String(runtimeRemediationBlockers.length)],
                ["Recovery ready", getBooleanBadge(runtimeRemediationRecovery.governance_recovery_ready).label],
                ["Recovery status", getString(runtimeRemediationRecovery.latest_continuity_status, "watch")],
              ]}
            />

            <MetricPanel
              title="Escalation & Recovery"
              tone={Object.values(runtimeRemediationEscalation).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(runtimeRemediationEscalation).filter(Boolean).length} escalation flag(s)`}
              items={[
                ["Endurance degradation", getBooleanBadge(runtimeRemediationEscalation.endurance_degradation_found).label],
                ["Escalation gap", getBooleanBadge(runtimeRemediationEscalation.escalation_gap_found).label],
                ["Continuity instability", getBooleanBadge(runtimeRemediationEscalation.continuity_instability_found).label],
                ["Governance degradation", getBooleanBadge(runtimeRemediationEscalation.governance_degradation_found).label],
                ["Supervision failure", getBooleanBadge(runtimeRemediationEscalation.supervision_failure_found).label],
                ["Observability failure", getBooleanBadge(runtimeRemediationEscalation.observability_failure_found).label],
              ]}
            />

            <MetricPanel
              title="History & Rationale"
              tone={runtimeRemediationHistorySummary.status === "PASS" ? "ok" : runtimeRemediationHistorySummary.status === "WARN" ? "neutral" : "error"}
              summary={`${getNumber(runtimeRemediationHistorySummary.score_history?.latest, runtimeRemediationScore).toFixed(2)} latest score`}
              items={[
                ["Latest analysis", getString(runtimeRemediationLatest.analysis_id, "n/a")],
                ["Latest status", getString(runtimeRemediationHistorySummary.status, "WARN")],
                ["Latest owner", getString(runtimeRemediationHistorySummary.latest_owner, "n/a")],
                ["Blocking count", String(getNumber(runtimeRemediationHistorySummary.blocking_count, runtimeRemediationBlockers.length))],
                ["Trend", getString(runtimeRemediationHistorySummary.score_history?.trend, "stable")],
                ["Rationale items", String(runtimeRemediationRationale.length)],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Runtime Remediation History</h3>
                <StatusBadge label={`${runtimeRemediationHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runtimeRemediationHistory.length ? (
                      runtimeRemediationHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.runtime_remediation_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.runtime_remediation_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.remediation_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No runtime remediation history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Runtime Remediation Indicators</h3>
                <StatusBadge label={runtimeRemediationAuthority} tone={runtimeRemediationAuthority === "GO" ? "ok" : runtimeRemediationAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Endurance degradation: {String(runtimeRemediationEscalation.endurance_degradation_found)}</div>
                <div>Escalation gap: {String(runtimeRemediationEscalation.escalation_gap_found)}</div>
                <div>Continuity instability: {String(runtimeRemediationEscalation.continuity_instability_found)}</div>
                <div>Governance degradation: {String(runtimeRemediationEscalation.governance_degradation_found)}</div>
                <div>Supervision failure: {String(runtimeRemediationEscalation.supervision_failure_found)}</div>
                <div>Observability failure: {String(runtimeRemediationEscalation.observability_failure_found)}</div>
                <div>Open blockers: {String(runtimeRemediationBlockers.length)}</div>
                <div>Recovered: {getBooleanBadge(runtimeRemediationRecovery.governance_recovery_ready).label}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Production Release Gate</h2>
              <p className="text-sm text-slate-400">
                Read-only production release authority derived from staged deployment validation evidence.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only release gate" : "Read-only release gate"}
              tone="neutral"
            />
          </div>

          {releaseGovernanceWarnings.length ? (
            <div className="space-y-3">
              {releaseGovernanceWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Release gate evidence remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Release Authority"
              tone={releaseGovernanceAuthority === "GO" ? "ok" : releaseGovernanceAuthority === "NO_GO" ? "error" : "neutral"}
              summary={`${releaseGovernanceAuthority} • ${releaseGovernanceScore.toFixed(2)}`}
              items={[
                ["Status", releaseGovernanceStatus],
                ["Authority", releaseGovernanceAuthority],
                ["Grade", releaseGovernanceGrade],
                ["History", String(releaseGovernanceHistory.length)],
                ["Analysis", getString(releaseLatest.analysis_id, "n/a")],
                ["Rollout", getBooleanBadge(Boolean(releaseGovernanceLatest.production_rollout_readiness)).label],
              ]}
            />

            <MetricPanel
              title="Release Readiness"
              tone={releaseGovernanceAuthority === "GO" ? "ok" : releaseGovernanceAuthority === "NO_GO" ? "error" : "neutral"}
              summary={`${getNumber(releaseGovernanceLatest.production_readiness_score, releaseGovernanceScore).toFixed(2)} readiness score`}
              items={[
                ["Runtime segmentation", getBooleanBadge(releaseReadiness.runtime_segmentation_ready).label],
                ["Operator access", getBooleanBadge(releaseReadiness.operator_access_ready).label],
                ["Observability", getBooleanBadge(releaseReadiness.observability_ready).label],
                ["Backup restore", getBooleanBadge(releaseReadiness.backup_restore_ready).label],
                ["Disaster recovery", getBooleanBadge(releaseReadiness.disaster_recovery_ready).label],
                ["Deployment governance", getBooleanBadge(releaseReadiness.deployment_governance_ready).label],
              ]}
            />

            <MetricPanel
              title="Risk Indicators"
              tone={releaseDeploymentRisk.deployment_risk ? "error" : "ok"}
              summary={`${Object.values(releaseDeploymentRisk || {}).filter(Boolean).length} risk flag(s)`}
              items={[
                ["Deployment risk", getBooleanBadge(releaseDeploymentRisk.deployment_risk).label],
                ["Runtime segmentation risk", getBooleanBadge(releaseDeploymentRisk.runtime_segmentation_risk).label],
                ["Operator access risk", getBooleanBadge(releaseDeploymentRisk.operator_access_risk).label],
                ["Observability risk", getBooleanBadge(releaseDeploymentRisk.observability_risk).label],
                ["Backup restore risk", getBooleanBadge(releaseDeploymentRisk.backup_restore_risk).label],
                ["HA risk", getBooleanBadge(releaseDeploymentRisk.high_availability_risk).label],
              ]}
            />

            <MetricPanel
              title="Operational Release"
              tone={releaseOperational.overall_validation_passed ? "ok" : "error"}
              summary={`${getBooleanBadge(Boolean(releaseOperational.overall_validation_passed)).label} validation`}
              items={[
                ["Lock verified", getBooleanBadge(releaseOperational.submission_lock_verified).label],
                ["Dry-run verified", getBooleanBadge(releaseOperational.dry_run_verified).label],
                ["Environment safe", getBooleanBadge(releaseOperational.environment_safe).label],
                ["Override", getBooleanBadge(Boolean(releaseGovernanceLatest.governance_override_authority)).label],
                ["Escalation", getBooleanBadge(Boolean(releaseGovernanceLatest.release_escalation_authority)).label],
                ["Rollout ready", getBooleanBadge(Boolean(releaseGovernanceLatest.production_rollout_readiness)).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Release Governance History</h3>
                <StatusBadge label={`${releaseGovernanceHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {releaseGovernanceHistory.length ? (
                      releaseGovernanceHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.release_governance_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.release_governance_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.release_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No release governance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Release Readiness Indicators</h3>
                <StatusBadge label={releaseGovernanceAuthority} tone={releaseGovernanceAuthority === "GO" ? "ok" : releaseGovernanceAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Runtime segmentation: {getBooleanBadge(releaseReadiness.runtime_segmentation_ready).label}</div>
                <div>Operator access: {getBooleanBadge(releaseReadiness.operator_access_ready).label}</div>
                <div>Observability: {getBooleanBadge(releaseReadiness.observability_ready).label}</div>
                <div>Backup restore: {getBooleanBadge(releaseReadiness.backup_restore_ready).label}</div>
                <div>Disaster recovery: {getBooleanBadge(releaseReadiness.disaster_recovery_ready).label}</div>
                <div>High availability: {getBooleanBadge(releaseReadiness.high_availability_ready).label}</div>
                <div>Audit retention: {getBooleanBadge(releaseReadiness.audit_retention_ready).label}</div>
                <div>Deployment governance: {getBooleanBadge(releaseReadiness.deployment_governance_ready).label}</div>
              </div>
              <div className="mt-6 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Submission lock: {getBooleanBadge(releaseOperational.submission_lock_verified).label}</div>
                <div>Dry-run: {getBooleanBadge(releaseOperational.dry_run_verified).label}</div>
                <div>Environment: {getBooleanBadge(releaseOperational.environment_safe).label}</div>
                <div>Rollout: {getBooleanBadge(Boolean(releaseGovernanceLatest.production_rollout_readiness)).label}</div>
              </div>
              <div className="mt-6 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>GO authority: {getBooleanBadge(Boolean(releaseAuthorityIndicators.go_release_authority)).label}</div>
                <div>WATCH authority: {getBooleanBadge(Boolean(releaseAuthorityIndicators.watch_release_authority)).label}</div>
                <div>NO-GO authority: {getBooleanBadge(Boolean(releaseAuthorityIndicators.no_go_release_authority)).label}</div>
                <div>Override: {getBooleanBadge(Boolean(releaseGovernanceLatest.governance_override_authority)).label}</div>
                <div>Escalation: {getBooleanBadge(Boolean(releaseGovernanceLatest.release_escalation_authority)).label}</div>
                <div>Score trend: {getString(releaseHistorySummary.score_history?.trend, "stable")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Activation Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only tenant, operator, supervision, and rollout expansion authority derived from supervised production rollout validation evidence.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only activation governance" : "Read-only activation governance"}
              tone="neutral"
            />
          </div>

          {activationWarnings.length ? (
            <div className="space-y-3">
              {activationWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Activation evidence remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Activation Authority"
              tone={activationAuthority === "GO" ? "ok" : activationAuthority === "NO_GO" ? "error" : "neutral"}
              summary={`${activationAuthority} • ${activationScore.toFixed(2)}`}
              items={[
                ["Status", activationStatus],
                ["Authority", activationAuthority],
                ["Grade", activationGrade],
                ["History", String(activationHistory.length)],
                ["Analysis", getString(activationLatest.analysis_id, "n/a")],
                ["Rollout", getBooleanBadge(Boolean(activationLatest.production_rollout_readiness)).label],
              ]}
            />

            <MetricPanel
              title="Readiness Breakdown"
              tone={activationAuthority === "GO" ? "ok" : activationAuthority === "NO_GO" ? "error" : "neutral"}
              summary={`${getNumber(activationLatestRollout.rollout_readiness_summary?.rollout_readiness_score, activationScore).toFixed(2)} rollout score`}
              items={[
                ["Tenant", getBooleanBadge(activationTenant.tenant_activation_ready).label],
                ["Operator", getBooleanBadge(activationOperator.operator_certification_ready).label],
                ["Supervision", getBooleanBadge(activationSupervision.supervision_assignment_ready).label],
                ["Deployment health", getBooleanBadge(activationThroughput.deployment_health_ready).label],
                ["Observability", getBooleanBadge(activationThroughput.production_observability_ready).label],
                ["Release auth", getBooleanBadge(activationThroughput.release_authorization_valid).label],
              ]}
            />

            <MetricPanel
              title="Freeze & Escalation"
              tone={activationFreeze.freeze_active ? "error" : "ok"}
              summary={`${Object.values(activationFreeze || {}).filter(Boolean).length} freeze flag(s)`}
              items={[
                ["Freeze active", getBooleanBadge(activationFreeze.freeze_active).label],
                ["Expansion freeze", getBooleanBadge(activationFreeze.throughput_expansion_freeze).label],
                ["Rollout freeze", getBooleanBadge(activationFreeze.rollout_authorization_freeze).label],
                ["Escalation ready", getBooleanBadge(activationEscalation.escalation_ready).label],
                ["Release authority", getString(activationLatestRelease.release_authority, "WATCH")],
                ["Rollout valid", getBooleanBadge(Boolean(activationLatestRollout.institutional_rollout_certification_evidence?.rollout_ready_for_supervised_deployment)).label],
              ]}
            />

            <MetricPanel
              title="Supervision Coverage"
              tone={activationSaturation.operator_saturation_active ? "error" : "ok"}
              summary={`${getNumber(activationCoverage.supervision_coverage_score, 0).toFixed(2)} coverage score`}
              items={[
                ["Coverage ready", getBooleanBadge(activationCoverage.active_supervision_coverage_ready).label],
                ["Operator ready", getBooleanBadge(activationCoverage.operator_availability_ready).label],
                ["Active sessions", String(getNumber(activationCoverage.coverage_active_sessions, 0))],
                ["Assigned RFQs", String(Array.isArray(activationCoverage.coverage_assigned_rfqs) ? activationCoverage.coverage_assigned_rfqs.length : 0)],
                ["Pending approvals", String(Array.isArray(activationCoverage.coverage_pending_approvals) ? activationCoverage.coverage_pending_approvals.length : 0)],
                ["Saturation", getBooleanBadge(activationSaturation.operator_saturation_active).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Activation Governance History</h3>
                <StatusBadge label={`${activationHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activationHistory.length ? (
                      activationHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.activation_governance_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.activation_governance_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.activation_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No activation governance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Activation Readiness Indicators</h3>
                <StatusBadge label={activationAuthority} tone={activationAuthority === "GO" ? "ok" : activationAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Tenant activation: {getBooleanBadge(activationTenant.tenant_activation_ready).label}</div>
                <div>Operator certification: {getBooleanBadge(activationOperator.operator_certification_ready).label}</div>
                <div>Supervision assignment: {getBooleanBadge(activationSupervision.supervision_assignment_ready).label}</div>
                <div>Staged segmentation: {getBooleanBadge(activationSegmentation.staged_rollout_segmentation_ready).label}</div>
                <div>Throughput expansion: {getBooleanBadge(activationThroughput.throughput_expansion_ready).label}</div>
                <div>Escalation readiness: {getBooleanBadge(activationEscalation.escalation_ready).label}</div>
                <div>Freeze active: {getBooleanBadge(activationFreeze.freeze_active).label}</div>
                <div>Release authority: {getString(activationLatestRelease.release_authority, "WATCH")}</div>
              </div>
              <div className="mt-6 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Active sessions: {getNumber(activationCoverage.coverage_active_sessions, 0)}</div>
                <div>Assigned RFQs: {String(Array.isArray(activationCoverage.coverage_assigned_rfqs) ? activationCoverage.coverage_assigned_rfqs.length : 0)}</div>
                <div>Pending approvals: {String(Array.isArray(activationCoverage.coverage_pending_approvals) ? activationCoverage.coverage_pending_approvals.length : 0)}</div>
                <div>Rollout valid: {getBooleanBadge(Boolean(activationLatestRollout.institutional_rollout_certification_evidence?.rollout_ready_for_supervised_deployment)).label}</div>
                <div>Certification: {getString(activationLatestRelease.certification_status, "WATCH")}</div>
                <div>Review board: {getString(activationEscalation.review_board_status, "watch")}</div>
              </div>
              <div className="mt-6 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Expansion trend: {getString(activationHistorySummary.score_history?.trend, "stable")}</div>
                <div>Expansion score: {getNumber(activationHistorySummary.latest_score, activationScore).toFixed(2)}</div>
                <div>Freeze flags: {String(Object.values(activationFreeze || {}).filter(Boolean).length)}</div>
                <div>Saturation flags: {String(Object.values(activationSaturation || {}).filter(Boolean).length)}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Production Supervision Command</h2>
              <p className="text-sm text-slate-400">
                Read-only operator coverage, RFQ oversight, escalation command visibility, and supervision SLA tracking derived from supervised production rollout evidence.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only supervision command" : "Read-only supervision command"}
              tone="neutral"
            />
          </div>

          {supervisionCommandWarnings.length ? (
            <div className="space-y-3">
              {supervisionCommandWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Supervision command evidence remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Supervision Authority"
              tone={supervisionCommandAuthority === "GO" ? "ok" : supervisionCommandAuthority === "NO_GO" ? "error" : "neutral"}
              summary={`${supervisionCommandAuthority} • ${supervisionCommandScore.toFixed(2)}`}
              items={[
                ["Status", supervisionCommandStatus],
                ["Authority", supervisionCommandAuthority],
                ["Grade", supervisionCommandGrade],
                ["History", String(supervisionCommandHistory.length)],
                ["Analysis", getString(supervisionCommandLatest.analysis_id, "n/a")],
                ["Rollout", getBooleanBadge(Boolean(supervisionCommandLatest.production_rollout_readiness)).label],
              ]}
            />

            <MetricPanel
              title="Coverage & Workload"
              tone={supervisionCommandCoverage.supervision_coverage_ready ? "ok" : "error"}
              summary={`${getNumber(supervisionCommandCoverage.coverage_score, 0).toFixed(2)} coverage score`}
              items={[
                ["Coverage ready", getBooleanBadge(supervisionCommandCoverage.supervision_coverage_ready).label],
                ["Active sessions", String(getNumber(supervisionCommandCoverage.coverage_active_sessions, 0))],
                ["Assigned RFQs", String(Array.isArray(supervisionCommandCoverage.coverage_assigned_rfqs) ? supervisionCommandCoverage.coverage_assigned_rfqs.length : 0)],
                ["Pending approvals", String(Array.isArray(supervisionCommandCoverage.coverage_pending_approvals) ? supervisionCommandCoverage.coverage_pending_approvals.length : 0)],
                ["Workload", getString(supervisionCommandWorkload.workload_pressure, "low")],
                ["SLA ready", getBooleanBadge(supervisionCommandSla.sla_ready).label],
              ]}
            />

            <MetricPanel
              title="Escalation & Freeze"
              tone={supervisionCommandFreeze.freeze_active ? "error" : "ok"}
              summary={`${Object.values(supervisionCommandFreeze || {}).filter(Boolean).length} freeze flag(s)`}
              items={[
                ["Freeze active", getBooleanBadge(supervisionCommandFreeze.freeze_active).label],
                ["Operator lapse", getBooleanBadge(supervisionCommandLapse.operator_certification_lapse).label],
                ["Coverage lapse", getBooleanBadge(supervisionCommandLapse.coverage_lapse).label],
                ["Escalation ready", getBooleanBadge(supervisionCommandEscalation.escalation_ready).label],
                ["Release authority", getString(supervisionCommandLatest.latest_release_certification?.release_authority, "WATCH")],
                ["Rollout valid", getBooleanBadge(Boolean(supervisionCommandLatest.institutional_rollout_certification_evidence?.rollout_ready_for_supervised_deployment)).label],
              ]}
            />

            <MetricPanel
              title="Supervision Saturation"
              tone={supervisionCommandSaturation.supervision_saturation_active ? "error" : "ok"}
              summary={`${Object.values(supervisionCommandSaturation || {}).filter(Boolean).length} saturation flag(s)`}
              items={[
                ["Saturation active", getBooleanBadge(supervisionCommandSaturation.supervision_saturation_active).label],
                ["Active sessions", String(getNumber(supervisionCommandCoverage.coverage_active_sessions, 0))],
                ["Over threshold", getBooleanBadge(supervisionCommandSaturation.active_sessions_over_threshold).label],
                ["Assigned RFQs", getBooleanBadge(supervisionCommandSaturation.assigned_rfqs_over_threshold).label],
                ["Pending approvals", getBooleanBadge(supervisionCommandSaturation.pending_approvals_over_threshold).label],
                ["Review board", getString(supervisionCommandEscalation.review_board_status, "watch")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Supervision Governance History</h3>
                <StatusBadge label={`${supervisionCommandHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {supervisionCommandHistory.length ? (
                      supervisionCommandHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.supervision_command_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.supervision_command_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.supervision_command_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No supervision command history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Supervision Indicators</h3>
                <StatusBadge label={supervisionCommandAuthority} tone={supervisionCommandAuthority === "GO" ? "ok" : supervisionCommandAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Active supervised operators: {String(Array.isArray(supervisionCommandOperators) ? supervisionCommandOperators.length : 0)}</div>
                <div>Coverage ready: {getBooleanBadge(supervisionCommandCoverage.supervision_coverage_ready).label}</div>
                <div>RFQ oversight: {String(getNumber(supervisionCommandRfqOversight.assigned_rfq_count, 0))}</div>
                <div>Escalation ready: {getBooleanBadge(supervisionCommandEscalation.escalation_ready).label}</div>
                <div>Operating workload: {getString(supervisionCommandWorkload.workload_pressure, "low")}</div>
                <div>SLA ready: {getBooleanBadge(supervisionCommandSla.sla_ready).label}</div>
                <div>Freeze active: {getBooleanBadge(supervisionCommandFreeze.freeze_active).label}</div>
                <div>Review board: {getString(supervisionCommandEscalation.review_board_status, "watch")}</div>
              </div>
              <div className="mt-6 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Operator lapse: {getBooleanBadge(supervisionCommandLapse.operator_certification_lapse).label}</div>
                <div>Coverage lapse: {getBooleanBadge(supervisionCommandLapse.coverage_lapse).label}</div>
                <div>Active sessions: {String(getNumber(supervisionCommandCoverage.coverage_active_sessions, 0))}</div>
                <div>Assigned RFQs: {String(Array.isArray(supervisionCommandCoverage.coverage_assigned_rfqs) ? supervisionCommandCoverage.coverage_assigned_rfqs.length : 0)}</div>
                <div>Pending approvals: {String(Array.isArray(supervisionCommandCoverage.coverage_pending_approvals) ? supervisionCommandCoverage.coverage_pending_approvals.length : 0)}</div>
                <div>Score trend: {getString(supervisionCommandHistorySummary.score_history?.trend, "stable")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Production Operations Audit</h2>
              <p className="text-sm text-slate-400">
                Immutable audit visibility for supervised rollout actions, acknowledgements, freeze history, and institutional retention.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only audit" : "Read-only audit"}
              tone="neutral"
            />
          </div>

          {operationsAuditWarnings.length ? (
            <div className="space-y-3">
              {operationsAuditWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Production operations audit status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Audit Governance"
              tone={operationsAuditStatus === "ok" ? "ok" : operationsAuditStatus === "blocked" ? "error" : "neutral"}
              summary={`${operationsAuditGrade} • ${operationsAuditScore.toFixed(2)} • ${getString(operationsAuditHistorySummary.score_history?.trend, "stable")}`}
              items={[
                ["Status", operationsAuditStatus],
                ["Authority", operationsAuditAuthority],
                ["Score", operationsAuditScore.toFixed(2)],
                ["Grade", operationsAuditGrade],
                ["History", String(operationsAuditHistory.length)],
                ["Trend", getString(operationsAuditHistorySummary.score_history?.trend, "stable")],
                ["Latest rollout score", getNumber(operationsAuditLatestRollout?.rollout_governance_score, 0).toFixed(2)],
                ["Audit history", String(Array.isArray(operationsAuditLatest.institutional_audit_history) ? operationsAuditLatest.institutional_audit_history.length : 0)],
              ]}
            />

            <MetricPanel
              title="Audit Retention & Completeness"
              tone={operationsAuditRetention.retention_compliant && operationsAuditCompleteness.audit_completeness_ready ? "ok" : "error"}
              summary={`${Object.values(operationsAuditRetention || {}).filter(Boolean).length} retained / ${Object.values(operationsAuditCompleteness || {}).filter(Boolean).length} complete`}
              items={[
                ["Retained", getBooleanBadge(operationsAuditRetention.retention_compliant).label],
                ["Rollout retained", getBooleanBadge(operationsAuditRetention.rollout_validation_retained).label],
                ["Release retained", getBooleanBadge(operationsAuditRetention.release_certification_retained).label],
                ["Completeness", getBooleanBadge(operationsAuditCompleteness.audit_completeness_ready).label],
                ["Retention indicators", String(Object.values(operationsAuditRetention || {}).filter(Boolean).length)],
                ["Completeness indicators", String(Object.values(operationsAuditCompleteness || {}).filter(Boolean).length)],
              ]}
            />

            <MetricPanel
              title="Audit Activity"
              tone={operationsAuditFreezeHistory.some((item) => item.freeze_active) ? "error" : "ok"}
              summary={`${operationsAuditRolloutActions.length} rollout / ${operationsAuditReleaseDecisionHistory.length} release`}
              items={[
                ["Rollout actions", String(operationsAuditRolloutActions.length)],
                ["Escalations", String(operationsAuditEscalations.length)],
                ["Freeze history", String(operationsAuditFreezeHistory.length)],
                ["Overrides", String(operationsAuditOverrideHistory.length)],
                ["Operator acks", String(operationsAuditOperatorAckHistory.length)],
                ["Supervision approvals", String(operationsAuditSupervisionApprovalHistory.length)],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Operations Audit History</h3>
                <StatusBadge label={`${operationsAuditHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operationsAuditHistory.length ? (
                      operationsAuditHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.operations_audit_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.operations_audit_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.operations_audit_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No operations audit history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Audit Indicators</h3>
                <StatusBadge label={operationsAuditAuthority} tone={operationsAuditAuthority === "GO" ? "ok" : operationsAuditAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Rollout actions: {String(operationsAuditRolloutActions.length)}</div>
                <div>Escalation acknowledgements: {String(operationsAuditEscalations.length)}</div>
                <div>Freeze history: {String(operationsAuditFreezeHistory.length)}</div>
                <div>Override history: {String(operationsAuditOverrideHistory.length)}</div>
                <div>Operator acknowledgements: {String(operationsAuditOperatorAckHistory.length)}</div>
                <div>Supervision approvals: {String(operationsAuditSupervisionApprovalHistory.length)}</div>
                <div>Release decisions: {String(operationsAuditReleaseDecisionHistory.length)}</div>
                <div>Retention compliant: {getBooleanBadge(operationsAuditRetention.retention_compliant).label}</div>
                <div>Completeness ready: {getBooleanBadge(operationsAuditCompleteness.audit_completeness_ready).label}</div>
                <div>Latest release authority: {getString(operationsAuditLatestRelease?.release_authority, "WATCH")}</div>
                <div>Release status: {getString(operationsAuditLatestRelease?.certification_status, "WATCH")}</div>
                <div>Audit history entries: {String(Array.isArray(operationsAuditLatest.institutional_audit_history) ? operationsAuditLatest.institutional_audit_history.length : 0)}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Production Incident Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only incident, supervision failure, and recovery coordination visibility for supervised production operations.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only incident governance" : "Read-only incident governance"}
              tone="neutral"
            />
          </div>

          {incidentGovernanceWarnings.length ? (
            <div className="space-y-3">
              {incidentGovernanceWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Production incident governance status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Incident Governance"
              tone={incidentGovernanceStatus === "ok" ? "ok" : incidentGovernanceStatus === "blocked" ? "error" : "neutral"}
              summary={`${incidentGovernanceGrade} • ${incidentGovernanceScore.toFixed(2)}`}
              items={[
                ["Status", incidentGovernanceStatus],
                ["Authority", incidentGovernanceAuthority],
                ["Score", incidentGovernanceScore.toFixed(2)],
                ["Grade", incidentGovernanceGrade],
                ["History", String(incidentGovernanceHistoryHistory.length)],
                ["Incident history", String(Array.isArray(incidentGovernanceLatest.institutional_incident_history) ? incidentGovernanceLatest.institutional_incident_history.length : 0)],
              ]}
            />

            <MetricPanel
              title="Incident Flags"
              tone={incidentGovernanceIncidents.length || incidentGovernanceSupervisionFailures.length || incidentGovernanceEscalationFailures.length || incidentGovernanceRolloutAnomalies.length || incidentGovernanceBreaches.length ? "error" : "ok"}
              summary={`${incidentGovernanceIncidents.length} incident / ${incidentGovernanceBreaches.length} breach`}
              items={[
                ["Operational incidents", String(incidentGovernanceIncidents.length)],
                ["Supervision failures", String(incidentGovernanceSupervisionFailures.length)],
                ["Escalation failures", String(incidentGovernanceEscalationFailures.length)],
                ["Rollout anomalies", String(incidentGovernanceRolloutAnomalies.length)],
                ["Governance breaches", String(incidentGovernanceBreaches.length)],
                ["Severity flags", String(incidentGovernanceSeverity.length)],
              ]}
            />

            <MetricPanel
              title="Recovery & Retention"
              tone={incidentGovernanceRetention.retention_compliant && incidentGovernanceRecoveryReadiness.recovery_ready ? "ok" : "error"}
              summary={`${Object.values(incidentGovernanceRetention || {}).filter(Boolean).length} retained / ${Object.values(incidentGovernanceRecoveryReadiness || {}).filter(Boolean).length} ready`}
              items={[
                ["Retained", getBooleanBadge(incidentGovernanceRetention.retention_compliant).label],
                ["Recovery ready", getBooleanBadge(incidentGovernanceRecoveryReadiness.recovery_ready).label],
                ["Deployment health", getBooleanBadge(incidentGovernanceRecovery.deployment_health_ready).label],
                ["Observability", getBooleanBadge(incidentGovernanceRecovery.observability_ready).label],
                ["Freeze active", getBooleanBadge(incidentGovernanceFreeze.freeze_active).label],
                ["Completeness", getBooleanBadge(incidentGovernanceCompleteness.audit_completeness_ready).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Incident Governance History</h3>
                <StatusBadge label={`${incidentGovernanceHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incidentGovernanceHistory.length ? (
                      incidentGovernanceHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.incident_governance_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.incident_governance_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.incident_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No incident governance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Incident Indicators</h3>
                <StatusBadge label={incidentGovernanceAuthority} tone={incidentGovernanceAuthority === "GO" ? "ok" : incidentGovernanceAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Operational incidents: {String(incidentGovernanceIncidents.length)}</div>
                <div>Supervision failures: {String(incidentGovernanceSupervisionFailures.length)}</div>
                <div>Escalation failures: {String(incidentGovernanceEscalationFailures.length)}</div>
                <div>Rollout anomalies: {String(incidentGovernanceRolloutAnomalies.length)}</div>
                <div>Governance breach indicators: {String(incidentGovernanceBreaches.length)}</div>
                <div>Recovery ready: {getBooleanBadge(incidentGovernanceRecoveryReadiness.recovery_ready).label}</div>
                <div>Freeze active: {getBooleanBadge(incidentGovernanceFreeze.freeze_active).label}</div>
                <div>Retention compliant: {getBooleanBadge(incidentGovernanceRetention.retention_compliant).label}</div>
                <div>Latest analysis: {getString(incidentGovernanceLatest.analysis_id, "n/a")}</div>
                <div>History entries: {String(Array.isArray(incidentGovernanceLatest.institutional_incident_history) ? incidentGovernanceLatest.institutional_incident_history.length : 0)}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Production Continuity Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only continuity, failover, recovery rehearsal, and supervision continuity visibility for supervised production operations.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only continuity governance" : "Read-only continuity governance"}
              tone="neutral"
            />
          </div>

          {continuityGovernanceWarnings.length ? (
            <div className="space-y-3">
              {continuityGovernanceWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Production continuity governance status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Continuity Governance"
              tone={continuityGovernanceStatus === "ok" ? "ok" : continuityGovernanceStatus === "blocked" ? "error" : "neutral"}
              summary={`${continuityGovernanceGrade} • ${continuityGovernanceScore.toFixed(2)}`}
              items={[
                ["Status", continuityGovernanceStatus],
                ["Authority", continuityGovernanceAuthority],
                ["Score", continuityGovernanceScore.toFixed(2)],
                ["Grade", continuityGovernanceGrade],
                ["History", String(continuityGovernanceHistory.length)],
                ["Trend", getString(continuityGovernanceHistorySummary.score_history?.trend, "stable")],
              ]}
            />

            <MetricPanel
              title="Recovery Readiness"
              tone={continuityRecoveryDrill.length || continuityDrRehearsal.length ? "neutral" : "ok"}
              summary={`${continuityRecoveryDrill.length} drill / ${continuityDrRehearsal.length} rehearsal`}
              items={[
                ["Recovery drills", String(continuityRecoveryDrill.length)],
                ["DR rehearsals", String(continuityDrRehearsal.length)],
                ["Failover readiness", String(continuityOperatorFailover.length)],
                ["Supervision continuity", String(continuitySupervision.length)],
                ["Recovery escalation", String(continuityEscalation.length)],
                ["Recovery timing", String(continuityTiming.length)],
              ]}
            />

            <MetricPanel
              title="Freeze & Retention"
              tone={continuityRetention.retention_compliant && !continuityFreeze.some((item: Record<string, any>) => item.freeze_active) ? "ok" : "error"}
              summary={`${Object.values(continuityRetention || {}).filter(Boolean).length} retained / ${Object.values(continuityCompleteness || {}).filter(Boolean).length} complete`}
              items={[
                ["Freeze active", getBooleanBadge(continuityFreeze.some((item: Record<string, any>) => item.freeze_active)).label],
                ["Retention compliant", getBooleanBadge(continuityRetention.retention_compliant).label],
                ["Recovery ready", getBooleanBadge(continuityGovernanceLatest.operational_continuity_scoring?.score >= 85).label],
                ["Completeness ready", getBooleanBadge(continuityCompleteness.continuity_governance_history_recorded).label],
                ["History retained", getBooleanBadge(continuityRetention.institutional_continuity_history_retained).label],
                ["Latest status", getString(continuityGovernanceLatest.operational_continuity_scoring?.status, "watch")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Continuity Governance History</h3>
                <StatusBadge label={`${continuityGovernanceHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {continuityGovernanceHistory.length ? (
                      continuityGovernanceHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.continuity_governance_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.continuity_governance_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.continuity_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No continuity governance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Continuity Indicators</h3>
                <StatusBadge label={continuityGovernanceAuthority} tone={continuityGovernanceAuthority === "GO" ? "ok" : continuityGovernanceAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Recovery drill readiness: {String(continuityRecoveryDrill.length)}</div>
                <div>DR rehearsal status: {String(continuityDrRehearsal.length)}</div>
                <div>Operator failover readiness: {String(continuityOperatorFailover.length)}</div>
                <div>Supervision continuity: {String(continuitySupervision.length)}</div>
                <div>Continuity freeze: {String(continuityFreeze.length)}</div>
                <div>Recovery escalation: {String(continuityEscalation.length)}</div>
                <div>Recovery timing: {String(continuityTiming.length)}</div>
                <div>History entries: {String(Array.isArray(continuityGovernanceLatest.continuity_governance_history) ? continuityGovernanceLatest.continuity_governance_history.length : 0)}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Submission Deadline Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only oversight for cutoff tracking, upload windows, courier timing, portal timeout, escalation timing, and late-submission prevention.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only deadline governance" : "Read-only deadline governance"}
              tone="neutral"
            />
          </div>

          {deadlineWarnings.length ? (
            <div className="space-y-3">
              {deadlineWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Submission deadlines are within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Deadline Governance"
              tone={getString(deadlineLatest.deadline_governance_status, "watch") === "ok" ? "ok" : getString(deadlineLatest.deadline_governance_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(deadlineLatest.timing_readiness_score, 0).toFixed(2)} timing readiness`}
              items={[
                ["Status", getString(deadlineLatest.deadline_governance_status, "watch")],
                ["Cutoff", getString(deadlineLatest.latest_deadline_governance?.submission_cutoff_tracking?.deadline, "n/a")],
                ["Upload window", getBooleanBadge(deadlineLatest.latest_deadline_governance?.upload_window_governance?.upload_window_open).label],
                ["Courier timing", getBooleanBadge(deadlineLatest.latest_deadline_governance?.courier_timing_governance?.courier_timing_warning ? false : true).label],
                ["Portal timeout", getBooleanBadge(deadlineLatest.latest_deadline_governance?.portal_timeout_governance?.portal_timeout_warning ? false : true).label],
                ["Escalation timing", getBooleanBadge(deadlineLatest.latest_deadline_governance?.escalation_timing_governance?.escalation_timing_warning ? false : true).label],
                ["Late prevention", getBooleanBadge(deadlineLatest.latest_deadline_governance?.late_submission_prevention ? false : true).label],
              ]}
            />

            <MetricPanel
              title="Deadline Warnings"
              tone={(deadlineLatest.latest_deadline_governance?.deadline_risk_warnings || []).length || Object.values(deadlineLatest.latest_deadline_governance?.overdue_submission_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${(deadlineLatest.latest_deadline_governance?.deadline_risk_warnings || []).length} risk / ${Object.values(deadlineLatest.latest_deadline_governance?.overdue_submission_indicators || {}).filter(Boolean).length} overdue`}
              items={[
                ["Risk warnings", String((deadlineLatest.latest_deadline_governance?.deadline_risk_warnings || []).length)],
                ["Overdue", String(Object.values(deadlineLatest.latest_deadline_governance?.overdue_submission_indicators || {}).filter(Boolean).length)],
                ["Congestion", String(Object.values(deadlineLatest.latest_deadline_governance?.congestion_window_indicators || {}).filter(Boolean).length)],
                ["Bundle ready", getBooleanBadge(deadlineLatest.latest_deadline_governance?.congestion_window_indicators?.submission_bundle_ready).label],
                ["Upload ready", getBooleanBadge(deadlineLatest.latest_deadline_governance?.congestion_window_indicators?.upload_package_ready).label],
                ["Physical ready", getBooleanBadge(deadlineLatest.latest_deadline_governance?.congestion_window_indicators?.physical_submission_ready).label],
              ]}
            />

            <MetricPanel
              title="Deadline Supervision"
              tone={getBooleanBadge(deadlineLatest.latest_deadline_governance?.governance_approval_gating).tone}
              summary={getBooleanBadge(deadlineLatest.latest_deadline_governance?.governance_approval_gating).label}
              items={[
                ["Supervision OK", getBooleanBadge(deadlineLatest.latest_deadline_governance?.governance_approval_gating).label],
                ["Readiness status", getString(deadlineLatest.latest_deadline_governance?.readiness_declaration_status, "WATCH")],
                ["Operator ready", String(getNumber(deadlineLatest.operator_assignment_readiness_summary?.ready_count, 0))],
                ["Not ready", String(getNumber(deadlineLatest.operator_assignment_readiness_summary?.not_ready_count, 0))],
                ["Approval gate", String(getNumber(deadlineLatest.operator_assignment_readiness_summary?.governance_approval_gate_count, 0))],
                ["Decision", getString(deadlineLatest.latest_deadline_governance?.deadline_governance_decision, "watch_deadline_governance")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Deadline Decisions</h3>
                <StatusBadge label={`${Array.isArray(deadlineLatest.deadline_governance_history) ? deadlineLatest.deadline_governance_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Cutoff</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(deadlineLatest.deadline_governance_history) && deadlineLatest.deadline_governance_history.length ? (
                      deadlineLatest.deadline_governance_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.deadline_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.deadline_governance_decision, "watch_deadline_governance")}
                              tone={item.deadline_governance_decision === "approve_deadline_governance" ? "ok" : item.deadline_governance_decision === "watch_deadline_governance" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getString(item.submission_cutoff_tracking?.deadline, "n/a")}</td>
                          <td className="p-3 text-right">{getNumber(item.timing_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No deadline governance decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Deadline History</h3>
                <StatusBadge label={`${Array.isArray(deadlineHistory) ? deadlineHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Warnings</th>
                      <th className="p-3 text-right">Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deadlineHistory.length ? (
                      deadlineHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.deadline_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.deadline_governance_status, "watch")}
                              tone={item.deadline_governance_status === "ok" ? "ok" : item.deadline_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{String((item.deadline_risk_warnings || []).length)}</td>
                          <td className="p-3 text-right">{getNumber(item.timing_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No deadline history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Bid Packaging Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only oversight for submission bundle completeness, ZIP integrity, print packs, folder structure, naming, and upload readiness.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only packaging governance" : "Read-only packaging governance"}
              tone="neutral"
            />
          </div>

          {packagingWarnings.length ? (
            <div className="space-y-3">
              {packagingWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Bid packaging is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Packaging Governance"
              tone={getString(packagingLatest.packaging_governance_status, "watch") === "ok" ? "ok" : getString(packagingLatest.packaging_governance_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(packagingLatest.packaging_readiness_score, 0).toFixed(2)} readiness score`}
              items={[
                ["Status", getString(packagingLatest.packaging_governance_status, "watch")],
                ["Bundle complete", getBooleanBadge(packagingLatest.latest_packaging_governance?.submission_bundle_completeness).label],
                ["Attachment valid", getBooleanBadge(packagingLatest.latest_packaging_governance?.attachment_bundle_validation).label],
                ["ZIP integrity", getBooleanBadge(packagingLatest.latest_packaging_governance?.zip_package_integrity).label],
                ["Print pack", getBooleanBadge(packagingLatest.latest_packaging_governance?.print_pack_readiness).label],
                ["Folder structure", getBooleanBadge(packagingLatest.latest_packaging_governance?.folder_structure_validation).label],
                ["Naming convention", getBooleanBadge(packagingLatest.latest_packaging_governance?.naming_convention_governance).label],
                ["Upload package", getBooleanBadge(packagingLatest.latest_packaging_governance?.upload_package_readiness).label],
              ]}
            />

            <MetricPanel
              title="Packaging Warnings"
              tone={(packagingLatest.latest_packaging_governance?.incomplete_package_warnings || []).length || (packagingLatest.latest_packaging_governance?.missing_attachment_warnings || []).length || Object.values(packagingLatest.latest_packaging_governance?.malformed_bundle_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${(packagingLatest.latest_packaging_governance?.incomplete_package_warnings || []).length} incomplete / ${(packagingLatest.latest_packaging_governance?.missing_attachment_warnings || []).length} missing`}
              items={[
                ["Incomplete warnings", String((packagingLatest.latest_packaging_governance?.incomplete_package_warnings || []).length)],
                ["Missing attachments", String((packagingLatest.latest_packaging_governance?.missing_attachment_warnings || []).length)],
                ["Malformed indicators", String(Object.values(packagingLatest.latest_packaging_governance?.malformed_bundle_indicators || {}).filter(Boolean).length)],
                ["Bundle complete", getBooleanBadge(packagingLatest.latest_packaging_governance?.submission_bundle_completeness).label],
                ["Attachment valid", getBooleanBadge(packagingLatest.latest_packaging_governance?.attachment_bundle_validation).label],
                ["Upload ready", getBooleanBadge(packagingLatest.latest_packaging_governance?.upload_package_readiness).label],
              ]}
            />

            <MetricPanel
              title="Packaging Supervision"
              tone={getBooleanBadge(packagingLatest.latest_packaging_governance?.governance_approval_gating).tone}
              summary={getBooleanBadge(packagingLatest.latest_packaging_governance?.governance_approval_gating).label}
              items={[
                ["Supervision OK", getBooleanBadge(packagingLatest.latest_packaging_governance?.governance_approval_gating).label],
                ["Readiness status", getString(packagingLatest.latest_packaging_governance?.readiness_declaration_status, "WATCH")],
                ["Operator ready", String(getNumber(packagingLatest.operator_assignment_readiness_summary?.ready_count, 0))],
                ["Not ready", String(getNumber(packagingLatest.operator_assignment_readiness_summary?.not_ready_count, 0))],
                ["Approval gate", String(getNumber(packagingLatest.operator_assignment_readiness_summary?.governance_approval_gate_count, 0))],
                ["Decision", getString(packagingLatest.latest_packaging_governance?.packaging_governance_decision, "watch_packaging_governance")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Packaging Decisions</h3>
                <StatusBadge label={`${Array.isArray(packagingLatest.packaging_governance_history) ? packagingLatest.packaging_governance_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Bundle</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(packagingLatest.packaging_governance_history) && packagingLatest.packaging_governance_history.length ? (
                      packagingLatest.packaging_governance_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.packaging_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.packaging_governance_decision, "watch_packaging_governance")}
                              tone={item.packaging_governance_decision === "approve_packaging_governance" ? "ok" : item.packaging_governance_decision === "watch_packaging_governance" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getBooleanBadge(item.submission_bundle_completeness).label}</td>
                          <td className="p-3 text-right">{getNumber(item.packaging_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No packaging governance decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Packaging History</h3>
                <StatusBadge label={`${Array.isArray(packagingHistory) ? packagingHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Warnings</th>
                      <th className="p-3 text-right">Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {packagingHistory.length ? (
                      packagingHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.packaging_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.packaging_governance_status, "watch")}
                              tone={item.packaging_governance_status === "ok" ? "ok" : item.packaging_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{String((item.incomplete_package_warnings || []).length)}</td>
                          <td className="p-3 text-right">{getNumber(item.packaging_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No packaging history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Returnable Schedule Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only oversight for annexures, mandatory returnables, pricing schedules, declarations, technical schedules, compulsory forms, and attachments.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only returnable governance" : "Read-only returnable governance"}
              tone="neutral"
            />
          </div>

          {returnableWarnings.length ? (
            <div className="space-y-3">
              {returnableWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Returnable schedules are within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Returnable Governance"
              tone={getString(returnableLatest.returnable_governance_status, "watch") === "ok" ? "ok" : getString(returnableLatest.returnable_governance_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(returnableLatest.bid_response_completeness_score, 0).toFixed(2)} completeness score`}
              items={[
                ["Status", getString(returnableLatest.returnable_governance_status, "watch")],
                ["Annexure", getString(returnableLatest.latest_returnable_governance?.annexure_classification, "annexure_missing")],
                ["Mandatory returnable", getBooleanBadge(returnableLatest.latest_returnable_governance?.mandatory_returnable_detection).label],
                ["Pricing schedule", getBooleanBadge(returnableLatest.latest_returnable_governance?.pricing_schedule_completeness).label],
                ["Declaration", getBooleanBadge(returnableLatest.latest_returnable_governance?.declaration_completeness).label],
                ["Technical schedule", getBooleanBadge(returnableLatest.latest_returnable_governance?.technical_schedule_completeness).label],
                ["Compulsory form", getBooleanBadge(returnableLatest.latest_returnable_governance?.compulsory_form_readiness).label],
                ["Mandatory attachment", getBooleanBadge(returnableLatest.latest_returnable_governance?.mandatory_attachment_completeness).label],
              ]}
            />

            <MetricPanel
              title="Returnable Warnings"
              tone={(returnableLatest.latest_returnable_governance?.incomplete_returnable_warnings || []).length || (returnableLatest.latest_returnable_governance?.unsigned_returnable_warnings || []).length || returnableMissingCount ? "error" : "ok"}
              summary={`${(returnableLatest.latest_returnable_governance?.incomplete_returnable_warnings || []).length} incomplete / ${(returnableLatest.latest_returnable_governance?.unsigned_returnable_warnings || []).length} unsigned`}
              items={[
                ["Incomplete warnings", String((returnableLatest.latest_returnable_governance?.incomplete_returnable_warnings || []).length)],
                ["Missing annexures", String(returnableMissingCount)],
                ["Unsigned warnings", String((returnableLatest.latest_returnable_governance?.unsigned_returnable_warnings || []).length)],
                ["Pricing complete", getBooleanBadge(returnableLatest.latest_returnable_governance?.pricing_schedule_completeness).label],
                ["Declaration complete", getBooleanBadge(returnableLatest.latest_returnable_governance?.declaration_completeness).label],
                ["Technical complete", getBooleanBadge(returnableLatest.latest_returnable_governance?.technical_schedule_completeness).label],
              ]}
            />

            <MetricPanel
              title="Returnable Supervision"
              tone={getBooleanBadge(returnableLatest.latest_returnable_governance?.governance_approval_gating).tone}
              summary={getBooleanBadge(returnableLatest.latest_returnable_governance?.governance_approval_gating).label}
              items={[
                ["Supervision OK", getBooleanBadge(returnableLatest.latest_returnable_governance?.governance_approval_gating).label],
                ["Readiness status", getString(returnableLatest.latest_returnable_governance?.readiness_declaration_status, "WATCH")],
                ["Operator ready", String(getNumber(returnableLatest.operator_assignment_readiness_summary?.ready_count, 0))],
                ["Not ready", String(getNumber(returnableLatest.operator_assignment_readiness_summary?.not_ready_count, 0))],
                ["Approval gate", String(getNumber(returnableLatest.operator_assignment_readiness_summary?.governance_approval_gate_count, 0))],
                ["Decision", getString(returnableLatest.latest_returnable_governance?.returnable_governance_decision, "watch_returnable_governance")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Returnable Decisions</h3>
                <StatusBadge label={`${Array.isArray(returnableLatest.returnable_governance_history) ? returnableLatest.returnable_governance_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Annexure</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(returnableLatest.returnable_governance_history) && returnableLatest.returnable_governance_history.length ? (
                      returnableLatest.returnable_governance_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.returnable_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.returnable_governance_decision, "watch_returnable_governance")}
                              tone={item.returnable_governance_decision === "approve_returnable_governance" ? "ok" : item.returnable_governance_decision === "watch_returnable_governance" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getString(item.annexure_classification, "annexure_missing")}</td>
                          <td className="p-3 text-right">{getNumber(item.bid_response_completeness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No returnable governance decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Returnable History</h3>
                <StatusBadge label={`${Array.isArray(returnableHistory) ? returnableHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Incomplete</th>
                      <th className="p-3 text-right">Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {returnableHistory.length ? (
                      returnableHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.returnable_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.returnable_governance_status, "watch")}
                              tone={item.returnable_governance_status === "ok" ? "ok" : item.returnable_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{String((item.incomplete_returnable_warnings || []).length)}</td>
                          <td className="p-3 text-right">{getNumber(item.bid_response_completeness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No returnable history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Procurement Compliance Artifacts</h2>
              <p className="text-sm text-slate-400">
                Read-only oversight for tax clearance, BBBEE, CIDB, COIDA, NHBRC, company registration, bank letters, and certificate validity.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only compliance governance" : "Read-only compliance governance"}
              tone="neutral"
            />
          </div>

          {complianceWarnings.length ? (
            <div className="space-y-3">
              {complianceWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Procurement compliance artifacts are within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Compliance Governance"
              tone={getString(complianceLatest.compliance_artifact_governance_status, "watch") === "ok" ? "ok" : getString(complianceLatest.compliance_artifact_governance_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(complianceLatest.compliance_readiness_score, 0).toFixed(2)} readiness score`}
              items={[
                ["Status", getString(complianceLatest.compliance_artifact_governance_status, "watch")],
                ["Tax clearance", getBooleanBadge(complianceLatest.latest_compliance_governance?.tax_clearance_present).label],
                ["BBBEE", getBooleanBadge(complianceLatest.latest_compliance_governance?.bbbee_present).label],
                ["CIDB", getBooleanBadge(complianceLatest.latest_compliance_governance?.cidb_present).label],
                ["COIDA", getBooleanBadge(complianceLatest.latest_compliance_governance?.coida_present).label],
                ["NHBRC", getBooleanBadge(complianceLatest.latest_compliance_governance?.nhbrc_present).label],
                ["Company reg.", getBooleanBadge(complianceLatest.latest_compliance_governance?.company_registration_present).label],
                ["Bank letter", getBooleanBadge(complianceLatest.latest_compliance_governance?.bank_letter_present).label],
              ]}
            />

            <MetricPanel
              title="Artifact Integrity"
              tone={(complianceLatest.latest_compliance_governance?.missing_artifact_warnings || []).length || Object.values(complianceLatest.latest_compliance_governance?.invalid_artifact_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${(complianceLatest.latest_compliance_governance?.missing_artifact_warnings || []).length} missing / ${Object.values(complianceLatest.latest_compliance_governance?.invalid_artifact_indicators || {}).filter(Boolean).length} invalid`}
              items={[
                ["Missing warnings", String((complianceLatest.latest_compliance_governance?.missing_artifact_warnings || []).length)],
                ["Invalid indicators", String(Object.values(complianceLatest.latest_compliance_governance?.invalid_artifact_indicators || {}).filter(Boolean).length)],
                ["Expiry warnings", String((complianceLatest.latest_compliance_governance?.expiry_warnings || []).length)],
                ["Tax expiry", getBooleanBadge(complianceLatest.latest_compliance_governance?.certificate_expiry_governance?.tax_clearance?.expiry_warning).label],
                ["BBBEE expiry", getBooleanBadge(complianceLatest.latest_compliance_governance?.certificate_expiry_governance?.bbbee?.expiry_warning).label],
                ["CIDB expiry", getBooleanBadge(complianceLatest.latest_compliance_governance?.certificate_expiry_governance?.cidb?.expiry_warning).label],
              ]}
            />

            <MetricPanel
              title="Compliance Supervision"
              tone={getBooleanBadge(complianceLatest.latest_compliance_governance?.governance_approval_gating).tone}
              summary={getBooleanBadge(complianceLatest.latest_compliance_governance?.governance_approval_gating).label}
              items={[
                ["Supervision OK", getBooleanBadge(complianceLatest.latest_compliance_governance?.governance_approval_gating).label],
                ["Readiness status", getString(complianceLatest.latest_compliance_governance?.readiness_declaration_status, "WATCH")],
                ["Operator ready", String(getNumber(complianceLatest.operator_assignment_readiness_summary?.ready_count, 0))],
                ["Not ready", String(getNumber(complianceLatest.operator_assignment_readiness_summary?.not_ready_count, 0))],
                ["Approval gate", String(getNumber(complianceLatest.operator_assignment_readiness_summary?.governance_approval_gate_count, 0))],
                ["Decision", getString(complianceLatest.latest_compliance_governance?.compliance_governance_decision, "watch_compliance_governance")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Compliance Decisions</h3>
                <StatusBadge label={`${Array.isArray(complianceLatest.compliance_governance_decision_history) ? complianceLatest.compliance_governance_decision_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Artifacts</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(complianceLatest.compliance_governance_decision_history) && complianceLatest.compliance_governance_decision_history.length ? (
                      complianceLatest.compliance_governance_decision_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.compliance_artifact_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.compliance_governance_decision, "watch_compliance_governance")}
                              tone={item.compliance_governance_decision === "approve_compliance_governance" ? "ok" : item.compliance_governance_decision === "watch_compliance_governance" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">
                            {[
                              getBooleanBadge(item.tax_clearance_required).label,
                              getBooleanBadge(item.bbbee_required).label,
                              getBooleanBadge(item.cidb_required).label,
                              getBooleanBadge(item.coida_required).label,
                            ].join(" / ")}
                          </td>
                          <td className="p-3 text-right">{getNumber(item.compliance_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No compliance governance decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Compliance History</h3>
                <StatusBadge label={`${Array.isArray(complianceHistory) ? complianceHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Expiry</th>
                      <th className="p-3 text-right">Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {complianceHistory.length ? (
                      complianceHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.compliance_artifact_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.compliance_artifact_governance_status, "watch")}
                              tone={item.compliance_artifact_governance_status === "ok" ? "ok" : item.compliance_artifact_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{String((item.expiry_warnings || []).length)}</td>
                          <td className="p-3 text-right">{getNumber(item.compliance_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No compliance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Supervised RFQ Intake Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only intake classification, pilot-scope enforcement, and operator assignment readiness for controlled pilot RFQs.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only intake" : "Read-only intake"}
              tone="neutral"
            />
          </div>

          {intakeWarnings.length ? (
            <div className="space-y-3">
              {intakeWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Supervised RFQ intake governance is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Intake Summary"
              tone={getString(intakeLatest.intake_status, "watch") === "ok" ? "ok" : getString(intakeLatest.intake_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(intakeLatest.intake_eligibility_score, 0).toFixed(2)} intake score`}
              items={[
                ["Status", getString(intakeLatest.intake_status, "watch")],
                ["Eligibility grade", getString(intakeLatest.intake_eligibility_grade, "watch")],
                ["Governance decisions", String(Array.isArray(intakeLatest.governance_intake_decisions) ? intakeLatest.governance_intake_decisions.length : 0)],
                ["Restricted warnings", String(Array.isArray(intakeLatest.restricted_category_warnings) ? intakeLatest.restricted_category_warnings.length : 0)],
                ["Scope valid count", String(getNumber(intakeLatest.pilot_scope_enforcement?.pilot_scope_valid_count, 0))],
                ["Scope invalid count", String(getNumber(intakeLatest.pilot_scope_enforcement?.pilot_scope_invalid_count, 0))],
              ]}
            />

            <MetricPanel
              title="Supervision Capacity"
              tone={getBooleanBadge(intakeLatest.supervision_capacity_indicators?.coverage_ok).tone}
              summary={getBooleanBadge(intakeLatest.supervision_capacity_indicators?.coverage_ok).label}
              items={[
                ["Coverage OK", getBooleanBadge(intakeLatest.supervision_capacity_indicators?.coverage_ok).label],
                ["Capacity warnings", String(getNumber(intakeLatest.supervision_capacity_indicators?.capacity_warning_count, 0))],
                ["Operator ready", String(getNumber(intakeLatest.operator_assignment_readiness_summary?.ready_count, 0))],
                ["Not ready", String(getNumber(intakeLatest.operator_assignment_readiness_summary?.not_ready_count, 0))],
                ["Approval gate", String(getNumber(intakeLatest.operator_assignment_readiness_summary?.governance_approval_gate_count, 0))],
                ["Approval block", String(getNumber(intakeLatest.operator_assignment_readiness_summary?.governance_approval_block_count, 0))],
              ]}
            />

            <MetricPanel
              title="Governance Gates"
              tone={getString(intakeLatest.latest_intake?.intake_decision, "watch_intake") === "approve_intake" ? "ok" : getString(intakeLatest.latest_intake?.intake_decision, "watch_intake") === "watch_intake" ? "neutral" : "error"}
              summary={getString(intakeLatest.latest_intake?.intake_decision, "watch_intake")}
              items={[
                ["Latest RFQ", getString(intakeLatest.latest_intake?.rfq_id, "n/a")],
                ["Category", getString(intakeLatest.latest_intake?.rfq_category, "unknown")],
                ["Pilot scope", getBooleanBadge(intakeLatest.latest_intake?.pilot_scope_enforced).label],
                ["Restricted", getBooleanBadge(intakeLatest.latest_intake?.restricted_category).label],
                ["Gating", getBooleanBadge(intakeLatest.latest_intake?.governance_approval_gating).label],
                ["Assignment", getBooleanBadge(intakeLatest.latest_intake?.operator_assignment_readiness).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Restricted Category Warnings</h3>
                <StatusBadge label={`${Array.isArray(intakeLatest.restricted_category_warnings) ? intakeLatest.restricted_category_warnings.length : 0} warning(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Category</th>
                      <th className="p-3 text-left">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(intakeLatest.governance_intake_decisions) && intakeLatest.governance_intake_decisions.length ? (
                      intakeLatest.governance_intake_decisions.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.intake_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.intake_decision, "watch_intake")}
                              tone={item.intake_decision === "approve_intake" ? "ok" : item.intake_decision === "watch_intake" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getString(item.rfq_category, "unknown")}</td>
                          <td className="p-3 text-slate-400">{Array.isArray(item.intake_decision_reason) ? item.intake_decision_reason.join("; ") : "n/a"}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No supervised intake decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Intake Decision History</h3>
                <StatusBadge label={`${Array.isArray(intakeHistory) ? intakeHistory.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {intakeHistory.length ? (
                      intakeHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.intake_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.intake_id, "n/a")}</td>
                          <td className="p-3">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.intake_status, "watch")}
                              tone={item.intake_status === "ok" ? "ok" : item.intake_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3 text-right">{getNumber(item.intake_eligibility_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No intake decision history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Supervised Pilot Operator Sessions</h2>
              <p className="text-sm text-slate-400">
                Read-only operator session coverage, acknowledgements, approvals, and supervision windows.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only sessions" : "Read-only sessions"}
              tone="neutral"
            />
          </div>

          {operatorSessionWarnings.length ? (
            <div className="space-y-3">
              {operatorSessionWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Supervised operator sessions are within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Session Summary"
              tone={getString(operatorSessionsLatest.operator_session_status, "watch") === "ok" ? "ok" : "neutral"}
              summary={`${getNumber(operatorSessionsLatest.operator_supervision_score, 0).toFixed(2)} supervision score`}
              items={[
                ["Active sessions", String(getNumber(operatorSessionsLatest.active_operator_session_count, 0))],
                ["Session status", getString(operatorSessionsLatest.operator_session_status, "watch")],
                ["Coverage", `${getNumber(operatorSessionsLatest.supervision_coverage?.coverage_rate, 0).toFixed(2)}%`],
                ["Workload", String(getNumber(operatorSessionsLatest.operator_workload?.assigned_rfq_count, 0))],
                ["Pending approvals", String(getNumber(operatorSessionsLatest.operator_workload?.pending_approval_count, 0))],
                ["Supervision grade", getString(operatorSessionsLatest.supervision_grade, "watch")],
              ]}
            />

            <MetricPanel
              title="Readiness & Coverage"
              tone={getString(operatorSessionsLatest.readiness_declaration_status, "WATCH") === "READY_FOR_CONTROLLED_PILOT" ? "ok" : "neutral"}
              summary={getString(operatorSessionsLatest.readiness_declaration_status, "WATCH")}
              items={[
                ["Declaration grade", getString(operatorSessionsLatest.readiness_declaration_grade, "watch")],
                ["Declaration score", getNumber(operatorSessionsLatest.readiness_declaration_score, 0).toFixed(2)],
                ["Coverage rate", `${getNumber(operatorSessionsLatest.supervision_coverage?.coverage_rate, 0).toFixed(2)}%`],
                ["Acknowledged", getBooleanBadge(operatorSessionsLatest.operator_acknowledgement?.acknowledged).label],
                ["Sequence match", getBooleanBadge(operatorSessionsLatest.supervision_coverage?.approved_sequence_matches).label],
                ["Window active", getBooleanBadge(operatorSessionsLatest.supervision_window?.active).label],
              ]}
            />

            <MetricPanel
              title="Approvals & Escalations"
              tone={Array.isArray(operatorSessionsLatest.pending_approval_checkpoints) && operatorSessionsLatest.pending_approval_checkpoints.length ? "error" : "ok"}
              summary={`${Array.isArray(operatorSessionsLatest.pending_approval_checkpoints) ? operatorSessionsLatest.pending_approval_checkpoints.length : 0} pending checkpoint(s)`}
              items={[
                ["SLA within limit", getBooleanBadge(operatorSessionsLatest.escalation_sla_tracking?.within_sla).label],
                ["Operator", getString(operatorSessionsLatest.operator_name, "staging-governance-operator")],
                ["Role", getString(operatorSessionsLatest.operator_role, "governance_reviewer")],
                ["Active RFQs", String(getNumber(operatorSessionsLatest.active_rfq_count, 0))],
                ["Unattended warnings", String(Array.isArray(operatorSessionsLatest.unattended_rfq_warnings) ? operatorSessionsLatest.unattended_rfq_warnings.length : 0)],
                ["Latest session", getString(operatorSessionsLatest.operator_session_id, "n/a")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Assigned RFQs</h3>
                <StatusBadge label={`${Array.isArray(operatorSessionsLatest.supervised_rfq_assignments) ? operatorSessionsLatest.supervised_rfq_assignments.length : 0} assignment(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">State</th>
                      <th className="p-3 text-left">Assigned</th>
                      <th className="p-3 text-left">Source cycle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(operatorSessionsLatest.supervised_rfq_assignments) && operatorSessionsLatest.supervised_rfq_assignments.length ? (
                      operatorSessionsLatest.supervised_rfq_assignments.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.rfq_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">{getString(item.supervision_state, "assigned")}</td>
                          <td className="p-3 text-slate-400">{getString(item.assigned_at, "n/a")}</td>
                          <td className="p-3 text-slate-400">{getString(item.source_cycle_id, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No supervised RFQ assignments are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Operator Session History</h3>
                <StatusBadge label={`${operatorSessionsHistory.length} session(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Session</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Coverage</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operatorSessionsHistory.length ? (
                      operatorSessionsHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.operator_session_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.operator_session_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.status, "watch")}
                              tone={item.status === "active" ? "ok" : item.status === "blocked" ? "error" : "neutral"}
                            />
                          </td>
                          <td className="p-3 text-right">{getNumber(item.operator_supervision_score, 0).toFixed(2)}</td>
                          <td className="p-3">{getNumber(item.supervision_coverage?.coverage_rate, 0).toFixed(2)}%</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No operator session history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Physical Submission Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only classification and readiness checks for RFQs that require courier, manual delivery, printing, signatures, or sealing.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only physical submission" : "Read-only physical submission"}
              tone="neutral"
            />
          </div>

          {physicalSubmissionWarnings.length ? (
            <div className="space-y-3">
              {physicalSubmissionWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Physical submission governance is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Physical Governance"
              tone={getString(physicalSubmissionLatest.physical_rfq_governance_status, "watch") === "ok" ? "ok" : getString(physicalSubmissionLatest.physical_rfq_governance_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(physicalSubmissionLatest.physical_submission_readiness_score, 0).toFixed(2)} readiness score`}
              items={[
                ["Status", getString(physicalSubmissionLatest.physical_rfq_governance_status, "watch")],
                ["Classification", getString(physicalSubmissionLatest.physical_submission_classification, "physical_delivery")],
                ["Physical RFQs", String(getNumber(physicalSubmissionLatest.physical_submission_required_count, 0))],
                ["Readiness decisions", String(Array.isArray(physicalSubmissionLatest.physical_submission_decision_history) ? physicalSubmissionLatest.physical_submission_decision_history.length : 0)],
                ["Gate count", String(getNumber(physicalSubmissionLatest.governance_approval_gate_count, 0))],
                ["Ready count", String(getNumber(physicalSubmissionLatest.operator_assignment_ready_count, 0))],
              ]}
            />

            <MetricPanel
              title="Chain of Custody"
              tone={getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.chain_of_custody_tracking?.chain_of_custody_present).tone}
              summary={getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.chain_of_custody_tracking?.chain_of_custody_present).label}
              items={[
                ["Custody present", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.chain_of_custody_tracking?.chain_of_custody_present).label],
                ["Handoff ok", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.chain_of_custody_tracking?.handoff_tracking_ok).label],
                ["POD expected", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.pod_evidence_placeholders?.pod_placeholder_required).label],
                ["POD present", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.pod_evidence_placeholders?.pod_placeholder_present).label],
                ["Manual handoff", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.manual_handoff_tracking?.manual_handoff_present).label],
                ["Manual route", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.courier_manual_delivery_routing?.manual_delivery_required).label],
              ]}
            />

            <MetricPanel
              title="Pack & Proof Readiness"
              tone={getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.submission_pack_readiness).tone}
              summary={getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.submission_pack_readiness).label}
              items={[
                ["Pack ready", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.submission_pack_readiness).label],
                ["Printing required", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.printing_signature_sealing_requirements?.requires_printing).label],
                ["Signature required", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.printing_signature_sealing_requirements?.requires_signature).label],
                ["Sealing required", getBooleanBadge(physicalSubmissionLatest.latest_physical_submission?.printing_signature_sealing_requirements?.requires_sealing).label],
                ["Deadline warnings", String(Array.isArray(physicalSubmissionLatest.latest_physical_submission?.delivery_deadline_warnings) ? physicalSubmissionLatest.latest_physical_submission?.delivery_deadline_warnings.length : 0)],
                ["Proof warnings", String(Array.isArray(physicalSubmissionLatest.latest_physical_submission?.missing_proof_warnings) ? physicalSubmissionLatest.latest_physical_submission?.missing_proof_warnings.length : 0)],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Physical Submission Decisions</h3>
                <StatusBadge label={`${Array.isArray(physicalSubmissionLatest.physical_submission_decision_history) ? physicalSubmissionLatest.physical_submission_decision_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Classification</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(physicalSubmissionLatest.physical_submission_decision_history) && physicalSubmissionLatest.physical_submission_decision_history.length ? (
                      physicalSubmissionLatest.physical_submission_decision_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.physical_submission_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.decision, "watch_physical_submission")}
                              tone={item.decision === "approve_physical_submission" ? "ok" : item.decision === "watch_physical_submission" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getString(physicalSubmissionLatest.physical_submission_classification, "physical_delivery")}</td>
                          <td className="p-3 text-right">{getNumber(item.score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No physical submission decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Physical Submission History</h3>
                <StatusBadge label={`${Array.isArray(physicalSubmissionHistory) ? physicalSubmissionHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Handoff</th>
                      <th className="p-3 text-right">Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {physicalSubmissionHistory.length ? (
                      physicalSubmissionHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.physical_submission_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.physical_rfq_governance_status, "watch")}
                              tone={item.physical_rfq_governance_status === "ok" ? "ok" : item.physical_rfq_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getBooleanBadge(item.manual_handoff_tracking?.manual_handoff_present).label}</td>
                          <td className="p-3 text-right">{getNumber(item.physical_submission_readiness_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No physical submission history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Handwritten & Signature Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only oversight for wet signatures, handwritten declarations, witnesses, commissioner requirements, affidavits, and manual attestation.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only signature governance" : "Read-only signature governance"}
              tone="neutral"
            />
          </div>

          {signatureWarnings.length ? (
            <div className="space-y-3">
              {signatureWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Signature governance is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Signature Governance"
              tone={getString(signatureLatest.signature_governance_status, "watch") === "ok" ? "ok" : getString(signatureLatest.signature_governance_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(signatureLatest.signature_governance_score, 0).toFixed(2)} governance score`}
              items={[
                ["Status", getString(signatureLatest.signature_governance_status, "watch")],
                ["Wet signature", getBooleanBadge(signatureLatest.latest_signature_governance?.wet_signature_required).label],
                ["Handwritten", getBooleanBadge(signatureLatest.latest_signature_governance?.handwritten_declaration_required).label],
                ["Witness", getBooleanBadge(signatureLatest.latest_signature_governance?.witness_required).label],
                ["Commissioner", getBooleanBadge(signatureLatest.latest_signature_governance?.commissioner_required).label],
                ["Affidavit", getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_required).label],
                ["Operator ready", String(getNumber(signatureLatest.operator_assignment_readiness_summary?.ready_count, 0))],
                ["Not ready", String(getNumber(signatureLatest.operator_assignment_readiness_summary?.not_ready_count, 0))],
              ]}
            />

            <MetricPanel
              title="Human Completion"
              tone={getBooleanBadge(signatureLatest.latest_signature_governance?.signature_completion_supervision?.signature_supervision_ok).tone}
              summary={getBooleanBadge(signatureLatest.latest_signature_governance?.signature_completion_supervision?.signature_supervision_ok).label}
              items={[
                ["Supervision OK", getBooleanBadge(signatureLatest.latest_signature_governance?.signature_completion_supervision?.signature_supervision_ok).label],
                ["Readiness OK", getBooleanBadge(signatureLatest.latest_signature_governance?.signature_completion_supervision?.readiness_ok).label],
                ["Human required", getBooleanBadge(signatureLatest.latest_signature_governance?.signature_completion_supervision?.signature_supervision_required).label],
                ["Unsigned docs", String(Object.values(signatureLatest.latest_signature_governance?.unsigned_document_indicators || {}).filter(Boolean).length)],
                ["Manual attestation", getBooleanBadge(signatureLatest.latest_signature_governance?.manual_attestation_required).label],
                ["Attestation routing", getBooleanBadge(signatureLatest.latest_signature_governance?.manual_attestation_routing?.manual_attestation_route_required).label],
              ]}
            />

            <MetricPanel
              title="Affidavit & Proof"
              tone={getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_readiness_indicators?.affidavit_present).tone}
              summary={getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_readiness_indicators?.affidavit_present).label}
              items={[
                ["Affidavit required", getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_readiness_indicators?.affidavit_required).label],
                ["Affidavit present", getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_readiness_indicators?.affidavit_present).label],
                ["Commissioner required", getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_readiness_indicators?.commissioner_required).label],
                ["Witness required", getBooleanBadge(signatureLatest.latest_signature_governance?.affidavit_readiness_indicators?.witness_required).label],
                ["Gate count", String(getNumber(signatureLatest.operator_assignment_readiness_summary?.governance_approval_gate_count, 0))],
                ["Ready count", String(getNumber(signatureLatest.operator_assignment_readiness_summary?.ready_count, 0))],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Signature Decisions</h3>
                <StatusBadge label={`${Array.isArray(signatureLatest.signature_governance_decision_history) ? signatureLatest.signature_governance_decision_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Type</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(signatureLatest.signature_governance_decision_history) && signatureLatest.signature_governance_decision_history.length ? (
                      signatureLatest.signature_governance_decision_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.signature_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.signature_decision, "watch_signature_governance")}
                              tone={item.signature_decision === "approve_signature_governance" ? "ok" : item.signature_decision === "watch_signature_governance" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">
                            {[
                              getBooleanBadge(item.wet_signature_required).label,
                              getBooleanBadge(item.handwritten_declaration_required).label,
                              getBooleanBadge(item.witness_required).label,
                              getBooleanBadge(item.commissioner_required).label,
                            ].join(" / ")}
                          </td>
                          <td className="p-3 text-right">{getNumber(item.signature_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No signature decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Signature History</h3>
                <StatusBadge label={`${Array.isArray(signatureHistory) ? signatureHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Attestation</th>
                      <th className="p-3 text-right">Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signatureHistory.length ? (
                      signatureHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.signature_governance_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.signature_governance_status, "watch")}
                              tone={item.signature_governance_status === "ok" ? "ok" : item.signature_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getBooleanBadge(item.manual_attestation_required).label}</td>
                          <td className="p-3 text-right">{getNumber(item.signature_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No signature history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Submission Modality Orchestration Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only routing governance across email, portal, and physical submission modalities.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only modality" : "Read-only modality"}
              tone="neutral"
            />
          </div>

          {modalityWarnings.length ? (
            <div className="space-y-3">
              {modalityWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Submission modality orchestration is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Modality Governance"
              tone={getString(modalityLatest.submission_modality_status, "watch") === "ok" ? "ok" : getString(modalityLatest.submission_modality_status, "watch") === "watch" ? "neutral" : "error"}
              summary={`${getNumber(modalityLatest.modality_governance_score, 0).toFixed(2)} governance score`}
              items={[
                ["Status", getString(modalityLatest.submission_modality_status, "watch")],
                ["Selected", getString(modalityLatest.selected_modality, "unsupported")],
                ["Fallback", getString(modalityLatest.fallback_modality, "unsupported")],
                ["Mixed routing", getBooleanBadge(modalityLatest.latest_submission_modality?.mixed_modality_routing).label],
                ["Gate count", String(getNumber(modalityLatest.governance_approval_gate_count, 0))],
                ["Ready count", String(getNumber(modalityLatest.operator_assignment_ready_count, 0))],
              ]}
            />

            <MetricPanel
              title="Modality Conflicts"
              tone={modalityWarnings.length ? "error" : "ok"}
              summary={modalityWarnings.length ? `${modalityWarnings.length} warning(s)` : "No conflicts"}
              items={[
                ["Selected missing", getBooleanBadge(modalityLatest.latest_submission_modality?.modality_conflict_indicators?.selected_modality_missing).label],
                ["Mixed routing", getBooleanBadge(modalityLatest.latest_submission_modality?.modality_conflict_indicators?.mixed_modality_routing).label],
                ["Portal/email conflict", getBooleanBadge(modalityLatest.latest_submission_modality?.modality_conflict_indicators?.portal_email_conflict).label],
                ["Physical/digital conflict", getBooleanBadge(modalityLatest.latest_submission_modality?.modality_conflict_indicators?.physical_with_digital_conflict).label],
                ["Unsupported warnings", String(Array.isArray(modalityLatest.latest_submission_modality?.unsupported_modality_warnings) ? modalityLatest.latest_submission_modality?.unsupported_modality_warnings.length : 0)],
                ["Supported modalities", String(Array.isArray(modalityLatest.latest_submission_modality?.supported_modalities) ? modalityLatest.latest_submission_modality?.supported_modalities.length : 0)],
              ]}
            />

            <MetricPanel
              title="Channel Governance"
              tone={getBooleanBadge(modalityLatest.latest_submission_modality?.governance_approval_gating).tone}
              summary={getBooleanBadge(modalityLatest.latest_submission_modality?.governance_approval_gating).label}
              items={[
                ["Email supported", getBooleanBadge(modalityLatest.latest_submission_modality?.submission_channel_governance_summary?.email_supported).label],
                ["Portal supported", getBooleanBadge(modalityLatest.latest_submission_modality?.submission_channel_governance_summary?.portal_supported).label],
                ["Physical supported", getBooleanBadge(modalityLatest.latest_submission_modality?.submission_channel_governance_summary?.physical_supported).label],
                ["Physical required", getBooleanBadge(modalityLatest.latest_submission_modality?.submission_channel_governance_summary?.physical_required).label],
                ["Selected matches supported", getBooleanBadge(modalityLatest.latest_submission_modality?.submission_channel_governance_summary?.selected_matches_supported).label],
                ["Supervision required", getBooleanBadge(modalityLatest.latest_submission_modality?.submission_channel_governance_summary?.modality_supervision_required).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Modality Decisions</h3>
                <StatusBadge label={`${Array.isArray(modalityLatest.modality_decision_history) ? modalityLatest.modality_decision_history.length : 0} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-left">Selected</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.isArray(modalityLatest.modality_decision_history) && modalityLatest.modality_decision_history.length ? (
                      modalityLatest.modality_decision_history.slice(0, 8).map((item: Record<string, any>) => (
                        <tr key={getString(item.submission_modality_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.modality_decision, "watch_modality")}
                              tone={item.modality_decision === "approve_modality" ? "ok" : item.modality_decision === "watch_modality" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getString(item.selected_modality, "unsupported")}</td>
                          <td className="p-3 text-right">{getNumber(item.modality_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No modality decisions are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Submission Channel Governance</h3>
                <StatusBadge label={`${Array.isArray(modalityHistory) ? modalityHistory.length : 0} record(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">RFQ</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Fallback</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modalityHistory.length ? (
                      modalityHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.submission_modality_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.rfq_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.modality_governance_status, "watch")}
                              tone={item.modality_governance_status === "ok" ? "ok" : item.modality_governance_status === "watch" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3">{getString(item.fallback_modality, "unsupported")}</td>
                          <td className="p-3 text-right">{getNumber(item.modality_governance_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No modality governance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Stability Monitoring</h2>
              <p className="text-sm text-slate-400">
                Read-only drift monitoring for controlled pilot cycles. No controls or production paths are exposed.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only stability" : "Read-only stability"}
              tone="neutral"
            />
          </div>

          {driftWarnings.length ? (
            <div className="space-y-3">
              {driftWarnings.map((warning: string, index: number) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Stability drift is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Stability Score"
              tone={getNumber(stabilityLatest.stability_score, 0) >= 85 ? "ok" : getNumber(stabilityLatest.stability_score, 0) >= 70 ? "neutral" : "error"}
              summary={`${getString(stabilityLatest.stability_grade, "unstable")} • ${getNumber(stabilityLatest.stability_score, 0).toFixed(2)}`}
              items={[
                ["Score", getNumber(stabilityLatest.stability_score, 0).toFixed(2)],
                ["Grade", getString(stabilityLatest.stability_grade, "unstable")],
                ["Cycles", String(getNumber(stabilityLatest.stability?.cycle_count, 0))],
                ["Rehearsals", String(getNumber(stabilityLatest.stability?.rehearsal_count, 0))],
                ["Warning count", String(driftWarnings.length)],
                ["Cadence compliant", getBooleanBadge(cadenceCompliance.compliant).label],
              ]}
            />

            <MetricPanel
              title="Readiness Drift"
              tone={getNumber(readinessDrift.delta, 0) < -2 ? "error" : getNumber(readinessDrift.delta, 0) > 2 ? "ok" : "neutral"}
              summary={`${getString(readinessDrift.trend, "unknown")} • Δ ${getNumber(readinessDrift.delta, 0).toFixed(2)}`}
              items={[
                ["Latest", `${getNumber(readinessDrift.latest, 0).toFixed(2)}`],
                ["Previous", `${getNumber(readinessDrift.previous, 0).toFixed(2)}`],
                ["Average", `${getNumber(readinessDrift.average, 0).toFixed(2)}`],
                ["Cycles tracked", String(Array.isArray(readinessDrift.points) ? readinessDrift.points.length : 0)],
                ["Cadence drift", `${getNumber(cadenceDrift.delta, 0).toFixed(2)}`],
                ["Cadence trend", getString(cadenceDrift.trend, "unknown")],
              ]}
            />

            <MetricPanel
              title="Operational Trends"
              tone={driftWarnings.length ? "error" : "ok"}
              summary={`${stabilityHistory.length} stability snapshot(s)`}
              items={[
                ["Queue trend", getString(queueTrend.trend, "unknown")],
                ["Worker trend", getString(workerTrend.trend, "unknown")],
                ["Telemetry trend", getString(telemetryTrend.trend, "unknown")],
                ["Retry trend", getString(retryTrend.trend, "unknown")],
                ["DLQ trend", getString(dlqTrend.trend, "unknown")],
                ["Operator trend", getString(operatorTrend.trend, "unknown")],
              ]}
            />
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-bold">Latest Stability Snapshot</h3>
              <StatusBadge label={getString(stabilityLatest.status, "unknown")} tone={stabilityLatest.status === "ok" ? "ok" : stabilityLatest.status === "watch" ? "neutral" : "error"} />
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Card title="Latest cycle" value={getString(latestStabilityCycle.cycle_id, "n/a")} />
              <Card title="Latest export" value={getString(latestStabilityExport.export_id, "n/a")} />
              <Card title="Cadence compliant" value={getBooleanBadge(cadenceCompliance.compliant).label} />
              <Card title="Drift warnings" value={String(driftWarnings.length)} />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Stability Trend History</h3>
              <StatusBadge label={`${stabilityHistory.length} snapshot(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Cycle</th>
                    <th className="p-3 text-right">Readiness</th>
                    <th className="p-3 text-right">Queue</th>
                    <th className="p-3 text-right">Worker</th>
                    <th className="p-3 text-right">Telemetry</th>
                    <th className="p-3 text-right">Retry</th>
                    <th className="p-3 text-left">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {stabilityHistory.length ? (
                    stabilityHistory.map((item: Record<string, any>) => (
                      <tr key={getString(item.cycle_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.cycle_id, "n/a")}</td>
                        <td className="p-3 text-right">{getNumber(item.readiness_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{getNumber(item.queue_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{getNumber(item.worker_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{getNumber(item.telemetry_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{getNumber(item.retry_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={7}>
                        No stability history is available yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Pilot Governance Review</h2>
              <p className="text-sm text-slate-400">
                Read-only sign-off review derived from the latest pilot evidence pack. No authorization controls are exposed.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only governance" : "Read-only governance"}
              tone="neutral"
            />
          </div>

          {pilotAuthorizationStatus !== "authorized" ? (
            <div className="space-y-3 rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
              <p className="font-semibold">Pilot authorization is not granted.</p>
              {noGoIndicators.length ? <p className="text-sm text-amber-200">NO-GO indicators: {noGoIndicators.join("; ")}</p> : null}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Pilot authorization status is read-only and currently {pilotAuthorizationStatus}.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Latest Evidence Pack"
              tone={pilotAuthorizationStatus === "authorized" ? "ok" : "neutral"}
              summary={getString(pilotEvidenceLatest.pack_id, "No evidence pack")}
              items={[
                ["Generated", getString(pilotEvidenceLatest.generated_at, "n/a")],
                ["Readiness score", `${getNumber(pilotEvidenceSummary.readiness_score, 0).toFixed(2)}`],
                ["Readiness grade", getString(pilotEvidenceSummary.readiness_grade, "not_ready")],
                ["Trend", getString(pilotEvidenceSummary.trend, "unknown")],
                ["History entries", String(getNumber(pilotEvidenceSummary.history_count, 0))],
                ["Lock source", getString(pilotEvidenceLatest.pack?.lock_source, "n/a")],
              ]}
            />

            <MetricPanel
              title="Governance Sign-Off"
              tone={pilotAuthorizationStatus === "authorized" ? "ok" : "error"}
              summary={pilotAuthorizationStatus}
              items={[
                ["Readiness threshold", `${getNumber(governanceReview.readiness_threshold, 85).toFixed(2)}`],
                ["No-GO indicators", String(noGoIndicators.length)],
                ["Operator checklist", String(signOffChecklist.length)],
                ["Governance checklist", String(governanceChecklist.length)],
                ["Dry-run verified", getBooleanBadge(latestEvidenceDryRun.status === "PASS").label],
                ["Submission lock verified", getBooleanBadge(latestEvidenceLock.status === "PASS").label],
                ["PASS / WARN / FAIL", `${getNumber(latestEvidencePackCounts.PASS, 0)} / ${getNumber(latestEvidencePackCounts.WARN, 0)} / ${getNumber(latestEvidencePackCounts.FAIL, 0)}`],
              ]}
            />

            <MetricPanel
              title="Rehearsal Cadence"
              tone="neutral"
              summary={`${getNumber(pilotEvidenceSummary.history_count, 0)} evidence pack(s)`}
              items={[
                ["Runs last 7 days", String(getNumber(pilotEvidenceSummary.cadence?.runs_last_7_days, 0))],
                ["Average gap hours", `${getNumber(pilotEvidenceSummary.cadence?.average_gap_hours, 0).toFixed(2)}`],
                ["Most recent", getString(pilotEvidenceSummary.cadence?.most_recent_run_at, "n/a")],
                ["Previous", getString(pilotEvidenceSummary.cadence?.previous_run_at, "n/a")],
                ["PASS/WARN/FAIL", JSON.stringify(governanceHistory.trends || {})],
                ["Evidence packs", String(pilotEvidenceHistory.length)],
              ]}
            />
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Operator and Governance Checklist</h3>
              <StatusBadge label={pilotAuthorizationStatus === "authorized" ? "Ready for review" : "Review required"} tone={pilotAuthorizationStatus === "authorized" ? "ok" : "error"} />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                <h4 className="font-semibold text-slate-200">Operator Sign-Off Checklist</h4>
                <ul className="mt-3 space-y-2 text-sm text-slate-300">
                  {signOffChecklist.length ? signOffChecklist.map((item: Record<string, any>, index: number) => (
                    <li key={`${item.item || "operator"}-${index}`} className="flex items-start justify-between gap-3">
                      <span>{getString(item.item, "Checklist item")}</span>
                      <StatusBadge label={getString(item.status, "unknown")} tone={item.status === "PASS" ? "ok" : item.status === "FAIL" ? "error" : "neutral"} />
                    </li>
                  )) : <li className="text-slate-500">No operator checklist items available.</li>}
                </ul>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                <h4 className="font-semibold text-slate-200">Governance Review Checklist</h4>
                <ul className="mt-3 space-y-2 text-sm text-slate-300">
                  {governanceChecklist.length ? governanceChecklist.map((item: Record<string, any>, index: number) => (
                    <li key={`${item.item || "governance"}-${index}`} className="flex items-start justify-between gap-3">
                      <span>{getString(item.item, "Checklist item")}</span>
                      <StatusBadge label={getString(item.status, "unknown")} tone={item.status === "PASS" ? "ok" : item.status === "FAIL" ? "error" : "neutral"} />
                    </li>
                  )) : <li className="text-slate-500">No governance checklist items available.</li>}
                </ul>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Evidence Pack History</h3>
              <StatusBadge label={`${pilotEvidenceHistory.length} pack(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Pack</th>
                    <th className="p-3 text-right">Score</th>
                    <th className="p-3 text-right">PASS</th>
                    <th className="p-3 text-right">WARN</th>
                    <th className="p-3 text-right">FAIL</th>
                    <th className="p-3 text-left">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {pilotEvidenceHistory.length ? (
                    pilotEvidenceHistory.map((item: Record<string, any>) => (
                      <tr key={getString(item.pack_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.pack_id, "n/a")}</td>
                        <td className="p-3 text-right">{getNumber(item.readiness_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{getNumber(item.summary_counts?.PASS, 0)}</td>
                        <td className="p-3 text-right">{getNumber(item.summary_counts?.WARN, 0)}</td>
                        <td className="p-3 text-right">{getNumber(item.summary_counts?.FAIL, 0)}</td>
                        <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={6}>
                        No evidence pack history found in the staging runtime.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Readiness</h2>
              <p className="text-sm text-slate-400">
                Read-only readiness score, thresholds, and trend history derived from staging rehearsals.
              </p>
            </div>
            <StatusBadge label={APP_ENV === "staging" ? "Staging-only readiness" : "Read-only readiness"} tone="neutral" />
          </div>

          {readinessWarnings.length ? (
            <div className="space-y-3">
              {readinessWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Readiness Score"
              tone={getNumber(readinessLatest.readiness_score, 0) >= 85 ? "ok" : getNumber(readinessLatest.readiness_score, 0) >= 70 ? "neutral" : "error"}
              summary={`${getString(readinessLatest.readiness_grade, "not_ready")} • ${getNumber(readinessLatest.readiness_score, 0).toFixed(2)}`}
              items={[
                ["Score", getNumber(readinessLatest.readiness_score, 0).toFixed(2)],
                ["Grade", getString(readinessLatest.readiness_grade, "not_ready")],
                ["Latest run", getString(readinessLatest.latest_run_id, "n/a")],
                ["Success rate", `${getNumber(readinessMetrics.rehearsal_success_rate, 0).toFixed(2)}%`],
                ["Telemetry health", `${getNumber(readinessMetrics.telemetry_health, 0).toFixed(2)}%`],
                ["Threshold", `${getNumber(readinessThresholds.readiness_score, 70).toFixed(2)}`],
              ]}
            />

            <MetricPanel
              title="Readiness Trend"
              tone={getString(readinessTrend.trend, "unknown") === "improving" ? "ok" : getString(readinessTrend.trend, "unknown") === "declining" ? "error" : "neutral"}
              summary={`${getString(readinessTrend.trend, "unknown")} • Δ ${getNumber(readinessTrend.delta, 0).toFixed(2)}`}
              items={[
                ["Average score", `${getNumber(readinessTrend.average_score, 0).toFixed(2)}`],
                ["Latest score", `${getNumber(readinessTrend.latest_score, 0).toFixed(2)}`],
                ["Previous score", `${getNumber(readinessTrend.previous_score, 0).toFixed(2)}`],
                ["History points", String(getNumber(readinessTrend.points, readinessHistory.length))],
                ["With timestamps", String(getNumber(readinessTrend.points_with_timestamp, readinessHistory.length))],
                ["Cadence", `${getNumber(readinessCadence.runs_last_7_days, 0)} run(s) / 7 days`],
              ]}
            />

            <MetricPanel
              title="Stability Indicators"
              tone={readinessWarnings.length ? "error" : "ok"}
              summary={`${readinessHistory.length} historical run(s)`}
              items={[
                ["Retry recovery", `${getNumber(readinessMetrics.retry_recovery_success, 0).toFixed(2)}%`],
                ["Rollback success", `${getNumber(readinessMetrics.rollback_success, 0).toFixed(2)}%`],
                ["Queue stability", `${getNumber(readinessMetrics.queue_stability, 0).toFixed(2)}%`],
                ["Worker stability", `${getNumber(readinessMetrics.worker_stability, 0).toFixed(2)}%`],
                ["DLQ frequency", `${getNumber(readinessMetrics.dlq_escalation_frequency, 0).toFixed(2)}%`],
                ["Operator interventions", `${getNumber(readinessMetrics.operator_intervention_frequency, 0).toFixed(2)}%`],
              ]}
            />
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Readiness Score History</h3>
              <StatusBadge label={`${readinessHistory.length} snapshot(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Run</th>
                    <th className="p-3 text-left">Grade</th>
                    <th className="p-3 text-right">Score</th>
                    <th className="p-3 text-right">Retry</th>
                    <th className="p-3 text-right">Queue</th>
                    <th className="p-3 text-right">Worker</th>
                    <th className="p-3 text-left">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {readinessHistory.length ? (
                    readinessHistory.map((item: Record<string, any>) => (
                      <tr key={getString(item.run_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.run_id, "n/a")}</td>
                        <td className="p-3">
                          <StatusBadge
                            label={getString(item.readiness_grade, "unknown")}
                            tone={item.readiness_grade === "ready" ? "ok" : item.readiness_grade === "watch" ? "neutral" : "error"}
                          />
                        </td>
                        <td className="p-3 text-right">{getNumber(item.readiness_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{getNumber(item.metrics?.retry_recovery_success, 0).toFixed(2)}%</td>
                        <td className="p-3 text-right">{getNumber(item.metrics?.queue_stability, 0).toFixed(2)}%</td>
                        <td className="p-3 text-right">{getNumber(item.metrics?.worker_stability, 0).toFixed(2)}%</td>
                        <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={7}>
                        No readiness score history found in the staging runtime.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Scheduled Pilot Cadence</h2>
              <p className="text-sm text-slate-400">
                Read-only cadence governance for recurring staging pilot cycles, governance review timing, and stability checkpoints.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only cadence" : "Read-only cadence"}
              tone="neutral"
            />
          </div>

          {cadenceWarnings.length ? (
            <div className="space-y-3">
              {cadenceWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Cadence governance is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Cadence Status"
              tone={cadenceLatest.status === "ok" ? "ok" : cadenceLatest.status === "watch" ? "neutral" : "error"}
              summary={`${getString(cadenceLatest.cadence_grade, "late")} • ${getNumber(cadenceLatest.cadence_score, 0).toFixed(2)}`}
              items={[
                ["Score", getNumber(cadenceLatest.cadence_score, 0).toFixed(2)],
                ["Grade", getString(cadenceLatest.cadence_grade, "late")],
                ["Pilot cycles", String(getNumber(pilotCadence.runs_last_7_days, 0))],
                ["Governance reviews", String(getNumber(governanceCadence.runs_last_7_days, 0))],
                ["Stability checkpoints", String(getNumber(cadenceStability.history_count, 0))],
                ["Warnings", String(cadenceWarnings.length)],
              ]}
            />

            <MetricPanel
              title="Pilot Cycle Cadence"
              tone={pilotCadence.compliant ? "ok" : "error"}
              summary={`${getString(pilotCadence.cadence_status, "unknown")} • ${getNumber(pilotCadence.runs_last_7_days, 0)} in window`}
              items={[
                ["Latest cycle", getString(pilotCadence.latest_cycle_id, "n/a")],
                ["Latest run", getString(pilotCadence.latest_run_at, "n/a")],
                ["Average gap hours", `${getNumber(pilotCadence.average_gap_hours, 0).toFixed(2)}`],
                ["Next due", getString(pilotCadence.next_cycle_due_at, "n/a")],
                ["Missed cycle warning", getBooleanBadge(pilotCadence.missed_cycle_warning).label],
                ["Window days", String(getNumber(pilotCadence.warning_threshold_days, 7))],
              ]}
            />

            <MetricPanel
              title="Governance Review Cadence"
              tone={governanceCadence.compliant ? "ok" : "error"}
              summary={`${getString(governanceCadence.cadence_status, "unknown")} • ${getNumber(governanceCadence.runs_last_7_days, 0)} in window`}
              items={[
                ["Latest review", getString(governanceCadence.latest_export_id, "n/a")],
                ["Latest review at", getString(governanceCadence.latest_review_at, "n/a")],
                ["Average gap hours", `${getNumber(governanceCadence.average_gap_hours, 0).toFixed(2)}`],
                ["Next due", getString(governanceCadence.next_review_due_at, "n/a")],
                ["Overdue warning", getBooleanBadge(governanceCadence.overdue_governance_review_warning).label],
                ["Window days", String(getNumber(governanceCadence.warning_threshold_days, 7))],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MetricPanel
              title="Stability Trend Checkpoints"
              tone={cadenceStability.cadence_compliant ? "ok" : "error"}
              summary={`${getNumber(cadenceStability.latest_score, 0).toFixed(2)} • ${getString(cadenceStability.latest_grade, "unstable")}`}
              items={[
                ["Latest score", `${getNumber(cadenceStability.latest_score, 0).toFixed(2)}`],
                ["Latest grade", getString(cadenceStability.latest_grade, "unstable")],
                ["Latest checkpoint", getString(cadenceStability.latest_generated_at, "n/a")],
                ["Drift warnings", String(Array.isArray(cadenceStability.drift_warnings) ? cadenceStability.drift_warnings.length : 0)],
                ["Cycle count", String(getNumber(cadenceStability.stability_cycle_count, 0))],
                ["Rehearsal count", String(getNumber(cadenceStability.stability_rehearsal_count, 0))],
              ]}
            />

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Cadence Tracking</h3>
                <StatusBadge label={`${cadenceHistory.length} checkpoint(s)`} tone="neutral" />
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Type</th>
                      <th className="p-3 text-left">ID</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cadenceHistory.length ? (
                      cadenceHistory.map((item: Record<string, any>) => (
                        <tr key={`${getString(item.kind, "cadence")}-${getString(item.id, Math.random().toString())}`} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.kind, "cadence")}</td>
                          <td className="p-3">{getString(item.id, "n/a")}</td>
                          <td className="p-3 text-right">
                            {getNumber(item.readiness_score ?? item.stability_score ?? 0, 0).toFixed(2)}
                          </td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.status, "unknown")}
                              tone={item.status === "PASS" ? "ok" : item.status === "FAIL" ? "error" : "neutral"}
                            />
                          </td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No cadence tracking data is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Exception Classification</h2>
              <p className="text-sm text-slate-400">
                Read-only classification and remediation tracking for recurring pilot-cycle anomalies.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only exceptions" : "Read-only exceptions"}
              tone="neutral"
            />
          </div>

          {exceptionWarnings.length ? (
            <div className="space-y-3">
              {exceptionWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Operational exception status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Exception Status"
              tone={exceptionsLatest.exception_status === "ok" ? "ok" : exceptionsLatest.exception_status === "watch" ? "neutral" : "error"}
              summary={`${getString(exceptionsLatest.exception_status, "watch")} • ${getNumber(exceptionSummary.total_exception_count, 0)} total`}
              items={[
                ["Total exceptions", String(getNumber(exceptionSummary.total_exception_count, 0))],
                ["Open", String(getNumber(exceptionSummary.open_exception_count, 0))],
                ["Resolved", String(getNumber(exceptionSummary.resolved_exception_count, 0))],
                ["Latest exception", getString(anomalySummary.latest_exception_type, "none")],
                ["Most common", getString(anomalySummary.most_common_exception_type, "none")],
                ["History entries", String(classificationHistory.length)],
              ]}
            />

            <MetricPanel
              title="Remediation Tracking"
              tone={getNumber(remediationSummary.unresolved_count, 0) > 0 ? "error" : "ok"}
              summary={`${getNumber(remediationSummary.unresolved_count, 0)} unresolved / ${getNumber(remediationSummary.resolved_count, 0)} resolved`}
              items={[
                ["Unresolved", String(getNumber(remediationSummary.unresolved_count, 0))],
                ["Resolved", String(getNumber(remediationSummary.resolved_count, 0))],
                ["Open categories", String(Array.isArray(remediationSummary.open_categories) ? remediationSummary.open_categories.length : 0)],
                ["Resolved categories", String(Array.isArray(remediationSummary.resolved_categories) ? remediationSummary.resolved_categories.length : 0)],
                ["Risk score", `${getNumber(riskIndicators.latest_readiness_score, 0).toFixed(2)}`],
                ["Latest exception age", `${getNumber(riskIndicators.latest_exception_age_hours, 0).toFixed(2)}h`],
              ]}
            />

            <MetricPanel
              title="Operational Risk Indicators"
              tone={riskIndicators.governance_compliance_risk || riskIndicators.systemic_failure_risk || riskIndicators.telemetry_degradation_risk || riskIndicators.queue_instability_risk || riskIndicators.retry_exhaustion_risk ? "error" : "ok"}
              summary={`${Array.isArray(riskIndicators.repeated_exception_types) ? riskIndicators.repeated_exception_types.length : 0} repeated type(s)`}
              items={[
                ["Governance risk", getBooleanBadge(riskIndicators.governance_compliance_risk).label],
                ["Systemic risk", getBooleanBadge(riskIndicators.systemic_failure_risk).label],
                ["Telemetry risk", getBooleanBadge(riskIndicators.telemetry_degradation_risk).label],
                ["Queue risk", getBooleanBadge(riskIndicators.queue_instability_risk).label],
                ["Retry risk", getBooleanBadge(riskIndicators.retry_exhaustion_risk).label],
                ["Operator risk", getBooleanBadge(riskIndicators.operator_intervention_risk).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Unresolved Exceptions</h3>
                <StatusBadge label={`${unresolvedExceptions.length} open`} tone={unresolvedExceptions.length ? "error" : "ok"} />
              </div>
              <div className="mt-4 space-y-3">
                {unresolvedExceptions.length ? unresolvedExceptions.map((item: Record<string, any>) => (
                  <div key={getString(item.exception_id, Math.random().toString())} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{getString(item.category, "unknown")}</p>
                        <p className="text-xs text-slate-500">{getString(item.source, "source")}</p>
                      </div>
                      <StatusBadge label={getString(item.severity, "medium")} tone={item.severity === "critical" || item.severity === "high" ? "error" : "neutral"} />
                    </div>
                    <p className="mt-2 text-sm text-slate-300">{getString(item.message, "No message")}</p>
                    <p className="mt-2 text-xs text-slate-500">Remediation: {getString(item.remediation_action, "n/a")}</p>
                  </div>
                )) : (
                  <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
                    No unresolved operational exceptions are currently recorded in staging.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Resolved Exception History</h3>
                <StatusBadge label={`${resolvedExceptionHistory.length} resolved`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Type</th>
                      <th className="p-3 text-left">Source</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Resolved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resolvedExceptionHistory.length ? (
                      resolvedExceptionHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.exception_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.category, "n/a")}</td>
                          <td className="p-3">{getString(item.source, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge label={getString(item.remediation_status, "resolved")} tone={item.remediation_status === "resolved" ? "ok" : "neutral"} />
                          </td>
                          <td className="p-3 text-slate-400">{getString(item.resolved_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No resolved exception history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Historical Anomalies</h3>
              <StatusBadge label={`${exceptionsHistory.length} item(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Exception</th>
                    <th className="p-3 text-left">Category</th>
                    <th className="p-3 text-left">Severity</th>
                    <th className="p-3 text-left">Remediation</th>
                    <th className="p-3 text-left">Detected</th>
                  </tr>
                </thead>
                <tbody>
                  {exceptionsHistory.length ? (
                    exceptionsHistory.map((item: Record<string, any>) => (
                      <tr key={getString(item.exception_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.exception_id, "n/a")}</td>
                        <td className="p-3">{getString(item.category, "n/a")}</td>
                        <td className="p-3">
                          <StatusBadge label={getString(item.severity, "medium")} tone={item.severity === "critical" || item.severity === "high" ? "error" : "neutral"} />
                        </td>
                        <td className="p-3 text-slate-300">{getString(item.remediation_action, "n/a")}</td>
                        <td className="p-3 text-slate-400">{getString(item.detected_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={5}>
                        No historical anomalies are available yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Remediation Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only remediation ownership, deadlines, accepted-risk classification, and closure tracking for recurring pilot exceptions.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only remediation" : "Read-only remediation"}
              tone="neutral"
            />
          </div>

          {remediationWarnings.length ? (
            <div className="space-y-3">
              {remediationWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Operational remediation governance is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Remediation Status"
              tone={getString(remediationLatest.remediation_status, "watch") === "ok" ? "ok" : getNumber(remediationSummaryData.open_remediation_count, 0) > 0 ? "error" : "neutral"}
              summary={`${getNumber(remediationSummaryData.open_remediation_count, 0)} open / ${getNumber(remediationSummaryData.resolved_remediation_count, 0)} resolved`}
              items={[
                ["Total", String(getNumber(remediationSummaryData.total_remediation_count, 0))],
                ["Open", String(getNumber(remediationSummaryData.open_remediation_count, 0))],
                ["Resolved", String(getNumber(remediationSummaryData.resolved_remediation_count, 0))],
                ["Overdue", String(getNumber(remediationSummaryData.overdue_remediation_count, 0))],
                ["Blocking", String(getNumber(remediationSummaryData.blocking_remediation_count, 0))],
                ["Accepted risk", String(getNumber(remediationSummaryData.accepted_risk_remediation_count, 0))],
              ]}
            />

            <MetricPanel
              title="Risk Closure Summary"
              tone={getNumber(remediationClosureSummary.overdue_count, 0) > 0 ? "error" : "ok"}
              summary={`${getNumber(remediationClosureSummary.open_count, 0)} open / ${getNumber(remediationClosureSummary.closed_count, 0)} closed`}
              items={[
                ["Open", String(getNumber(remediationClosureSummary.open_count, 0))],
                ["Closed", String(getNumber(remediationClosureSummary.closed_count, 0))],
                ["Overdue", String(getNumber(remediationClosureSummary.overdue_count, 0))],
                ["Accepted risk", String(getNumber(remediationClosureSummary.accepted_risk_count, 0))],
                ["Latest remediation", getString(remediationHistorySummary.latest_remediation_id, "n/a")],
                ["Latest owner", getString(remediationHistorySummary.latest_owner, "n/a")],
              ]}
            />

            <MetricPanel
              title="Operational Risk Indicators"
              tone={remediationIndicators.overdue_remediation_warning || remediationIndicators.unresolved_blocker_warning ? "error" : "ok"}
              summary={`${remediationHistory.length} history item(s)`}
              items={[
                ["Overdue warning", getBooleanBadge(remediationIndicators.overdue_remediation_warning).label],
                ["Unresolved blocker", getBooleanBadge(remediationIndicators.unresolved_blocker_warning).label],
                ["Accepted risk", getBooleanBadge(remediationIndicators.accepted_risk_warning).label],
                ["History warning", getBooleanBadge(remediationIndicators.history_warning).label],
                ["Latest cycle", getString(remediationLatest.latest_cycle?.cycle_id, "n/a")],
                ["Latest export", getString(remediationLatest.latest_governance_export?.export_id, "n/a")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Remediation Actions</h3>
                <StatusBadge label={`${remediationActions.length} tracked`} tone={remediationActions.length ? "neutral" : "ok"} />
              </div>
              <div className="mt-4 space-y-3">
                {remediationActions.length ? remediationActions.map((item: Record<string, any>) => (
                  <div key={getString(item.remediation_id, Math.random().toString())} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{getString(item.category, "unknown")}</p>
                        <p className="text-xs text-slate-500">{getString(item.owner, "unassigned")}</p>
                      </div>
                      <StatusBadge label={getString(item.completion_status, "in_progress")} tone={item.completion_status === "completed" ? "ok" : item.overdue ? "error" : "neutral"} />
                    </div>
                    <p className="mt-2 text-sm text-slate-300">{getString(item.remediation_action, "n/a")}</p>
                    <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-slate-400 md:grid-cols-2">
                      <div>Deadline: {getString(item.deadline_at, "n/a")}</div>
                      <div>Risk: {getString(item.accepted_operational_risk_classification, "n/a")}</div>
                      <div>Blocker: {getString(item.blocker_status, "n/a")}</div>
                      <div>Resolved: {getString(item.resolved_at, "n/a")}</div>
                    </div>
                  </div>
                )) : (
                  <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
                    No remediation actions are currently tracked in staging.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Remediation History</h3>
                <StatusBadge label={`${remediationHistory.length} item(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Remediation</th>
                      <th className="p-3 text-left">Owner</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-left">Deadline</th>
                      <th className="p-3 text-left">Resolved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {remediationHistory.length ? (
                      remediationHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.remediation_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.category, "n/a")}</td>
                          <td className="p-3">{getString(item.owner, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge label={getString(item.completion_status, "in_progress")} tone={item.completion_status === "completed" ? "ok" : item.overdue ? "error" : "neutral"} />
                          </td>
                          <td className="p-3 text-slate-300">{getString(item.deadline_at, "n/a")}</td>
                          <td className="p-3 text-slate-400">{getString(item.resolved_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No remediation history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Pilot Progression Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only continuation, watch-status, closure, and scope-expansion governance for controlled pilot decisions.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only progression" : "Read-only progression"}
              tone="neutral"
            />
          </div>

          {progressionWarnings.length ? (
            <div className="space-y-3">
              {progressionWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Pilot progression governance is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Progression Status"
              tone={progressionStatus === "ok" ? "ok" : progressionStatus === "watch" ? "neutral" : "error"}
              summary={`${progressionDecision} • ${progressionScore.toFixed(2)}`}
              items={[
                ["Status", progressionStatus],
                ["Decision", progressionDecision],
                ["Score", progressionScore.toFixed(2)],
                ["Grade", progressionGrade],
                ["Latest review", getString(progressionLatest.latest_review_board_status, "n/a")],
                ["History entries", String(progressionHistory.length)],
              ]}
            />

            <MetricPanel
              title="Eligibility Indicators"
              tone={progressionEligibility.expansion_eligible ? "ok" : progressionEligibility.continuation_eligible ? "neutral" : "error"}
              summary={`${progressionEligibility.expansion_eligible ? "expansion" : progressionEligibility.continuation_eligible ? "continuation" : "blocked"}`}
              items={[
                ["Continuation", getBooleanBadge(progressionEligibility.continuation_eligible).label],
                ["Watch", getBooleanBadge(progressionEligibility.watch_eligible).label],
                ["Closure", getBooleanBadge(progressionEligibility.closure_eligible).label],
                ["Expansion", getBooleanBadge(progressionEligibility.expansion_eligible).label],
                ["No-go clear", getBooleanBadge(progressionEligibility.no_go_clear).label],
                ["Submission lock", getBooleanBadge(progressionEligibility.submission_lock_clear).label],
              ]}
            />

            <MetricPanel
              title="Unresolved Blockers"
              tone={getNumber(progressionBlockers.blocking_remediation_count, 0) > 0 ? "error" : "ok"}
              summary={`${getNumber(progressionBlockers.blocking_remediation_count, 0)} blocking / ${getNumber(progressionBlockers.open_remediation_count, 0)} open`}
              items={[
                ["Blocking remediation", String(getNumber(progressionBlockers.blocking_remediation_count, 0))],
                ["Open remediation", String(getNumber(progressionBlockers.open_remediation_count, 0))],
                ["Open exceptions", String(getNumber(progressionBlockers.open_exception_count, 0))],
                ["Latest rationale", getString(progressionRationale.status, "PASS")],
                ["Rationale entries", String(Array.isArray(progressionRationale.rationale) ? progressionRationale.rationale.length : 0)],
                ["Decision history", String(progressionDecisionHistory.length)],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Governance Decisions</h3>
                <StatusBadge label={`${progressionHistory.length} decision(s)`} tone="neutral" />
              </div>
              <div className="mt-4 space-y-3">
                {progressionHistory.length ? progressionHistory.map((item: Record<string, any>) => (
                  <div key={getString(item.progression_id, Math.random().toString())} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{getString(item.progression_decision, "review_required")}</p>
                        <p className="text-xs text-slate-500">{getString(item.review_id, "n/a")}</p>
                      </div>
                      <StatusBadge label={getString(item.progression_grade, "watch")} tone={item.progression_grade === "ready" ? "ok" : item.progression_grade === "watch" ? "neutral" : "error"} />
                    </div>
                    <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-slate-400 md:grid-cols-2">
                      <div>Score: {getNumber(item.progression_score, 0).toFixed(2)}</div>
                      <div>Continuation: {getBooleanBadge(item.pilot_continuation_review).label}</div>
                      <div>Watch: {getBooleanBadge(item.watch_status_review).label}</div>
                      <div>Expansion: {getBooleanBadge(item.scope_expansion_review).label}</div>
                    </div>
                  </div>
                )) : (
                  <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
                    No progression decisions are currently available in staging.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Governance Rationale</h3>
                <StatusBadge label={getString(progressionRationale.status, "PASS")} tone={getString(progressionRationale.status, "PASS") === "PASS" ? "ok" : "neutral"} />
              </div>
              <div className="mt-4 space-y-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <div className="grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                    <div>Readiness: {getNumber(progressionRationale.latest_readiness_score, 0).toFixed(2)}</div>
                    <div>Review board: {getString(progressionRationale.latest_review_board_status, "watch")}</div>
                    <div>Remediation: {getString(progressionRationale.latest_remediation_status, "watch")}</div>
                    <div>Exceptions: {getString(progressionRationale.latest_exception_status, "watch")}</div>
                  </div>
                </div>
                <div className="space-y-2">
                  {Array.isArray(progressionRationale.rationale) ? progressionRationale.rationale.map((line: string, index: number) => (
                    <div key={`${line}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/30 p-3 text-sm text-slate-300">
                      {line}
                    </div>
                  )) : (
                    <div className="rounded-lg border border-emerald-700 bg-emerald-950/40 p-3 text-sm text-emerald-100">
                      No governance rationale has been recorded yet.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Pilot Operations Summary Index</h2>
              <p className="text-sm text-slate-400">
                Consolidated read-only readiness, stability, remediation, progression, cadence, exception, and governance summary for staging operations.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only summary" : "Read-only summary"}
              tone="neutral"
            />
          </div>

          {operationsSummaryWarnings.length ? (
            <div className="space-y-3">
              {operationsSummaryWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Pilot operations summary status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Consolidated Governance Score"
              tone={getNumber(operationsSummaryLatest.consolidated_governance_score, 0) >= 85 ? "ok" : getNumber(operationsSummaryLatest.consolidated_governance_score, 0) >= 70 ? "neutral" : "error"}
              summary={`${getString(operationsSummaryLatest.consolidated_governance_grade, "blocked")} • ${getNumber(operationsSummaryLatest.consolidated_governance_score, 0).toFixed(2)}`}
              items={[
                ["Readiness", getString(operationsSummaryLatest.readiness_status, "watch")],
                ["Stability", getString(operationsSummaryLatest.stability_status, "watch")],
                ["Remediation", getString(operationsSummaryLatest.remediation_status, "watch")],
                ["Progression", getString(operationsSummaryLatest.progression_status, "watch")],
                ["Cadence", getString(operationsSummaryLatest.cadence_status, "on_track")],
                ["NO-GO", getString(operationsSummaryLatest.no_go_status, "UNKNOWN")],
                ["Readiness component", `${getNumber(operationsSummary.readiness, 0).toFixed(2)}`],
                ["Stability component", `${getNumber(operationsSummary.stability, 0).toFixed(2)}`],
              ]}
            />

            <MetricPanel
              title="Consolidated Watch Indicators"
              tone={Object.values(operationsWatchIndicators).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(operationsWatchIndicators).filter(Boolean).length} active watch indicator(s)`}
              items={[
                ["Readiness watch", getBooleanBadge(operationsWatchIndicators.readiness_watch).label],
                ["Stability watch", getBooleanBadge(operationsWatchIndicators.stability_watch).label],
                ["Remediation watch", getBooleanBadge(operationsWatchIndicators.remediation_watch).label],
                ["Progression watch", getBooleanBadge(operationsWatchIndicators.progression_watch).label],
                ["Cadence watch", getBooleanBadge(operationsWatchIndicators.cadence_watch).label],
                ["Exception watch", getBooleanBadge(operationsWatchIndicators.exception_watch).label],
              ]}
            />

            <MetricPanel
              title="Governance Recommendation"
              tone={getString(operationsRecommendation.recommendation, "review_required") === "scope_expansion_review" ? "ok" : getString(operationsRecommendation.recommendation, "review_required") === "pilot_continuation_review" ? "neutral" : "error"}
              summary={getString(operationsRecommendation.recommendation, "review_required")}
              items={[
                ["Latest readiness", `${getNumber(operationsRecommendation.latest_readiness_score, 0).toFixed(2)}`],
                ["Latest stability", `${getNumber(operationsRecommendation.latest_stability_score, 0).toFixed(2)}`],
                ["Blocking remediations", String(getNumber(operationsBlockers.blocking_remediation_count, 0))],
                ["Open remediations", String(getNumber(operationsBlockers.open_remediation_count, 0))],
                ["Open exceptions", String(getNumber(operationsBlockers.open_exception_count, 0))],
                ["History entries", String(operationsHistory.length)],
              ]}
            />
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Operational Summary History</h3>
              <StatusBadge label={`${operationsSummaryHistory.length} snapshot(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Summary</th>
                    <th className="p-3 text-left">Governance</th>
                    <th className="p-3 text-right">Score</th>
                    <th className="p-3 text-left">Readiness</th>
                    <th className="p-3 text-left">Remediation</th>
                    <th className="p-3 text-left">Progression</th>
                    <th className="p-3 text-left">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {operationsSummaryHistory.length ? (
                    operationsSummaryHistory.map((item: Record<string, any>) => (
                      <tr key={getString(item.summary_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.summary_id, "n/a")}</td>
                        <td className="p-3">{getString(item.governance_review_status, "n/a")}</td>
                        <td className="p-3 text-right">{getNumber(item.consolidated_governance_score, 0).toFixed(2)}</td>
                        <td className="p-3">
                          <StatusBadge label={getString(item.readiness_status, "watch")} tone={item.readiness_status === "ok" ? "ok" : item.readiness_status === "watch" ? "neutral" : "error"} />
                        </td>
                        <td className="p-3">
                          <StatusBadge label={getString(item.remediation_status, "watch")} tone={item.remediation_status === "ok" ? "ok" : item.remediation_status === "watch" ? "neutral" : "error"} />
                        </td>
                        <td className="p-3">
                          <StatusBadge label={getString(item.progression_status, "watch")} tone={item.progression_status === "ok" ? "ok" : item.progression_status === "watch" ? "neutral" : "error"} />
                        </td>
                        <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={7}>
                        No operational summary history is available yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Institutional Readiness Declaration</h2>
              <p className="text-sm text-slate-400">
                Final read-only staging declaration for controlled pilot readiness, watch, or no-go.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only declaration" : "Read-only declaration"}
              tone="neutral"
            />
          </div>

          {declarationWarnings.length ? (
            <div className="space-y-3">
              {declarationWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Readiness declaration status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Declaration Status"
              tone={getString(declarationLatest.declaration_status, "WATCH") === "READY_FOR_CONTROLLED_PILOT" ? "ok" : getString(declarationLatest.declaration_status, "WATCH") === "WATCH" ? "neutral" : "error"}
              summary={`${getString(declarationLatest.declaration_status, "WATCH")} • ${getNumber(declarationLatest.declaration_score, 0).toFixed(2)}`}
              items={[
                ["Grade", getString(declarationLatest.declaration_grade, "watch")],
                ["Readiness", `${getNumber(declarationLatest.declaration_rationale_summary?.readiness_score, 0).toFixed(2)}`],
                ["Stability", `${getNumber(declarationLatest.declaration_rationale_summary?.stability_score, 0).toFixed(2)}`],
                ["NO-GO", getString(declarationLatest.declaration_rationale_summary?.no_go_status, "UNKNOWN")],
                ["Decision history", String(declarationHistory.length)],
                ["Latest summary", getString(declarationLatest.declaration_history_summary?.latest_declaration_status, "n/a")],
              ]}
            />

            <MetricPanel
              title="Declaration Rationale"
              tone={getString(declarationLatest.declaration_status, "WATCH") === "READY_FOR_CONTROLLED_PILOT" ? "ok" : "neutral"}
              summary={getString(declarationLatest.declaration_rationale_summary?.status, "WARN")}
              items={[
                ["Remediation", getString(declarationLatest.declaration_rationale_summary?.remediation_status, "watch")],
                ["Cadence", getString(declarationLatest.declaration_rationale_summary?.cadence_status, "on_track")],
                ["Progression", getString(declarationLatest.declaration_rationale_summary?.progression_status, "watch")],
                ["Recommendation", getString(declarationLatest.declaration_rationale_summary?.governance_recommendation, "review_required")],
                ["Rationale entries", String(Array.isArray(declarationLatest.declaration_rationale_summary?.rationale) ? declarationLatest.declaration_rationale_summary.rationale.length : 0)],
                ["History safe", getBooleanBadge(declarationLatest.declaration_history_summary?.latest_declaration_status === "READY_FOR_CONTROLLED_PILOT").label],
              ]}
            />

            <MetricPanel
              title="Overrides & Escalation"
              tone={Object.values(declarationLatest.governance_override_indicators || {}).some(Boolean) || Array.isArray(declarationLatest.escalation_triggers) && declarationLatest.escalation_triggers.length ? "error" : "ok"}
              summary={`${Object.values(declarationLatest.governance_override_indicators || {}).filter(Boolean).length} override(s)`}
              items={[
                ["History override", getBooleanBadge(declarationLatest.governance_override_indicators?.history_override_required).label],
                ["Recommendation override", getBooleanBadge(declarationLatest.governance_override_indicators?.recommendation_override_required).label],
                ["Blocker override", getBooleanBadge(declarationLatest.governance_override_indicators?.blocker_override_required).label],
                ["NO-GO override", getBooleanBadge(declarationLatest.governance_override_indicators?.no_go_override_required).label],
                ["Escalations", String(Array.isArray(declarationLatest.escalation_triggers) ? declarationLatest.escalation_triggers.length : 0)],
                ["Latest declaration", getString(declarationLatest.declaration_history_summary?.latest_declaration_id, "n/a")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Declaration History</h3>
                <StatusBadge label={`${declarationHistory.length} declaration(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Declaration</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Readiness</th>
                      <th className="p-3 text-left">Progression</th>
                      <th className="p-3 text-left">NO-GO</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {declarationHistory.length ? (
                      declarationHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.declaration_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.declaration_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.declaration_status, "WATCH")}
                              tone={item.declaration_status === "READY_FOR_CONTROLLED_PILOT" ? "ok" : item.declaration_status === "WATCH" ? "neutral" : "error"}
                            />
                          </td>
                          <td className="p-3 text-right">{getNumber(item.declaration_score, 0).toFixed(2)}</td>
                          <td className="p-3">{getString(item.readiness_status, "watch")}</td>
                          <td className="p-3">{getString(item.progression_status, "watch")}</td>
                          <td className="p-3">{getString(item.no_go_status, "UNKNOWN")}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={7}>
                          No declaration history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Declaration Rationale</h3>
                <StatusBadge label={getString(declarationLatest.declaration_status, "WATCH")} tone={declarationLatest.declaration_status === "READY_FOR_CONTROLLED_PILOT" ? "ok" : declarationLatest.declaration_status === "WATCH" ? "neutral" : "error"} />
              </div>
              <div className="mt-4 space-y-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <div className="grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                    <div>Readiness: {getNumber(declarationLatest.declaration_rationale_summary?.readiness_score, 0).toFixed(2)}</div>
                    <div>Stability: {getNumber(declarationLatest.declaration_rationale_summary?.stability_score, 0).toFixed(2)}</div>
                    <div>Remediation: {getString(declarationLatest.declaration_rationale_summary?.remediation_status, "watch")}</div>
                    <div>Cadence: {getString(declarationLatest.declaration_rationale_summary?.cadence_status, "on_track")}</div>
                    <div>Progression: {getString(declarationLatest.declaration_rationale_summary?.progression_status, "watch")}</div>
                    <div>NO-GO: {getString(declarationLatest.declaration_rationale_summary?.no_go_status, "UNKNOWN")}</div>
                  </div>
                </div>
                <div className="space-y-2">
                  {Array.isArray(declarationLatest.declaration_rationale_summary?.rationale) ? declarationLatest.declaration_rationale_summary.rationale.map((line: string, index: number) => (
                    <div key={`${line}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/30 p-3 text-sm text-slate-300">
                      {line}
                    </div>
                  )) : (
                    <div className="rounded-lg border border-emerald-700 bg-emerald-950/40 p-3 text-sm text-emerald-100">
                      No readiness declaration rationale has been recorded yet.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Final Submission Readiness Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only institutional authority for final submission readiness, escalation, and submission authorization.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only final readiness" : "Read-only final readiness"}
              tone="neutral"
            />
          </div>

          {finalWarnings.length ? (
            <div className="space-y-3">
              {finalWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Final submission readiness is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Final Readiness Status"
              tone={getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT") === "READY_TO_SUBMIT" ? "ok" : getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT") === "NOT_READY_TO_SUBMIT" ? "error" : "neutral"}
              summary={`${getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT")} • ${getNumber(finalLatest.final_submission_readiness_score, 0).toFixed(2)}`}
              items={[
                ["Status", getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT")],
                ["Score", getNumber(finalLatest.final_submission_readiness_score, 0).toFixed(2)],
                ["Grade", getString(finalLatest.final_submission_readiness_grade, "not_ready")],
                ["Decision", getString(finalLatest.final_submission_readiness_decision, "defer_final_submission")],
                ["History", String(finalHistory.length)],
                ["Authority", getString(finalLatest.final_escalation_authority, "governance_review_board")],
              ]}
            />

            <MetricPanel
              title="Final Verification"
              tone={Object.values(finalLatest.unresolved_blocker_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(finalLatest.unresolved_blocker_indicators || {}).filter(Boolean).length} blocker(s)`}
              items={[
                ["Completeness", getBooleanBadge(finalLatest.final_completeness_verification?.final_completeness_ok).label],
                ["Compliance", getBooleanBadge(finalLatest.final_compliance_verification?.final_compliance_ok).label],
                ["Packaging", getBooleanBadge(finalLatest.final_packaging_verification?.final_packaging_ok).label],
                ["Timing", getBooleanBadge(finalLatest.final_timing_verification?.final_timing_ok).label],
                ["Supervision", getBooleanBadge(finalLatest.final_supervision_verification?.supervision_ok).label],
                ["Modality", getBooleanBadge(finalLatest.final_modality_verification?.final_modality_ok).label],
              ]}
            />

            <MetricPanel
              title="Overrides & Escalation"
              tone={Object.values(finalLatest.governance_override_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(finalLatest.governance_override_indicators || {}).filter(Boolean).length} override(s)`}
              items={[
                ["Final escalation", getString(finalLatest.final_escalation_authority, "governance_review_board")],
                ["Readiness override", getBooleanBadge(finalLatest.governance_override_indicators?.readiness_override_required).label],
                ["Compliance override", getBooleanBadge(finalLatest.governance_override_indicators?.compliance_override_required).label],
                ["Packaging override", getBooleanBadge(finalLatest.governance_override_indicators?.packaging_override_required).label],
                ["Timing override", getBooleanBadge(finalLatest.governance_override_indicators?.timing_override_required).label],
                ["Supervision override", getBooleanBadge(finalLatest.governance_override_indicators?.supervision_override_required).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Final Readiness History</h3>
                <StatusBadge label={`${finalHistory.length} readiness entry(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Readiness</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {finalHistory.length ? (
                      finalHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.final_readiness_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.final_submission_readiness_status, "NOT_READY_TO_SUBMIT")}</td>
                          <td className="p-3">{getString(item.final_submission_readiness_decision, "defer_final_submission")}</td>
                          <td className="p-3 text-right">{getNumber(item.final_submission_readiness_score, 0).toFixed(2)}</td>
                          <td className="p-3">{getString(item.final_escalation_authority, "governance_review_board")}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No final readiness history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Final Readiness Rationale</h3>
                <StatusBadge label={getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT")} tone={getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT") === "READY_TO_SUBMIT" ? "ok" : getString(finalLatest.final_submission_readiness_status, "NOT_READY_TO_SUBMIT") === "NOT_READY_TO_SUBMIT" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 space-y-2">
                {Array.isArray(finalLatest.final_readiness_rationale) ? finalLatest.final_readiness_rationale.map((line: string, index: number) => (
                  <div key={`${line}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/30 p-3 text-sm text-slate-300">
                    {line}
                  </div>
                )) : (
                  <div className="rounded-lg border border-emerald-700 bg-emerald-950/40 p-3 text-sm text-emerald-100">
                    No final readiness rationale has been recorded yet.
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Intelligence Governance</h2>
              <p className="text-sm text-slate-400">
                Read-only intelligence scoring and trend analysis across supervised procurement operations.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only intelligence" : "Read-only intelligence"}
              tone="neutral"
            />
          </div>

          {operationalIntelligenceWarnings.length ? (
            <div className="space-y-3">
              {operationalIntelligenceWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Operational intelligence remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Intelligence Score"
              tone={getString(operationalIntelligenceLatest.operational_intelligence_status, "watch") === "ok" ? "ok" : getString(operationalIntelligenceLatest.operational_intelligence_status, "watch") === "blocked" ? "error" : "neutral"}
              summary={`${getString(operationalIntelligenceLatest.operational_intelligence_grade, "blocked")} • ${getNumber(operationalIntelligenceLatest.operational_intelligence_score, 0).toFixed(2)}`}
              items={[
                ["Status", getString(operationalIntelligenceLatest.operational_intelligence_status, "watch")],
                ["Score", getNumber(operationalIntelligenceLatest.operational_intelligence_score, 0).toFixed(2)],
                ["Grade", getString(operationalIntelligenceLatest.operational_intelligence_grade, "blocked")],
                ["History", String(operationalIntelligenceHistory.length)],
                ["Analysis", getString(operationalIntelligenceLatest.latest_operational_intelligence?.analysis_id, "n/a")],
                ["Decision", getString(operationalIntelligenceLatest.latest_operational_intelligence?.operational_intelligence_decision, "defer_supervised_pilot")],
              ]}
            />

            <MetricPanel
              title="RFQ Trends"
              tone={getBooleanBadge(operationalIntelligenceLatest.rfq_trend_analysis?.total_rfqs > 0).tone}
              summary={`${getNumber(operationalIntelligenceLatest.rfq_trend_analysis?.rfq_trend_score, 0).toFixed(2)} trend score`}
              items={[
                ["Total RFQs", String(getNumber(operationalIntelligenceLatest.rfq_trend_analysis?.total_rfqs, 0))],
                ["Trend", getString(operationalIntelligenceLatest.rfq_trend_analysis?.queue_trend?.trend, "unknown")],
                ["Stage count", String(Object.keys(operationalIntelligenceLatest.rfq_trend_analysis?.stage_counts || {}).length)],
                ["Submitted", String(getNumber(operationalIntelligenceLatest.rfq_trend_analysis?.stage_counts?.SUBMITTED, 0))],
                ["Submission ready", String(getNumber(operationalIntelligenceLatest.rfq_trend_analysis?.stage_counts?.SUBMISSION_READY, 0))],
                ["Modality", getString(operationalIntelligenceLatest.submission_modality_utilization_analysis?.dominant_modality, "unsupported")],
              ]}
            />

            <MetricPanel
              title="Governance Health"
              tone={Object.values(operationalIntelligenceLatest.governance_degradation_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(operationalIntelligenceLatest.governance_degradation_indicators || {}).filter(Boolean).length} degradation flag(s)`}
              items={[
                ["Bottleneck", getBooleanBadge(operationalIntelligenceLatest.governance_degradation_indicators?.bottleneck_warning ? false : true).label],
                ["Compliance", getBooleanBadge(operationalIntelligenceLatest.governance_degradation_indicators?.compliance_warning ? false : true).label],
                ["Anomaly", getBooleanBadge(operationalIntelligenceLatest.governance_degradation_indicators?.anomaly_warning ? false : true).label],
                ["Supervision", getBooleanBadge(operationalIntelligenceLatest.governance_degradation_indicators?.supervision_warning ? false : true).label],
                ["Throughput", getBooleanBadge(operationalIntelligenceLatest.governance_degradation_indicators?.throughput_warning ? false : true).label],
                ["Final readiness", getBooleanBadge(operationalIntelligenceLatest.governance_degradation_indicators?.final_readiness_warning ? false : true).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Operational Intelligence History</h3>
                <StatusBadge label={`${operationalIntelligenceHistory.length} analysis(es)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operationalIntelligenceHistory.length ? (
                      operationalIntelligenceHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.operational_intelligence_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.operational_intelligence_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No operational intelligence history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Intelligence Analysis</h3>
                <StatusBadge label={getString(operationalIntelligenceLatest.operational_intelligence_status, "watch")} tone={getString(operationalIntelligenceLatest.operational_intelligence_status, "watch") === "ok" ? "ok" : getString(operationalIntelligenceLatest.operational_intelligence_status, "watch") === "blocked" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Modality utilization: {getString(operationalIntelligenceLatest.submission_modality_utilization_analysis?.dominant_modality, "unsupported")}</div>
                <div>Bottleneck: {getString(operationalIntelligenceLatest.operational_bottleneck_analysis?.bottleneck_status, "watch")}</div>
                <div>Compliance drift: {getString(operationalIntelligenceLatest.compliance_drift_analysis?.compliance_drift_status, "watch")}</div>
                <div>Anomaly severity: {getString(operationalIntelligenceLatest.governance_anomaly_analysis?.anomaly_severity, "low")}</div>
                <div>Supervision load: {getString(operationalIntelligenceLatest.supervision_load_analysis?.supervision_load?.supervision_load_status, "watch")}</div>
                <div>Throughput: {getString(operationalIntelligenceLatest.operational_throughput_analysis?.operational_throughput_status, "watch")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Executive Procurement Command</h2>
              <p className="text-sm text-slate-400">
                Read-only executive forecasts and strategic analytics for supervised procurement operations.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only executive command" : "Read-only executive command"}
              tone="neutral"
            />
          </div>

          {executiveCommandWarnings.length ? (
            <div className="space-y-3">
              {executiveCommandWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Executive command forecasts remain within current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Executive Score"
              tone={executiveCommandStatus === "ok" ? "ok" : executiveCommandStatus === "blocked" ? "error" : "neutral"}
              summary={`${executiveCommandGrade} • ${executiveCommandScore.toFixed(2)}`}
              items={[
                ["Status", executiveCommandStatus],
                ["Score", executiveCommandScore.toFixed(2)],
                ["Grade", executiveCommandGrade],
                ["History", String(executiveCommandHistory.length)],
                ["Analysis", getString(executiveCommandForecast.analysis_id, "n/a")],
                ["Decision", getString(executiveCommandForecast.executive_governance_decision, "defer_supervised_pilot")],
              ]}
            />

            <MetricPanel
              title="Forecasts"
              tone={executiveRiskIndicators.high_risk ? "error" : "ok"}
              summary={`${getNumber(executiveCommandForecast.procurement_health_score, executiveCommandScore).toFixed(2)} health`}
              items={[
                ["Throughput", getNumber(executiveCommandForecast.procurement_throughput_forecast?.score, 0).toFixed(2)],
                ["Risk", getNumber(executiveCommandForecast.operational_risk_forecast?.score, 0).toFixed(2)],
                ["Governance", getNumber(executiveCommandForecast.governance_degradation_forecast?.score, 0).toFixed(2)],
                ["Supervision", getNumber(executiveCommandForecast.supervision_capacity_forecast?.score, 0).toFixed(2)],
                ["Trend", getString(executiveCommandForecast.procurement_trend_forecast?.trend, "stable")],
                ["Escalation", getNumber(executiveCommandForecast.escalation_forecast?.score, 0).toFixed(2)],
              ]}
            />

            <MetricPanel
              title="Risk Indicators"
              tone={executiveRiskIndicators.high_risk ? "error" : "ok"}
              summary={`${Object.values(executiveRiskIndicators || {}).filter(Boolean).length} risk flag(s)`}
              items={[
                ["High risk", getBooleanBadge(executiveRiskIndicators.high_risk).label],
                ["Governance degradation", getBooleanBadge(executiveRiskIndicators.governance_degradation).label],
                ["Supervision saturation", getBooleanBadge(executiveRiskIndicators.supervision_saturation).label],
                ["Final readiness blocked", getBooleanBadge(executiveRiskIndicators.final_readiness_blocked).label],
                ["Review backlog", getBooleanBadge(executiveSaturationIndicators.review_backlog).label],
                ["Queue pressure", getBooleanBadge(executiveSaturationIndicators.queue_pressure).label],
              ]}
            />

            <MetricPanel
              title="Strategic Readiness"
              tone={executiveReadinessIndicators.ready_for_controlled_pilot ? "ok" : "error"}
              summary={`${getNumber(executiveCommandHistorySummary.latest_score, executiveCommandScore).toFixed(2)} history score`}
              items={[
                ["Ready for pilot", getBooleanBadge(executiveReadinessIndicators.ready_for_controlled_pilot).label],
                ["Intelligence ready", getBooleanBadge(executiveReadinessIndicators.intelligence_ready).label],
                ["Stability ready", getBooleanBadge(executiveReadinessIndicators.stability_ready).label],
                ["Execution ready", getBooleanBadge(executiveReadinessIndicators.execution_ready).label],
                ["Forecast trend", getString(executiveForecastingIndicators.trend, "stable")],
                ["Forecast decision", getString(executiveForecastingIndicators.decision, "defer_supervised_pilot")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Executive Intelligence History</h3>
                <StatusBadge label={`${executiveCommandHistory.length} forecast(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executiveCommandHistory.length ? (
                      executiveCommandHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.executive_governance_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.executive_governance_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No executive intelligence history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Executive Forecast Indicators</h3>
                <StatusBadge label={executiveCommandStatus} tone={executiveCommandStatus === "ok" ? "ok" : executiveCommandStatus === "blocked" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Throughput forecast: {getString(executiveCommandForecast.procurement_throughput_forecast?.trend, "stable")}</div>
                <div>Operational risk: {getString(executiveCommandForecast.operational_risk_forecast?.trend, "stable")}</div>
                <div>Governance degradation: {getString(executiveCommandForecast.governance_degradation_forecast?.trend, "stable")}</div>
                <div>Supervision capacity: {getString(executiveCommandForecast.supervision_capacity_forecast?.trend, "stable")}</div>
                <div>Forecasting trend: {getString(executiveCommandForecast.procurement_trend_forecast?.trend, "stable")}</div>
                <div>Escalation trend: {getString(executiveCommandForecast.escalation_forecast?.trend, "stable")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Executive Governance Index</h2>
              <p className="text-sm text-slate-400">
                Consolidated read-only governance overview spanning activation, supervision, audit, incident, continuity, release, intelligence, and executive command.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only governance index" : "Read-only governance index"}
              tone="neutral"
            />
          </div>

          {governanceIndexWarnings.length ? (
            <div className="space-y-3">
              {governanceIndexWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Executive governance index remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Governance Index"
              tone={governanceIndexStatus === "ok" ? "ok" : governanceIndexStatus === "blocked" ? "error" : "neutral"}
              summary={`${governanceIndexGrade} • ${governanceIndexScore.toFixed(2)}`}
              items={[
                ["Status", governanceIndexStatus],
                ["Authority", governanceIndexAuthority],
                ["Score", governanceIndexScore.toFixed(2)],
                ["Grade", governanceIndexGrade],
                ["History", String(governanceIndexHistory.length)],
                ["Trend", getString(governanceIndexHistorySummary.score_history?.trend, "stable")],
                ["Analysis", getString(governanceIndexLatest.latest_executive_governance_index?.analysis_id, "n/a")],
              ]}
            />

            <MetricPanel
              title="Readiness Domains"
              tone={getBooleanBadge(Boolean(governanceIndexInstitutional.ready_for_controlled_rollout)).tone}
              summary={`${getNumber(governanceIndexInstitutional.rollout_readiness_score, governanceIndexScore).toFixed(2)} rollout score`}
              items={[
                ["Activation", getBooleanBadge(getString(governanceIndexActivation.authority, "WATCH") === "GO").label],
                ["Supervision", getBooleanBadge(getString(governanceIndexSupervision.authority, "WATCH") === "GO").label],
                ["Audit", getBooleanBadge(getString(governanceIndexAudit.authority, "WATCH") === "GO").label],
                ["Incident", getBooleanBadge(getString(governanceIndexIncident.authority, "WATCH") === "GO").label],
                ["Continuity", getBooleanBadge(getString(governanceIndexContinuity.authority, "WATCH") === "GO").label],
                ["Intelligence", getBooleanBadge(getString(governanceIndexIntelligence.authority, "WATCH") === "GO").label],
                ["Release", getBooleanBadge(getString(governanceIndexRelease.authority, "WATCH") === "GO").label],
              ]}
            />

            <MetricPanel
              title="Risk & Escalation"
              tone={Object.values(governanceIndexEscalation || {}).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(governanceIndexDegradation || {}).filter(Boolean).length} degradation flag(s)`}
              items={[
                ["Activation", getBooleanBadge(governanceIndexDegradation.activation_degradation ? false : true).label],
                ["Supervision", getBooleanBadge(governanceIndexDegradation.supervision_degradation ? false : true).label],
                ["Audit", getBooleanBadge(governanceIndexDegradation.audit_degradation ? false : true).label],
                ["Incident", getBooleanBadge(governanceIndexDegradation.incident_degradation ? false : true).label],
                ["Continuity", getBooleanBadge(governanceIndexDegradation.continuity_degradation ? false : true).label],
                ["Release blocker", getBooleanBadge(governanceIndexEscalation.release_blocker ? false : true).label],
              ]}
            />

            <MetricPanel
              title="Institutional Rollout"
              tone={governanceIndexInstitutional.ready_for_controlled_rollout ? "ok" : "error"}
              summary={`${getNumber(governanceIndexInstitutional.rollout_readiness_score, governanceIndexScore).toFixed(2)} readiness score`}
              items={[
                ["Ready", getBooleanBadge(governanceIndexInstitutional.ready_for_controlled_rollout).label],
                ["Release valid", getBooleanBadge(governanceIndexInstitutional.release_authority_valid).label],
                ["Activation ready", getBooleanBadge(governanceIndexInstitutional.activation_ready).label],
                ["Supervision ready", getBooleanBadge(governanceIndexInstitutional.supervision_ready).label],
                ["Audit ready", getBooleanBadge(governanceIndexInstitutional.audit_ready).label],
                ["Human supervision", getBooleanBadge(governanceIndexEscalation.human_supervision_required).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Governance Index History</h3>
                <StatusBadge label={`${governanceIndexHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Authority</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {governanceIndexHistory.length ? (
                      governanceIndexHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.executive_governance_index_authority, "WATCH")}</td>
                          <td className="p-3">{getString(item.executive_governance_index_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.executive_governance_index_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No executive governance index history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Governance Index Indicators</h3>
                <StatusBadge label={governanceIndexAuthority} tone={governanceIndexAuthority === "GO" ? "ok" : governanceIndexAuthority === "NO_GO" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Activation ready: {getBooleanBadge(governanceIndexInstitutional.activation_ready).label}</div>
                <div>Supervision ready: {getBooleanBadge(governanceIndexInstitutional.supervision_ready).label}</div>
                <div>Audit ready: {getBooleanBadge(governanceIndexInstitutional.audit_ready).label}</div>
                <div>Incident ready: {getBooleanBadge(governanceIndexInstitutional.incident_ready).label}</div>
                <div>Continuity ready: {getBooleanBadge(governanceIndexInstitutional.continuity_ready).label}</div>
                <div>Intelligence ready: {getBooleanBadge(governanceIndexInstitutional.intelligence_ready).label}</div>
                <div>Governance degradation: {String(Object.values(governanceIndexDegradation || {}).filter(Boolean).length)}</div>
                <div>Escalation indicators: {String(Object.values(governanceIndexEscalation || {}).filter(Boolean).length)}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Enterprise Production Operationalization</h2>
              <p className="text-sm text-slate-400">
                Read-only enterprise deployment readiness governance using staging evidence and executive forecasts.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only production governance" : "Read-only production governance"}
              tone="neutral"
            />
          </div>

          {productionOperationalizationWarnings.length ? (
            <div className="space-y-3">
              {productionOperationalizationWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Production operationalization remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Production Readiness"
              tone={productionReadinessStatus === "ok" ? "ok" : productionReadinessStatus === "blocked" ? "error" : "neutral"}
              summary={`${productionReadinessGrade} • ${productionReadinessScore.toFixed(2)}`}
              items={[
                ["Status", productionReadinessStatus],
                ["Score", productionReadinessScore.toFixed(2)],
                ["Grade", productionReadinessGrade],
                ["History", String(productionOperationalizationHistory.length)],
                ["Analysis", getString(productionOperationalizationLatest.analysis_id, "n/a")],
                ["Decision", getString(productionOperationalizationLatest.latest_production_governance?.production_governance_summary?.decision, "defer_enterprise_deployment")],
              ]}
            />

            <MetricPanel
              title="Runtime Segmentation"
              tone={getBooleanBadge(productionSegmentation?.tenant_workspace_isolation?.isolation_verified).tone}
              summary={`${getNumber(productionSegmentation?.production_runtime_segmentation_score, 0).toFixed(2)} segmentation score`}
              items={[
                ["Tenant count", String(getNumber(productionSegmentation?.tenant_workspace_isolation?.tenant_count, 0))],
                ["Workspace count", String(getNumber(productionSegmentation?.tenant_workspace_isolation?.workspace_count, 0))],
                ["Pairs", String(getNumber(productionSegmentation?.tenant_workspace_isolation?.tenant_workspace_pair_count, 0))],
                ["Isolation", getBooleanBadge(productionSegmentation?.tenant_workspace_isolation?.isolation_verified).label],
                ["Status", getString(productionSegmentation?.production_runtime_segmentation_status, "watch")],
                ["Grade", getString(productionSegmentation?.production_runtime_segmentation_grade, "blocked")],
              ]}
            />

            <MetricPanel
              title="Access & Observability"
              tone={productionAccessRiskIndicators.pending_approval_backlog || productionAccessRiskIndicators.operator_role_mismatch ? "error" : "ok"}
              summary={`${getNumber(productionAccess?.operator_access_governance_score, 0).toFixed(2)} access score`}
              items={[
                ["Access status", getString(productionAccess?.operator_access_governance_status, "watch")],
                ["Observability", getString(productionObservability?.production_observability_governance_status, "watch")],
                ["Backup", getString(productionBackup?.backup_restore_governance_status, "watch")],
                ["Recovery", getString(productionDisasterRecovery?.disaster_recovery_governance_status, "watch")],
                ["HA", getString(productionHighAvailability?.high_availability_governance_status, "watch")],
                ["Audit", getString(productionAuditRetention?.audit_retention_governance_status, "watch")],
              ]}
            />

            <MetricPanel
              title="Deployment Readiness"
              tone={productionRiskIndicators.deployment_risk ? "error" : "ok"}
              summary={`${getNumber(productionDeployment?.deployment_readiness_governance_score, 0).toFixed(2)} deployment score`}
              items={[
                ["Deployment", getString(productionDeployment?.deployment_readiness_governance_status, "watch")],
                ["Operator risk", getBooleanBadge(productionAccessRiskIndicators.pending_approval_backlog).label],
                ["HA ready", getBooleanBadge(productionHAIndicators.queue_stable).label],
                ["Recovery ready", getBooleanBadge(productionRecoveryIndicators.final_readiness_cleared).label],
                ["Backup ready", getBooleanBadge(productionBackup?.backup_restore_governance_status === "ok").label],
                ["Observability ready", getBooleanBadge(productionObservability?.production_observability_governance_status === "ok").label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Production Governance History</h3>
                <StatusBadge label={`${productionOperationalizationHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productionOperationalizationHistory.length ? (
                      productionOperationalizationHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.production_readiness_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.production_readiness_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No production governance history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Readiness Indicators</h3>
                <StatusBadge label={productionReadinessStatus} tone={productionReadinessStatus === "ok" ? "ok" : productionReadinessStatus === "blocked" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Operator access: {getString(productionAccess?.operator_access_governance_status, "watch")}</div>
                <div>Observability: {getString(productionObservability?.production_observability_governance_status, "watch")}</div>
                <div>Backup restore: {getString(productionBackup?.backup_restore_governance_status, "watch")}</div>
                <div>Disaster recovery: {getString(productionDisasterRecovery?.disaster_recovery_governance_status, "watch")}</div>
                <div>High availability: {getString(productionHighAvailability?.high_availability_governance_status, "watch")}</div>
                <div>Audit retention: {getString(productionAuditRetention?.audit_retention_governance_status, "watch")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Command Centre Distributed Orchestration</h2>
              <p className="text-sm text-slate-400">
                Read-only staging orchestration visibility for queue partition readiness, worker shard readiness, autoscaling readiness, failover orchestration, supervision coverage, and saturation pressure.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only orchestration" : "Read-only orchestration"}
              tone="neutral"
            />
          </div>

          {distributedOrchestrationWarnings.length ? (
            <div className="space-y-3">
              {distributedOrchestrationWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Distributed orchestration recovery remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            <MetricPanel
              title="Orchestration State"
              tone={distributedOrchestrationRecoveryState === "recovered" ? "ok" : distributedOrchestrationRecoveryState === "unresolved-blocked" ? "error" : "neutral"}
              summary={`${distributedOrchestrationRecoveryState} • ${distributedOrchestrationScore.toFixed(2)}`}
              items={[
                ["Status", distributedOrchestrationStatus],
                ["Authority", distributedOrchestrationAuthority],
                ["Score", distributedOrchestrationScore.toFixed(2)],
                ["Grade", distributedOrchestrationGrade],
                ["History", String(distributedOrchestrationHistory.length)],
                ["Recovery state", distributedOrchestrationRecoveryState],
              ]}
            />

            <MetricPanel
              title="Readiness Signals"
              tone={getBooleanBadge(distributedOrchestrationRecoveryState === "recovered").tone}
              summary={`${[
                distributedOrchestrationQueue.queue_partition_ready,
                distributedOrchestrationWorker.worker_shard_ready,
                distributedOrchestrationAutoscaling.autoscaling_ready,
                distributedOrchestrationFailover.failover_orchestration_ready,
                distributedOrchestrationSupervision.distributed_supervision_coverage_ready,
              ].filter(Boolean).length}/5 ready`}
              items={[
                ["Queue partition", getBooleanBadge(distributedOrchestrationQueue.queue_partition_ready).label],
                ["Worker shard", getBooleanBadge(distributedOrchestrationWorker.worker_shard_ready).label],
                ["Autoscaling", getBooleanBadge(distributedOrchestrationAutoscaling.autoscaling_ready).label],
                ["Failover", getBooleanBadge(distributedOrchestrationFailover.failover_orchestration_ready).label],
                ["Supervision coverage", getBooleanBadge(distributedOrchestrationSupervision.distributed_supervision_coverage_ready).label],
                ["Workload pressure", getString(distributedOrchestrationWorkload.workload_pressure, "low")],
              ]}
            />

            <MetricPanel
              title="Degradation Signals"
              tone={Object.values(distributedOrchestrationDegradation || {}).some(Boolean) || Boolean(distributedOrchestrationWorkload.supervision_saturation_active) ? "error" : "ok"}
              summary={`${distributedOrchestrationBlockers.length} blocker(s)`}
              items={[
                ["Queue degradation", getBooleanBadge(distributedOrchestrationDegradation.queue_partition_degradation).label],
                ["Worker degradation", getBooleanBadge(distributedOrchestrationDegradation.worker_shard_degradation).label],
                ["Autoscaling degradation", getBooleanBadge(distributedOrchestrationDegradation.autoscaling_degradation).label],
                ["Failover degradation", getBooleanBadge(distributedOrchestrationDegradation.failover_orchestration_degradation).label],
                ["Saturation active", getBooleanBadge(distributedOrchestrationWorkload.supervision_saturation_active).label],
                ["Blocker sources", String(distributedOrchestrationBlockerSources.length)],
              ]}
            />

            <MetricPanel
              title="Recovery Rationale"
              tone={distributedOrchestrationRecoveryState === "recovered" ? "ok" : distributedOrchestrationRecoveryState === "unresolved-blocked" ? "error" : "neutral"}
              summary={`${getNumber(distributedOrchestrationRationale.score_impact?.final_score, distributedOrchestrationScore).toFixed(2)} final score`}
              items={[
                ["Base score", getNumber(distributedOrchestrationRationale.score_impact?.base_score, 0).toFixed(2)],
                ["Deductions", getNumber(distributedOrchestrationRationale.score_impact?.deductions, 0).toFixed(2)],
                ["Final score", getNumber(distributedOrchestrationRationale.score_impact?.final_score, distributedOrchestrationScore).toFixed(2)],
                ["Blockers", String(distributedOrchestrationBlockers.length)],
                ["State basis", String(getNumber(distributedOrchestrationRationale.state_basis?.unresolved_blocker_count, 0))],
                ["Summary", getString(distributedOrchestrationRationale.summary, "n/a")],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Orchestration Governance History</h3>
                <StatusBadge label={`${distributedOrchestrationHistory.length} checkpoint(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Analysis</th>
                      <th className="p-3 text-left">State</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {distributedOrchestrationHistory.length ? (
                      distributedOrchestrationHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.analysis_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.analysis_id, "n/a")}</td>
                          <td className="p-3">{getString(item.recovery_state, "degraded-but-recovering")}</td>
                          <td className="p-3">{getString(item.distributed_orchestration_status, "watch")}</td>
                          <td className="p-3 text-right">{getNumber(item.distributed_orchestration_score, 0).toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={4}>
                          No distributed orchestration history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Blockers and Rationale</h3>
                <StatusBadge label={distributedOrchestrationRecoveryState} tone={distributedOrchestrationRecoveryState === "recovered" ? "ok" : distributedOrchestrationRecoveryState === "unresolved-blocked" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <div>Final recovery state: {distributedOrchestrationRecoveryState}</div>
                <div>Recovery rationale: {getString(distributedOrchestrationRationale.summary, "n/a")}</div>
                <div>Score impact: {getNumber(distributedOrchestrationRationale.score_impact?.base_score, 0).toFixed(2)} {"->"} {getNumber(distributedOrchestrationRationale.score_impact?.final_score, distributedOrchestrationScore).toFixed(2)}</div>
                <div>Blocker sources: {String(distributedOrchestrationBlockerSources.length)}</div>
                <div>Unresolved blockers: {String(distributedOrchestrationBlockers.length)}</div>
                <div className="space-y-2 rounded-xl border border-slate-800 bg-slate-950 p-4">
                  {distributedOrchestrationBlockers.length ? (
                    distributedOrchestrationBlockers.map((blocker, index) => (
                      <div key={`${blocker}-${index}`} className="rounded-lg border border-amber-700/60 bg-amber-950/50 p-3 text-amber-100">
                        {getString(blocker, "n/a")}
                      </div>
                    ))
                  ) : (
                    <div className="text-emerald-200">No unresolved blockers remain in the staged evidence.</div>
                  )}
                </div>
                <div className="space-y-2">
                  {distributedOrchestrationBlockerSources.map((source: Record<string, any>) => (
                    <div key={getString(source.source, Math.random().toString())} className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                      <div className="font-medium text-slate-100">{getString(source.source, "n/a")}</div>
                      <div className="text-slate-400">Ready: {getBooleanBadge(source.ready).label}</div>
                      <div className="text-slate-400">Blockers: {String(Array.isArray(source.blockers) ? source.blockers.length : 0)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Controlled Operational Pilot Execution</h2>
              <p className="text-sm text-slate-400">
                Read-only operational endurance, stability, cadence, and supervision tracking for supervised pilot execution.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only operational pilot" : "Read-only operational pilot"}
              tone="neutral"
            />
          </div>

          {operationalPilotWarnings.length ? (
            <div className="space-y-3">
              {operationalPilotWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Operational pilot execution remains within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Execution Status"
              tone={getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "PASS" || getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "ok" ? "ok" : getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "FAIL" || getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "blocked" ? "error" : "neutral"}
              summary={`${getString(operationalPilotLatest.operational_pilot_execution_grade, "not_ready")} • ${getNumber(operationalPilotLatest.operational_endurance_score, 0).toFixed(2)}`}
              items={[
                ["Status", getString(operationalPilotLatest.operational_pilot_execution_status, "watch")],
                ["Endurance", getNumber(operationalPilotLatest.operational_endurance_score, 0).toFixed(2)],
                ["Stability", getNumber(operationalPilotLatest.sustained_stability_score, 0).toFixed(2)],
                ["Decision", getString(operationalPilotLatest.operational_pilot_execution_decision, "defer_supervised_pilot")],
                ["History", String(operationalPilotHistory.length)],
                ["Review interval", `${getNumber(operationalPilotLatest.operational_review_interval_hours, 0).toFixed(2)}h`],
              ]}
            />

            <MetricPanel
              title="Reliability Indicators"
              tone={Object.values(operationalPilotLatest.supervised_execution_reliability_indicators || {}).some((value) => value === false) ? "error" : "ok"}
              summary={`${Object.values(operationalPilotLatest.supervised_execution_reliability_indicators || {}).filter(Boolean).length} / ${Object.keys(operationalPilotLatest.supervised_execution_reliability_indicators || {}).length} passing`}
              items={[
                ["Governance checkpoint", getBooleanBadge(operationalPilotLatest.supervised_execution_reliability_indicators?.governance_checkpoint_verified).label],
                ["Cadence enforced", getBooleanBadge(operationalPilotLatest.supervised_execution_reliability_indicators?.rehearsal_cadence_enforced).label],
                ["Concurrency enforced", getBooleanBadge(operationalPilotLatest.supervised_execution_reliability_indicators?.concurrency_limit_enforced).label],
                ["Operator ack", getBooleanBadge(operationalPilotLatest.supervised_execution_reliability_indicators?.operator_acknowledged).label],
                ["Submission lock", getBooleanBadge(operationalPilotLatest.supervised_execution_reliability_indicators?.submission_lock_verified).label],
                ["Dry-run", getBooleanBadge(operationalPilotLatest.supervised_execution_reliability_indicators?.dry_run_verified).label],
              ]}
            />

            <MetricPanel
              title="Degradation Indicators"
              tone={Object.values(operationalPilotLatest.operational_degradation_indicators || {}).some(Boolean) ? "error" : "ok"}
              summary={`${Object.values(operationalPilotLatest.operational_degradation_indicators || {}).filter(Boolean).length} degradation flag(s)`}
              items={[
                ["Queue", getBooleanBadge(operationalPilotLatest.operational_degradation_indicators?.queue_degradation ? false : true).label],
                ["Worker", getBooleanBadge(operationalPilotLatest.operational_degradation_indicators?.worker_degradation ? false : true).label],
                ["Telemetry", getBooleanBadge(operationalPilotLatest.operational_degradation_indicators?.telemetry_degradation ? false : true).label],
                ["Retry", getBooleanBadge(operationalPilotLatest.operational_degradation_indicators?.retry_degradation ? false : true).label],
                ["Rollback", getBooleanBadge(operationalPilotLatest.operational_degradation_indicators?.rollback_degradation ? false : true).label],
                ["NO-GO", getBooleanBadge(operationalPilotLatest.operational_degradation_indicators?.no_go_degradation ? false : true).label],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Execution Governance History</h3>
                <StatusBadge label={`${operationalPilotHistory.length} cycle(s)`} tone="neutral" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Cycle</th>
                      <th className="p-3 text-left">Decision</th>
                      <th className="p-3 text-right">Endurance</th>
                      <th className="p-3 text-right">Stability</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operationalPilotHistory.length ? (
                      operationalPilotHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.cycle_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.cycle_id, "n/a")}</td>
                          <td className="p-3">{getString(item.operational_pilot_execution_decision, "defer_supervised_pilot")}</td>
                          <td className="p-3 text-right">{getNumber(item.operational_endurance_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-right">{getNumber(item.sustained_stability_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No operational pilot execution history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Execution Evidence Aggregation</h3>
                <StatusBadge label={getString(operationalPilotLatest.operational_pilot_execution_decision, "defer_supervised_pilot")} tone={getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "PASS" || getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "ok" ? "ok" : getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "FAIL" || getString(operationalPilotLatest.operational_pilot_execution_status, "watch") === "blocked" ? "error" : "neutral"} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Evidence pack: {getBooleanBadge(operationalPilotLatest.supervised_execution_evidence_aggregation?.evidence_pack_present).label}</div>
                <div>Queue status: {getString(operationalPilotLatest.supervised_execution_evidence_aggregation?.queue_stability_evidence?.status, "n/a")}</div>
                <div>Worker status: {getString(operationalPilotLatest.supervised_execution_evidence_aggregation?.worker_stability_evidence?.status, "n/a")}</div>
                <div>Telemetry status: {getString(operationalPilotLatest.supervised_execution_evidence_aggregation?.telemetry_health_evidence?.status, "n/a")}</div>
                <div>Submission lock: {getString(operationalPilotLatest.supervised_execution_evidence_aggregation?.submission_lock_verification?.status, "n/a")}</div>
                <div>Dry-run: {getString(operationalPilotLatest.supervised_execution_evidence_aggregation?.dry_run_enforcement_verification?.status, "n/a")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Review Board</h2>
              <p className="text-sm text-slate-400">
                Read-only institutional governance review for recurring pilot oversight, exceptions, and escalation tracking.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only review board" : "Read-only review board"}
              tone="neutral"
            />
          </div>

          {reviewBoardWarnings.length ? (
            <div className="space-y-3">
              {reviewBoardWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Governance review-board status is within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Review-Board Status"
              tone={reviewBoardStatus === "ok" ? "ok" : reviewBoardStatus === "watch" ? "neutral" : "error"}
              summary={`${getString(reviewBoardSummary.latest_recommendation, "review_required")} • ${reviewBoardScore.toFixed(2)}`}
              items={[
                ["Status", reviewBoardStatus],
                ["Score", reviewBoardScore.toFixed(2)],
                ["Latest review", getString(reviewBoardLatest.latest_session?.review_id, "n/a")],
                ["Latest readiness", `${getNumber(reviewBoardSummary.latest_readiness_score, 0).toFixed(2)}`],
                ["Latest trend", getString(reviewBoardSummary.latest_trend, "stable")],
                ["Sessions", String(getNumber(reviewBoardSummary.session_count, 0))],
              ]}
            />

            <MetricPanel
              title="Governance Review History"
              tone="neutral"
              summary={`${reviewBoardHistory.length} review session(s)`}
              items={[
                ["Runs last 7 days", String(getNumber(reviewBoardHistoryCadence.runs_last_7_days, 0))],
                ["Average gap hours", `${getNumber(reviewBoardHistoryCadence.average_gap_hours, 0).toFixed(2)}`],
                ["Most recent", getString(reviewBoardHistoryCadence.most_recent_review_at, "n/a")],
                ["Previous", getString(reviewBoardHistoryCadence.previous_review_at, "n/a")],
                ["Cadence status", getString(reviewBoardHistoryCadence.status, "unknown")],
                ["Window days", String(getNumber(reviewBoardHistoryCadence.window_days, 7))],
              ]}
            />

            <MetricPanel
              title="Operational Exceptions"
              tone={reviewBoardOutstanding.length || reviewBoardExceptions.length ? "error" : "ok"}
              summary={`${reviewBoardOutstanding.length} outstanding / ${reviewBoardExceptions.length} unresolved`}
              items={[
                ["Outstanding actions", String(reviewBoardOutstanding.length)],
                ["Unresolved exceptions", String(reviewBoardExceptions.length)],
                ["Escalation items", String(getNumber(reviewBoardEscalation.count, 0))],
                ["Submission lock", getString(reviewBoardLatest.submission_lock_status, "unknown")],
                ["Dry-run", getString(reviewBoardLatest.dry_run_status, "unknown")],
                ["NO-GO", getString(reviewBoardLatest.no_go_status, "unknown")],
              ]}
            />
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">Review-Board History</h3>
              <StatusBadge label={`${reviewBoardHistory.length} session(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Review</th>
                    <th className="p-3 text-left">Status</th>
                    <th className="p-3 text-right">Score</th>
                    <th className="p-3 text-right">Outstanding</th>
                    <th className="p-3 text-right">Exceptions</th>
                    <th className="p-3 text-left">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewBoardHistory.length ? (
                    reviewBoardHistory.map((item: Record<string, any>) => (
                      <tr key={getString(item.review_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.review_id, "n/a")}</td>
                        <td className="p-3">
                          <StatusBadge
                            label={getString(item.review_board_status, "unknown")}
                            tone={item.review_board_status === "ok" ? "ok" : item.review_board_status === "watch" ? "neutral" : "error"}
                          />
                        </td>
                        <td className="p-3 text-right">{getNumber(item.readiness_score, 0).toFixed(2)}</td>
                        <td className="p-3 text-right">{Array.isArray(item.outstanding_governance_actions) ? item.outstanding_governance_actions.length : 0}</td>
                        <td className="p-3 text-right">{Array.isArray(item.unresolved_operational_exceptions) ? item.unresolved_operational_exceptions.length : 0}</td>
                        <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={6}>
                        No governance review-board history is available yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Recurring Controlled Pilot Cycles</h2>
              <p className="text-sm text-slate-400">
                Longitudinal pilot-cycle oversight with recurring readiness, NO-GO, governance, and stability summaries.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only recurring cycles" : "Read-only recurring cycles"}
              tone="neutral"
            />
          </div>

          {recurringCycleWarnings.length ? (
            <div className="space-y-3">
              {recurringCycleWarnings.map((warning, index) => (
                <div key={`${warning}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {warning}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-700 bg-emerald-950/40 p-4 text-emerald-100">
              Recurring controlled pilot cycles are within the current staging thresholds.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Recurring Cycle Status"
              tone={recurringCycleStatus === "ok" ? "ok" : recurringCycleStatus === "watch" ? "neutral" : "error"}
              summary={`${recurringCycleGrade} • ${recurringCycleScore.toFixed(2)}`}
              items={[
                ["Status", recurringCycleStatus],
                ["Score", recurringCycleScore.toFixed(2)],
                ["Grade", recurringCycleGrade],
                ["Latest cycle", getString(recurringCycleLatest.cycle_id, "n/a")],
                ["Total cycles", String(getNumber(recurringCycleSummaryCounts.PASS, 0) + getNumber(recurringCycleSummaryCounts.WARN, 0) + getNumber(recurringCycleSummaryCounts.FAIL, 0))],
                ["History entries", String(recurringCyclesHistory.length)],
              ]}
            />

            <MetricPanel
              title="Governance Compliance"
              tone={getString(recurringCompliance.status, "PASS") === "PASS" ? "ok" : getString(recurringCompliance.status, "PASS") === "WARN" ? "neutral" : "error"}
              summary={`${getNumber(recurringCompliance.compliance_rate, 0).toFixed(2)}% compliant`}
              items={[
                ["Compliance rate", `${getNumber(recurringCompliance.compliance_rate, 0).toFixed(2)}%`],
                ["Governance checkpoint", `${getNumber(recurringCompliance.governance_checkpoint_pass_rate, 0).toFixed(2)}%`],
                ["Submission lock", `${getNumber(recurringCompliance.submission_lock_pass_rate, 0).toFixed(2)}%`],
                ["Dry-run", `${getNumber(recurringCompliance.dry_run_pass_rate, 0).toFixed(2)}%`],
                ["NO-GO clear", `${getNumber(recurringCompliance.no_go_clear_rate, 0).toFixed(2)}%`],
                ["Operator acknowledgement", `${getNumber(recurringCompliance.operator_acknowledgement_rate, 0).toFixed(2)}%`],
              ]}
            />

            <MetricPanel
              title="Operational Endurance"
              tone={getNumber(recurringEndurance.clean_cycle_rate, 0) >= 85 ? "ok" : "neutral"}
              summary={`${getNumber(recurringEndurance.clean_cycle_rate, 0).toFixed(2)}% clean cycles`}
              items={[
                ["Clean cycle rate", `${getNumber(recurringEndurance.clean_cycle_rate, 0).toFixed(2)}%`],
                ["Readiness pass rate", `${getNumber(recurringEndurance.readiness_pass_rate, 0).toFixed(2)}%`],
                ["Evidence generation", `${getNumber(recurringEndurance.evidence_generation_rate, 0).toFixed(2)}%`],
                ["Stability snapshots", String(getNumber(recurringEndurance.stability_snapshot_count, 0))],
                ["Trend", getString(recurringCycleTrends.readiness?.trend, "unknown")],
                ["Delta", `${getNumber(recurringCycleTrends.readiness?.delta, 0).toFixed(2)}`],
              ]}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Longitudinal Pilot History</h3>
                <StatusBadge label={`${recurringCyclesHistory.length} cycle(s)`} tone="neutral" />
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Cycle</th>
                      <th className="p-3 text-left">Status</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-right">Artifacts</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recurringCyclesHistory.length ? (
                      recurringCyclesHistory.map((item: Record<string, any>) => (
                        <tr key={getString(item.cycle_id, Math.random().toString())} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.cycle_id, "n/a")}</td>
                          <td className="p-3">
                            <StatusBadge
                              label={getString(item.status, "unknown")}
                              tone={item.status === "PASS" ? "ok" : item.status === "FAIL" ? "error" : "neutral"}
                            />
                          </td>
                          <td className="p-3 text-right">{getNumber(item.readiness_score, 0).toFixed(2)}</td>
                          <td className="p-3 text-right">{getNumber(item.artifact_count, 0)}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No recurring pilot cycle history is available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Recurring Stability Snapshots</h3>
                <StatusBadge label={`${recurringStability.length} snapshot(s)`} tone="neutral" />
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-3 text-left">Cycle</th>
                      <th className="p-3 text-right">Queue</th>
                      <th className="p-3 text-right">Worker</th>
                      <th className="p-3 text-right">Telemetry</th>
                      <th className="p-3 text-left">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recurringStability.length ? (
                      recurringStability.map((item: Record<string, any>) => (
                        <tr key={`${getString(item.cycle_id, "cycle")}-${getString(item.generated_at, Math.random().toString())}`} className="border-t border-slate-800">
                          <td className="p-3 font-medium">{getString(item.cycle_id, "n/a")}</td>
                          <td className="p-3 text-right">{getString(item.queue_status, "n/a")}</td>
                          <td className="p-3 text-right">{getString(item.worker_status, "n/a")}</td>
                          <td className="p-3 text-right">{getString(item.telemetry_status, "n/a")}</td>
                          <td className="p-3 text-slate-400">{getString(item.generated_at, "n/a")}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-400" colSpan={5}>
                          No recurring stability snapshots are available yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold">Operational Rehearsal Evidence</h2>
              <p className="text-sm text-slate-400">
                Read-only rehearsal history, drill outcomes, and evidence artifacts. No controls are exposed.
              </p>
            </div>
            <StatusBadge
              label={APP_ENV === "staging" ? "Staging-only evidence" : "Read-only evidence"}
              tone="neutral"
            />
          </div>

          {Array.isArray(rehearsalLatest.warning_banners) && rehearsalLatest.warning_banners.length ? (
            <div className="space-y-3">
              {rehearsalLatest.warning_banners.map((banner: string, index: number) => (
                <div key={`${banner}-${index}`} className="rounded-xl border border-amber-700 bg-amber-950/50 p-4 text-amber-100">
                  {banner}
                </div>
              ))}
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <MetricPanel
              title="Latest Rehearsal"
              tone={getString(rehearsalLatest.status, "unknown") === "ok" ? "ok" : "neutral"}
              summary={getString(rehearsalLatest.run_id, "No rehearsal evidence")}
              items={[
                ["Generated", getString(rehearsalLatest.generated_at, "n/a")],
                ["PASS", String(getNumber(rehearsalLatest.run?.overall_counts?.PASS, 0))],
                ["WARN", String(getNumber(rehearsalLatest.run?.overall_counts?.WARN, 0))],
                ["FAIL", String(getNumber(rehearsalLatest.run?.overall_counts?.FAIL, 0))],
                ["Evidence files", String(getNumber(rehearsalArtifacts.artifact_count, 0))],
                ["Total size", `${getNumber(rehearsalArtifacts.total_size_bytes, 0)} bytes`],
              ]}
            />

            <MetricPanel
              title="Operational Health"
              tone={getString(rehearsalHealth.status, "unknown") === "ok" ? "ok" : "error"}
              summary={getString(rehearsalHealth.status, "unknown")}
              items={[
                ["Healthy", getBooleanBadge(rehearsalHealth.healthy).label],
                ["PASS", String(getNumber(rehearsalHealth.pass_count, 0))],
                ["WARN", String(getNumber(rehearsalHealth.warn_count, 0))],
                ["FAIL", String(getNumber(rehearsalHealth.fail_count, 0))],
                ["Dry-run", getBooleanBadge(rehearsalLatest.run?.dry_run_guarantees?.live_submissions === false).label],
                ["Environment", getString(rehearsalLatest.run?.environment_contract?.path, "n/a")],
              ]}
            />

            <MetricPanel
              title="Evidence Summary"
              tone="neutral"
              summary={`${rehearsalTimeline.length} timeline step(s)`}
              items={[
                ["Scenarios", String(getNumber(rehearsalLatest.run?.scenario_count, rehearsalTimeline.length))],
                ["Retry drill", getString(rehearsalDrills.retry_drill?.status, "n/a")],
                ["Rollback drill", getString(rehearsalDrills.rollback_drill?.status, "n/a")],
                ["Queue drill", getString(rehearsalDrills.queue_drill?.status, "n/a")],
                ["DLQ drill", getString(rehearsalDrills.dlq_drill?.status, "n/a")],
                ["Telemetry drill", getString(rehearsalDrills.telemetry_validation?.status, "n/a")],
              ]}
            />
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Rehearsal Timeline</h2>
              <StatusBadge label="Read-only" tone="neutral" />
            </div>

            <div className="mt-4 space-y-3">
              {rehearsalTimeline.length ? (
                rehearsalTimeline.map((step: Record<string, any>) => (
                  <div key={`${step.index}-${step.scenario}`} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{getString(step.scenario, "scenario")}</p>
                        <p className="text-xs text-slate-500">Step {getNumber(step.index, 0)}</p>
                      </div>
                      <StatusBadge label={getString(step.status, "unknown")} tone={step.status === "PASS" ? "ok" : step.status === "FAIL" ? "error" : "neutral"} />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-slate-300 md:grid-cols-4">
                      <div>Checks: {getNumber(step.checks, 0)}</div>
                      <div>Warnings: {getNumber(step.warnings, 0)}</div>
                      <div>Failures: {getNumber(step.failures, 0)}</div>
                      <div>Evidence: {getString(step.evidence_dir, "n/a")}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-slate-400">
                  No rehearsal timeline is available yet.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Rehearsal History</h2>
              <StatusBadge label={`${rehearsalHistory.length} run(s)`} tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">Run</th>
                    <th className="p-3 text-left">Status</th>
                    <th className="p-3 text-right">PASS</th>
                    <th className="p-3 text-right">WARN</th>
                    <th className="p-3 text-right">FAIL</th>
                    <th className="p-3 text-left">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {rehearsalHistory.length ? (
                    rehearsalHistory.map((run: Record<string, any>) => (
                      <tr key={getString(run.run_id, Math.random().toString())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(run.run_id, "n/a")}</td>
                        <td className="p-3">
                          <StatusBadge
                            label={getString(run.status, "unknown")}
                            tone={run.status === "PASS" ? "ok" : run.status === "FAIL" ? "error" : "neutral"}
                          />
                        </td>
                        <td className="p-3 text-right">{getNumber(run.overall_counts?.PASS, 0)}</td>
                        <td className="p-3 text-right">{getNumber(run.overall_counts?.WARN, 0)}</td>
                        <td className="p-3 text-right">{getNumber(run.overall_counts?.FAIL, 0)}</td>
                        <td className="p-3 text-slate-400">{getString(run.generated_at, "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={6}>
                        No rehearsal history found in the staging runtime.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Recent RFQ States</h2>
              <StatusBadge label="Read-only" tone="neutral" />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800 text-slate-300">
                  <tr>
                    <th className="p-3 text-left">RFQ</th>
                    <th className="p-3 text-left">State</th>
                    <th className="p-3 text-left">Source</th>
                    <th className="p-3 text-left">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {visibility.recentRfqs.length ? (
                    visibility.recentRfqs.map((item) => (
                      <tr key={String(item.rfq_id || item.title || Math.random())} className="border-t border-slate-800">
                        <td className="p-3 font-medium">{getString(item.rfq_id || item.reference || item.tender_id, "n/a")}</td>
                        <td className="p-3">
                          <StatusBadge label={getString(item.current_state || item.state || "unknown")} tone="neutral" />
                        </td>
                        <td className="p-3 text-slate-300">{getString(item.source || item.source_name || "staging")}</td>
                        <td className="p-3 text-slate-400">{getString(item.updated_at || item.created_at || "", "n/a")}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="p-4 text-slate-400" colSpan={4}>
                        No RFQ records found in the current staging runtime.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Operational Warnings</h2>
              <StatusBadge
                label={warnings.length ? `${warnings.length} warning(s)` : "No warnings"}
                tone={warnings.length ? "error" : "ok"}
              />
            </div>

            <div className="mt-4 space-y-3">
              {warnings.length ? (
                warnings.map((warning, index) => (
                  <div key={`${warning}-${index}`} className="rounded-xl border border-amber-800 bg-amber-950/40 p-4 text-amber-100">
                    {warning}
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-slate-400">
                  Dry-run telemetry, lock protection, and queue visibility are stable.
                </div>
              )}
            </div>
          </div>
        </section>

        {dashboard ? (
          <>
            <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <StatusPanel
                title="RFQ Workflow"
                rows={[
                  ["RFQs created", dashboard.rfq_status.rfqs_created],
                  ["Dispatch ready", dashboard.rfq_status.dispatch_ready],
                  ["RFQs sent", dashboard.rfq_status.rfqs_sent],
                  ["Dry-run blocked", dashboard.rfq_status.rfqs_blocked_dry_run],
                ]}
              />

              <StatusPanel
                title="Supplier Responses"
                rows={[
                  ["Mailbox checked", dashboard.response_status.mailbox_messages_checked],
                  ["Matched responses", dashboard.response_status.matched_supplier_responses],
                  ["Quotes ingested", dashboard.response_status.quotes_ingested],
                ]}
              />

              <StatusPanel
                title="Adjudication"
                rows={[
                  ["Decisions", dashboard.adjudication_status.total_decisions],
                  ["Awards", dashboard.adjudication_status.recommended_awards],
                  ["Negotiations", dashboard.adjudication_status.recommended_negotiations],
                  ["Held for review", dashboard.adjudication_status.held_for_review],
                ]}
              />
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 p-5">
                <h2 className="text-xl font-bold">Supplier Decisions</h2>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 text-slate-300">
                    <tr>
                      <th className="p-4 text-left">Supplier</th>
                      <th className="p-4 text-left">Decision</th>
                      <th className="p-4 text-right">Score</th>
                      <th className="p-4 text-right">Target</th>
                      <th className="p-4 text-right">Quoted</th>
                      <th className="p-4 text-right">Variance</th>
                      <th className="p-4 text-right">Variance %</th>
                    </tr>
                  </thead>

                  <tbody>
                    {dashboard.supplier_decisions.map((d) => (
                      <tr
                        key={d.supplier_name}
                        className="border-t border-slate-800"
                      >
                        <td className="p-4 font-medium">{d.supplier_name}</td>
                        <td className="p-4">
                          <span className="rounded-full bg-slate-700 px-3 py-1 text-xs">
                            {d.decision}
                          </span>
                        </td>
                        <td className="p-4 text-right">{d.final_score}</td>
                        <td className="p-4 text-right">{money(d.target_total)}</td>
                        <td className="p-4 text-right">{money(d.quoted_total)}</td>
                        <td className="p-4 text-right">{money(d.variance)}</td>
                        <td className="p-4 text-right">
                          {d.variance_pct.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <footer className="text-xs text-slate-500">
              Last refreshed: {dashboard.generated_at}
            </footer>
          </>
        ) : null}
      </div>
    </main>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: "ok" | "error" | "neutral";
}) {
  const className =
    tone === "ok"
      ? "border-emerald-800 bg-emerald-950 text-emerald-300"
      : tone === "error"
        ? "border-rose-800 bg-rose-950 text-rose-300"
        : "border-slate-700 bg-slate-800 text-slate-200";

  return (
    <span className={`rounded-full border px-3 py-1 ${className}`}>
      {label}
    </span>
  );
}

function StatusPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, number]>;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <h2 className="mb-4 font-bold">{title}</h2>

      <div className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between">
            <span className="text-slate-400">{label}</span>
            <span className="font-semibold">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricPanel({
  title,
  summary,
  tone,
  items,
}: {
  title: string;
  summary: string;
  tone: "ok" | "error" | "neutral";
  items: Array<[string, string]>;
}) {
  const borderClass =
    tone === "ok"
      ? "border-emerald-800"
      : tone === "error"
        ? "border-rose-800"
        : "border-slate-800";

  return (
    <div className={`rounded-2xl border bg-slate-900 p-5 ${borderClass}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-bold">{title}</h3>
        <StatusBadge label={summary} tone={tone} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
