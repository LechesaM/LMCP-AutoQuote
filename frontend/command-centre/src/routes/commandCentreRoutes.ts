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
    path: "/review",
    label: "Review Queue",
    description: "Operator capacity and queue health",
  },
  {
    path: "/governance",
    label: "Governance",
    description: "Manual control and release rules",
  },
] as const;

export function getCommandCentreRouteMeta(pathname) {
  const normalizedPath = pathname === "/" ? "/dashboard" : pathname.replace(/\/+$/, "") || "/dashboard";
  return (
    commandCentreRoutes.find((route) => route.path === normalizedPath) ?? commandCentreRoutes[0]
  );
}
