export const fallbackSummary = {
  harvestedToday: 184,
  qualified: 46,
  quoteReady: 18,
  submitted: 7,
  activePortals: 300,
  isolatedPortals: 25,
  alerts: 4,
};

export const fallbackTenders = [
  {
    id: "tn-001",
    title: "Upgrade of Security Fence at Government Offices",
    buyer: "DPWI",
    province: "Free State",
    submission_type: "portal-only",
    briefing_required: false,
    close_date: "2026-03-18",
    score: 92,
    status: "Quote Ready",
    sector: "Construction",
    quote_ready: true,
    estimate_value: "R 4.8M",
  },
  {
    id: "tn-002",
    title: "Portable Water & Wastewater Treatment Operations",
    buyer: "Correctional Services",
    province: "Northern Cape",
    submission_type: "email-only",
    briefing_required: false,
    close_date: "2026-03-21",
    score: 88,
    status: "Review Needed",
    sector: "Water Services",
    quote_ready: false,
    estimate_value: "R 2.1M",
  },
  {
    id: "tn-003",
    title: "Road Signs and Traffic Accommodation Package",
    buyer: "SANRAL",
    province: "Western Cape",
    submission_type: "portal-only",
    briefing_required: false,
    close_date: "2026-03-24",
    score: 85,
    status: "In Drafting",
    sector: "Civil Engineering",
    quote_ready: false,
    estimate_value: "R 7.9M",
  },
];

export const fallbackPortals = [
  {
    name: "eTenders",
    state: "Healthy",
    latency: "1.2s",
    success_rate: "94%",
    last_error: "None",
    zone: "National",
  },
  {
    name: "SANRAL",
    state: "Slow",
    latency: "4.8s",
    success_rate: "81%",
    last_error: "Timeout on attachments",
    zone: "SOE",
  },
  {
    name: "Mangaung",
    state: "Isolated",
    latency: "Offline",
    success_rate: "22%",
    last_error: "Repeated HTTP 500",
    zone: "Municipal",
  },
];

export const fallbackAlerts = [
  "3 portals moved into isolation mode after repeated failures.",
  "Disk Safety Guard active and free-space threshold is healthy.",
  "Backup completed successfully at 02:00 with retention policy applied.",
  "2 high-value opportunities need pricing approval before submission.",
];
