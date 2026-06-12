export const SIDEBAR_ADMIN_ROLES = ["supervisor", "admin"];

export const operatorPrimarySidebarNavigationItems = [
  { label: "Mission Control", path: "/mission-control" },
  { label: "Dashboard", path: "/dashboard" },
  { label: "RFQ Operations", path: "/operations" },
  { label: "Review Workflow", path: "/review-efficiency" },
  { label: "Work Queue", path: "/review" },
  { label: "Pricing Review", path: "/pricing-evidence" },
  { label: "Approval Centre", path: "/governance" },
  { label: "Evidence Centre", path: "/audit-defensibility" },
  { label: "Submission Readiness", path: "/compliance-reporting" },
];

export const operatorSupportSidebarNavigationItems = [
  { label: "Operator Assignments", path: "/operator-assignments" },
  { label: "Governance Compliance", path: "/governance-compliance" },
  { label: "Quote Intelligence", path: "/supplier-quote-intelligence" },
  { label: "AutoQuote Libraries", path: "/autoquote-libraries" },
  { label: "Weekly Intelligence Report", path: "/autoquote-weekly-report" },
];

export const adminRuntimeSidebarNavigationItems = [
  { label: "Source Health", path: "/source-health" },
  { label: "Runtime Operations", path: "/runtime-operations" },
  { label: "Runtime Analytics", path: "/operational-analytics" },
  { label: "Telemetry Internals", path: "/observability" },
  { label: "SLA Monitoring", path: "/sla-monitoring" },
  { label: "Runtime Anomalies", path: "/runtime-anomalies" },
  { label: "Stabilization Operations", path: "/stabilization-operations" },
  { label: "Burn-in Diagnostics", path: "/runtime-reliability" },
  { label: "Demo Seeding", path: "/admin/demo-seed" },
];

export const secondarySidebarNavigationItems = [
  ...operatorPrimarySidebarNavigationItems,
  ...operatorSupportSidebarNavigationItems,
  ...adminRuntimeSidebarNavigationItems,
];

export function getSidebarNavigationSections(role = "") {
  const isAdminRuntimeVisible = SIDEBAR_ADMIN_ROLES.includes(role);
  const adminRuntimeItems = role === "admin"
    ? adminRuntimeSidebarNavigationItems
    : adminRuntimeSidebarNavigationItems.filter((item) => item.path !== "/admin/demo-seed");

  return [
    {
      label: "Procurement Operations",
      items: operatorPrimarySidebarNavigationItems,
    },
    {
      label: "Governance",
      items: [...operatorSupportSidebarNavigationItems, ...(isAdminRuntimeVisible ? adminRuntimeItems : [])],
    },
  ];
}
