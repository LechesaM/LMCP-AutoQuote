import type { OperatorNotificationRecord } from "./operator";

export type OperatorNotificationsResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  notifications: OperatorNotificationRecord[];
};
