export type SourceHealthRow = {
  sourceId: string;
  name: string;
  sourceTier: string;
  parserType: string;
  status: string;
  lastSuccess: string;
  lastFailure: string;
  failureCount: number;
  averageResponseTimeMs: number;
  parserFailureRate: number;
  healthState: string;
};

export type SourceHealthDetailsResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  rows: SourceHealthRow[];
  tierBreakdown: Record<string, number>;
  summary: {
    totalSources: number;
    healthySources: number;
    degradedSources: number;
    failingSources: number;
    disabledSources: number;
  };
};
