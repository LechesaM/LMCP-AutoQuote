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
