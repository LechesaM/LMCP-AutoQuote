export const topStats = [
  { label: "Active Portals", value: "320", trend: "+18", tone: "green" },
  { label: "Healthy", value: "28", trend: "+4", tone: "green" },
  { label: "Slow", value: "25", trend: "-2", tone: "orange" },
  { label: "Blocked", value: "15", trend: "+3", tone: "red" },
];

export const controlState = {
  systemOn: true,
  harvestPaused: false,
  submissionPaused: false,
  emergencyStop: false,
  lastAction: "Mission Control Online",
};

export const dashboardMetrics = {
  harvested: { title: "RFQs Harvested", bars: [14, 22, 18, 28, 24, 36, 32, 48, 41, 54, 46, 66] },
  weekNow: { title: "This Week", value: "540", sub: "↑ 7.8%" },
  monthNow: { title: "This Month", value: "1,870", sub: "↑ 24.6%" },
  opportunityScore: [48, 76, 58, 89, 67, 81, 63, 92, 78],
  crawlSpeed: "95 Pages/min",
  systemLoad: 72,
  topCategories: [
    { name: "Healthy", count: 286, delta: "+31%" },
    { name: "Slow", count: 25, delta: "-11%" },
    { name: "Trends", count: 39, delta: "+17%" },
  ],
  recentErrors: [
    { name: "Timeout Error", count: 12, tone: "orange" },
    { name: "Login Failure", count: 8, tone: "yellow" },
    { name: "Connection Lost", count: 5, tone: "red" },
  ],
};

export const heatMapStats = [
  { label: "Hot", value: 540, tone: "red" },
  { label: "Moderate", value: 198, tone: "orange" },
  { label: "Low Activity", value: 99, tone: "yellow" },
];

export const radarStatus = {
  portalStatus: [
    { name: "Healthy", count: 260, tone: "green" },
    { name: "Slow", count: 25, tone: "yellow" },
    { name: "Blocked", count: 15, tone: "red" },
  ],
  recentErrors: [
    { name: "Timeout Error", count: 6, tone: "orange" },
    { name: "Login Failure", count: 3, tone: "yellow" },
    { name: "Connection Lost", count: 9, tone: "red" },
  ],
};

export const tenderColumns = {
  hot: [
    { title: "Construction of New School", org: "Department of Education", value: "R2,200,000", score: "92", method: "Email Submission" },
    { title: "Fuel Supply", org: "Provincial Treasury", value: "R1,890,000", score: "88", method: "Portal Submission" },
    { title: "Road Markings", org: "Metro Works", value: "R1,300,000", score: "77", method: "Email Submission" },
  ],
  medium: [
    { title: "IT Services Contract", org: "Internal Department", value: "R2,300,000", score: "83", method: "Email Submission" },
    { title: "PPE Resupply", org: "Logistics Division", value: "R2,500,000", score: "95", method: "Portal Submission" },
    { title: "Municipal Tools", org: "Local Municipality", value: "R980,000", score: "69", method: "Email Submission" },
  ],
  low: [
    { title: "Office Supplies Tender", org: "Department Innovation", value: "R190,000", score: "21", method: "Email Submission" },
    { title: "Copiers Lease", org: "Regional Administration", value: "R100,000", score: "18", method: "Portal Submission" },
    { title: "Furniture Refresh", org: "City of Thwane", value: "R190,000", score: "9", method: "Portal Submission" },
  ],
};
