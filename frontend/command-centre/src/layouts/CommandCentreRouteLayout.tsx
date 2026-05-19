import { Outlet } from "react-router-dom";
import CommandCentreLayout from "./CommandCentreLayout.tsx";
import { useRouteTelemetry } from "../hooks/useRouteTelemetry";

export default function CommandCentreRouteLayout() {
  const routeTelemetry = useRouteTelemetry();

  return (
    <CommandCentreLayout routeTelemetry={routeTelemetry}>
      <Outlet />
    </CommandCentreLayout>
  );
}
