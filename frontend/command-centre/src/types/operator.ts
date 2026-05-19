export type OperatorActionPayload = {
  operatorId: string;
  tenderId: string;
  note?: string;
  targetType?: string;
  details?: Record<string, unknown>;
};

export type OperatorActionRecord = {
  actionId: string;
  action: string;
  operatorId: string;
  tenderId: string;
  targetType: string;
  note: string;
  status: string;
  reversible: boolean;
  reviewable: boolean;
  auditEventId: string;
  createdAt: string;
  updatedAt: string;
  details: Record<string, unknown>;
};

export type OperatorActionsResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  actions: OperatorActionRecord[];
  total: number;
};

export type OperatorAssignmentRecord = {
  assignmentId: string;
  operatorId: string;
  tenderId: string;
  status: string;
  priority: number;
  assignedAt: string;
  dueAt: string;
  workload: number;
  recommendation: string;
  source: string;
  details: Record<string, unknown>;
};

export type OperatorAssignmentsResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  assignments: OperatorAssignmentRecord[];
  recommendations: Array<{
    tenderId: string;
    title: string;
    recommendation: string;
    priority: number;
    workflowStage: string;
    owner: string;
    reason: string;
    dueAt: string;
  }>;
  summary: {
    totalAssignments: number;
    activeAssignments: number;
    operators: number;
    capacity: number;
  };
  capacity: OperatorCapacitySnapshot;
};

export type OperatorTimelineEvent = {
  eventId: string;
  eventType: string;
  operatorId: string;
  tenderId: string;
  title: string;
  severity: string;
  reversible: boolean;
  reviewable: boolean;
  createdAt: string;
  details: Record<string, unknown>;
};

export type OperatorTimelineResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  events: OperatorTimelineEvent[];
  total: number;
};

export type OperatorNotificationRecord = {
  notificationId: string;
  type: string;
  severity: string;
  title: string;
  message: string;
  tenderId: string;
  operatorId: string;
  acknowledged: boolean;
  createdAt: string;
  details: Record<string, unknown>;
};

export type OperatorNotificationsResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  notifications: OperatorNotificationRecord[];
};

export type OperatorCapacitySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  teamSize: number;
  perOperatorDailyCapacity: number;
  totalDailyCapacity: number;
  assignedToday: number;
  remainingCapacity: number;
  overloaded: boolean;
  recommendedLoad: number;
};

export type OperatorAuditResponse = OperatorTimelineResponse;
