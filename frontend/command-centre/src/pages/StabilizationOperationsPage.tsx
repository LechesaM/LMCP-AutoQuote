import DeploymentStabilityPanel from "../components/stabilization/DeploymentStabilityPanel.tsx";
import FallbackResiliencePanel from "../components/stabilization/FallbackResiliencePanel.tsx";
import GovernanceConsistencyPanel from "../components/stabilization/GovernanceConsistencyPanel.tsx";
import RuntimeStabilityPanel from "../components/stabilization/RuntimeStabilityPanel.tsx";
import TelemetryNoisePanel from "../components/stabilization/TelemetryNoisePanel.tsx";
import { useRuntimeStability } from "../hooks/useRuntimeStability";

export default function StabilizationOperationsPage() {
  const stabilization = useRuntimeStability();

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-command-cyan/20 bg-gradient-to-br from-command-cyan/10 via-slate-950 to-slate-950 p-5">
        <div className="text-xs font-black uppercase tracking-[.28em] text-command-cyan">Stabilization Operations</div>
        <h2 className="mt-2 text-2xl font-black text-white">Supervised-live stability hardening</h2>
        <p className="mt-2 max-w-4xl text-sm text-slate-300">
          Runtime stability, fallback resilience, telemetry tuning, governance consistency and deployment stability stay read-only and advisory.
        </p>
      </div>
      <RuntimeStabilityPanel snapshot={stabilization.runtimeStability} loading={stabilization.loading} refreshing={stabilization.refreshing} error={stabilization.error} />
      <div className="grid gap-6 xl:grid-cols-2">
        <FallbackResiliencePanel snapshot={stabilization.fallbackHealth} loading={stabilization.loading} />
        <TelemetryNoisePanel snapshot={stabilization.telemetryNoise} loading={stabilization.loading} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <GovernanceConsistencyPanel snapshot={stabilization.governanceConsistency} loading={stabilization.loading} />
        <DeploymentStabilityPanel snapshot={stabilization.deploymentStability} loading={stabilization.loading} />
      </div>
    </div>
  );
}
