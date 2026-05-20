export type ComplianceControlsState = {
  status: string;
  generatedAt: string;
  dataSource: string;
  complianceScore: number;
  warnings: string[];
  blockers: string[];
  manualGovernanceOnly: boolean;
  controls: Record<string, boolean>;
};

