export type RfqFilterState = {
  timePeriod: string;
  tenderType: string;
  profitThreshold: string;
  province: string;
  radarMode: string;
};

export type ReviewQueueItem = {
  title: string;
  province: string;
  value: string;
  profit: string;
  recommendation: string;
};
