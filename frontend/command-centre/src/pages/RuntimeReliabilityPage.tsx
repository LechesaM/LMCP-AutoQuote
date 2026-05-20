import DeploymentStabilityPanel from "../components/stabilization/DeploymentStabilityPanel.tsx";
import FallbackResiliencePanel from "../components/stabilization/FallbackResiliencePanel.tsx";
import RuntimeStabilityPanel from "../components/stabilization/RuntimeStabilityPanel.tsx";
import TelemetryNoisePanel from "../components/stabilization/TelemetryNoisePanel.tsx";
import { useRuntimeReliability } from "../hooks/useRuntimeReliability";

export default function RuntimeReliabilityPage() {
  const reliability = useRuntimeReliability();

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-command-amber/20 bg-gradient-to-br from-command-amber/10 via-slate-950 to-slate-950 p-5">
        <div className="text-xs font-black uppercase tracking-[.28em] text-command-amber">Runtime Reliability</div>
        <h2 className="mt-2 text-2xl font-black text-white">Reliability, fallback and deployment continuity</h2>
        <p className="mt-2 max-w-4xl text-sm text-slate-300">
          Read-only operational reliability monitoring for queue stability, fallback health and deployment consistency.
        </p>
      </div>
      <RuntimeStabilityPanel snapshot={reliability.snapshot?.runtimeStability} loading={reliability.loading} refreshing={reliability.refreshing} error={reliability.error} />
      <div className="grid gap-6 xl:grid-cols-2">
        <FallbackResiliencePanel snapshot={reliability.snapshot?.fallbackHealth} loading={reliability.loading} />
        <TelemetryNoisePanel snapshot={reliability.snapshot?.telemetryNoise} loading={reliability.loading} />
      </div>
      <DeploymentStabilityPanel snapshot={reliability.snapshot?.deploymentStability} loading={reliability.loading} />
    </div>
  );
}
