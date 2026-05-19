import type { OperatorTimelineEvent } from "./operator";

export type OperatorAuditTimelineResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  events: OperatorTimelineEvent[];
  total: number;
};
