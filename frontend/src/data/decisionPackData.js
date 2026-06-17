export const decisionPackData = {
  decisionRules: [
    "If a category is blocked in the tender playbook, classify it as EXCLUDE.",
    "If a category is Target immediately and the summary score is 7.0 or higher, classify it as TARGET_IMMEDIATELY.",
    "If a category is Review carefully or the province view includes an inferred entry, classify it as REVIEW_CAREFULLY.",
    "Use supplier coverage and province fit as advisory inputs only.",
  ],
  topOverallCategories: [
    { category: "PPE", action: "TARGET_IMMEDIATELY", reason: "Highest combined score and broad supplier coverage." },
    { category: "Cleaning materials", action: "TARGET_IMMEDIATELY", reason: "Strong province fit and broad supplier coverage." },
    { category: "Janitorial supplies", action: "TARGET_IMMEDIATELY", reason: "Strong province fit and broad supplier coverage." },
    { category: "Stationery", action: "TARGET_IMMEDIATELY", reason: "High execution fit for replenishment-style RFQs." },
    { category: "Water treatment consumables", action: "TARGET_IMMEDIATELY", reason: "Strong execution fit with focused supplier coverage." },
  ],
  provinceShortlists: {
    Gauteng: ["PPE", "Cleaning materials", "Janitorial supplies", "Stationery", "Construction materials"],
    WesternCape: ["Cleaning materials", "Janitorial supplies", "Water treatment consumables", "Water reticulation / plumbing", "Road signs"],
    KwaZuluNatal: ["Cleaning materials", "Janitorial supplies", "Water treatment consumables", "PPE", "Construction materials"],
    Mpumalanga: ["Office furniture", "Cleaning materials", "Janitorial supplies", "PPE", "Water treatment consumables"],
  },
};
