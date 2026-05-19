import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import useTelemetryStore from "../store/telemetryStore";
import { getCommandCentreRouteMeta } from "../routes/commandCentreRoutes";

export function useRouteTelemetry() {
  const location = useLocation();
  const recordRouteView = useTelemetryStore((state) => state.recordRouteView);
  const routeHistory = useTelemetryStore((state) => state.routeHistory);
  const currentRoute = useTelemetryStore((state) => state.currentRoute);
  const currentRouteLabel = useTelemetryStore((state) => state.currentRouteLabel);
  const routeViewCount = useTelemetryStore((state) => state.routeViewCount);
  const lastRouteAt = useTelemetryStore((state) => state.lastRouteAt);

  const routeMeta = getCommandCentreRouteMeta(location.pathname);

  useEffect(() => {
    recordRouteView(routeMeta.path, routeMeta.label);
  }, [location.pathname, recordRouteView, routeMeta.label, routeMeta.path]);

  return {
    currentRoute,
    currentRouteLabel,
    routeViewCount,
    lastRouteAt,
    routeHistory,
    routeMeta,
  };
}
