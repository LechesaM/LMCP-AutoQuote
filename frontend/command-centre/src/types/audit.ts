export type AuditIntegrityState = {
  status: string;
  generatedAt: string;
  dataSource: string;
  totalEvents: number;
  missingRequiredFields: number;
  timestampsSorted: boolean;
  duplicateIds: boolean;
  orphanedActions: Array<Record<string, unknown>>;
  warnings: string[];
  blockers: string[];
  integrityScore: number;
  appendOnlyAssumed: boolean;
};

