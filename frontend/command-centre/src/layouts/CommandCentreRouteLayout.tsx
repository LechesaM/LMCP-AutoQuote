import { Outlet } from "react-router-dom";
import CommandCentreLayout from "./CommandCentreLayout.tsx";
import { useRouteTelemetry } from "../hooks/useRouteTelemetry";
import { useTelemetryRefresh } from "../hooks/useTelemetryRefresh";
import { useHarvestHealthRefresh } from "../hooks/useHarvestHealthRefresh";
import { useReviewQueueRefresh } from "../hooks/useReviewQueueRefresh";

export default function CommandCentreRouteLayout() {
  const routeTelemetry = useRouteTelemetry();
  useTelemetryRefresh();
  useHarvestHealthRefresh();
  useReviewQueueRefresh();

  return (
    <CommandCentreLayout routeTelemetry={routeTelemetry}>
      <Outlet />
    </CommandCentreLayout>
  );
}
