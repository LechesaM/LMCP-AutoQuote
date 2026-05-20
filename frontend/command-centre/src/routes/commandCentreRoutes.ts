export const commandCentreRoutes = [
  {
    path: "/dashboard",
    label: "Dashboard",
    description: "Live command centre view",
  },
  {
    path: "/executive-dashboard",
    label: "Executive Dashboard",
    description: "Strategic operating intelligence",
  },
  {
    path: "/profitability-analytics",
    label: "Profitability Analytics",
    description: "Margin and opportunity intelligence",
  },
  {
    path: "/operational-forecasting",
    label: "Operational Forecasting",
    description: "Queue and demand projection",
  },
  {
    path: "/operations",
    label: "RFQ Operations",
    description: "Harvest and qualification flow",
  },
  {
    path: "/source-health",
    label: "Source Health",
    description: "Harvest source and parser state",
  },
  {
    path: "/qualification-insights",
    label: "Qualification Insights",
    description: "GO / manual / reject intelligence",
  },
  {
    path: "/pricing-evidence",
    label: "Pricing Evidence",
    description: "Supplier quote defensibility",
  },
  {
    path: "/review",
    label: "Review Queue",
    description: "Operator capacity and queue health",
  },
  {
    path: "/operator-productivity",
    label: "Operator Productivity",
    description: "Workload and efficiency optimization",
  },
  {
    path: "/queue-optimization",
    label: "Queue Optimization",
    description: "Priority ordering and heatmaps",
  },
  {
    path: "/review-efficiency",
    label: "Review Efficiency",
    description: "Throughput and evidence handling",
  },
  {
    path: "/governance",
    label: "Governance",
    description: "Manual control and release rules",
  },
  {
    path: "/governance-compliance",
    label: "Governance Compliance",
    description: "Policy registry and compliance controls",
  },
  {
    path: "/audit-defensibility",
    label: "Audit Defensibility",
    description: "Audit chain and evidence continuity",
  },
  {
    path: "/compliance-reporting",
    label: "Compliance Reporting",
    description: "Attestations and regulatory exports",
  },
  {
    path: "/operator-operations",
    label: "Operator Operations",
    description: "Controlled action workspace",
  },
  {
    path: "/operator-assignments",
    label: "Operator Assignments",
    description: "Queue ownership and workload",
  },
  {
    path: "/runtime-operations",
    label: "Runtime Operations",
    description: "Observability and backup validation",
  },
  {
    path: "/operational-analytics",
    label: "Operational Analytics",
    description: "Runtime trends and source reliability",
  },
  {
    path: "/incident-management",
    label: "Incident Management",
    description: "Incident timelines and alerts",
  },
  {
    path: "/observability",
    label: "Observability",
    description: "Prometheus, Grafana, Sentry and runtime health",
  },
  {
    path: "/sla-monitoring",
    label: "SLA Monitoring",
    description: "Service-level and freshness monitoring",
  },
  {
    path: "/runtime-anomalies",
    label: "Runtime Anomalies",
    description: "Advisory anomaly detection",
  },
  {
    path: "/activity-timeline",
    label: "Activity Timeline",
    description: "Append-only operator history",
  },
] as const;

export function getCommandCentreRouteMeta(pathname) {
  const normalizedPath = pathname === "/" ? "/dashboard" : pathname.replace(/\/+$/, "") || "/dashboard";
  return (
    commandCentreRoutes.find((route) => route.path === normalizedPath) ?? commandCentreRoutes[0]
  );
}
