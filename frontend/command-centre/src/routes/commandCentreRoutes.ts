export const commandCentreRoutes = [
  {
    path: "/dashboard",
    label: "Dashboard",
    description: "Live command centre view",
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
    path: "/governance",
    label: "Governance",
    description: "Manual control and release rules",
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
