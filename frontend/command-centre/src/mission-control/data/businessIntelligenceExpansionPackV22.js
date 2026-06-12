export const businessIntelligenceSchema = [
  "title",
  "buyer",
  "category",
  "province",
  "source",
  "published_at",
  "closing_at",
  "evidence_links",
  "confidence_score",
  "risk_score",
];

export const verificationLadder = [
  { from: "Discovery", to: "Qualification", intent: "Identify whether the opportunity is worth further analysis." },
  { from: "Qualification", to: "Pricing", intent: "Check supplier coverage, BOQ readiness, and margin potential." },
  { from: "Pricing", to: "Evidence Review", intent: "Attach source evidence and validate pricing assumptions." },
  { from: "Evidence Review", to: "Operational Readiness", intent: "Confirm the record is safe to promote for execution." },
];

export const evidenceReviewFramework = [
  { step: "Source coverage", rule: "Every opportunity should have a source trace and a matching backup source." },
  { step: "Pricing traceability", rule: "Each price line should have an auditable supplier or benchmark reference." },
  { step: "Temporal validity", rule: "Recheck stale items whenever the window exceeds the freshness threshold." },
  { step: "Human sign-off", rule: "Promotion beyond the review boundary requires explicit operator approval." },
];

export const awardConfirmedPromotionProgram = [
  "Target award-confirmed records as the primary success metric.",
  "Retain a visible evidence chain for every promotion.",
  "Prefer supply-side confirmations over inferred outcomes.",
  "Exclude speculative or unverified quote targets.",
];

export const provinceSupplierCoverage = [
  { province: "Gauteng", category: "Electrical infrastructure", primary: "National Electrical", backup: "PowerGrid Supply", coverage: "Healthy" },
  { province: "KwaZulu-Natal", category: "PPE / workwear", primary: "Dromex", backup: "SafeWork SA", coverage: "Healthy" },
  { province: "Western Cape", category: "Water infrastructure", primary: "Aqua Plumb", backup: "BlueWave Trade", coverage: "Healthy" },
  { province: "Eastern Cape", category: "Cleaning / hygiene", primary: "Chemex", backup: "Hygiene Depot", coverage: "Watch" },
];

export const priorityCategoryCoverageTarget = [
  "Electrical infrastructure",
  "Water infrastructure",
  "Road infrastructure",
  "PPE / safety",
  "Cleaning / hygiene",
  "Office supply",
];

export const pricingReviewCycles = [
  { status: "Fresh", cadence: "Review monthly", reason: "New items can be promoted after a routine validation pass." },
  { status: "Warm", cadence: "Review every 14 days", reason: "Recheck items with moderate volatility or supply shifts." },
  { status: "Cold", cadence: "Review weekly", reason: "High-change categories need tighter price and supplier controls." },
  { status: "Stale", cadence: "Review immediately", reason: "Records should not be promoted without renewed validation." },
];

export const pricingRecordFields = [
  "Supplier name",
  "Unit cost",
  "Margin",
  "Traceability chain",
  "Delivery cost",
  "Lead time",
  "Confidence score",
  "Evidence status",
];

export const pricingReviewCadence = [
  { cadence: "30 days", trigger: "Minor market movement or freshness drift." },
  { cadence: "90 days", trigger: "Supplier relationship or lead-time changes." },
  { cadence: "180 days", trigger: "Structural price changes or operational policy review." },
];

export const competitorIntelligenceFields = [
  "Competitor presence",
  "Likely incumbent",
  "Bundled offering",
  "Coverage gaps",
  "Price pressure",
  "Risk notes",
];

export const winProbabilityCalibrationFields = [
  "Win likelihood",
  "Pricing confidence",
  "Evidence completeness",
  "Coverage depth",
  "Competitive intensity",
];

export const winProbabilityCalibrationLoop = [
  "Compare expected win probability against actual outcomes.",
  "Feed back successful and failed bids into calibration.",
  "Adjust weighting for freshness, supplier coverage, and evidence quality.",
];

export const operatorReadinessPack = [
  "Review queue access",
  "Evidence pack access",
  "Pricing schedule access",
  "Approver list",
  "Escalation contacts",
];

export const weeklyRegressionRunPrep = [
  "Verify submission history samples.",
  "Rebuild pricing schedules against known catalog items.",
  "Confirm the evidence trace survives a refresh cycle.",
];

export const governanceBoundary = [
  "Do not auto-promote unverified opportunities.",
  "Do not suppress operator approvals.",
  "Do not bypass audit or evidence capture.",
  "Do not ship a pricing schedule without traceability.",
];

export const trackBAssurance = [
  "Record each review cycle in the evidence log.",
  "Retain the source trail for supplier matches.",
  "Document changes to pricing confidence thresholds.",
];

export const trackBOperatingChecklist = [
  "Load verified supplier evidence.",
  "Refresh the review window.",
  "Confirm operator availability.",
  "Run a dry pricing schedule.",
];

export const trackBReviewTemplates = [
  "Qualification memo",
  "Pricing exception note",
  "Evidence review checklist",
  "Operator approval template",
];
