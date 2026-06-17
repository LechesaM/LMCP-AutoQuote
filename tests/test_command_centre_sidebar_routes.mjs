import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  adminRuntimeSidebarNavigationItems,
  getSidebarNavigationSections,
  operatorPrimarySidebarNavigationItems,
  operatorSupportSidebarNavigationItems,
} from "../frontend/command-centre/src/routes/sidebarNavigation.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");

function readFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

function extractRoutePaths(source) {
  const objectPaths = Array.from(source.matchAll(/path:\s*"([^"]+)"/g), (match) => match[1]);
  const jsxPaths = Array.from(source.matchAll(/path\s*=\s*"([^"]+)"/g), (match) => match[1]);
  return new Set([...objectPaths, ...jsxPaths]);
}

const routesSource = readFile("frontend/command-centre/src/routes/commandCentreRoutes.ts");
const appSource = readFile("frontend/command-centre/src/App.jsx");
const rolesSource = readFile("frontend/command-centre/src/auth/roles.ts");
const sidebarSource = readFile("frontend/command-centre/src/routes/sidebarNavigation.js");
const actionBarSource = readFile("frontend/command-centre/src/components/operator/RFQReviewActionBar.tsx");

const routePaths = extractRoutePaths(routesSource);
const appPaths = extractRoutePaths(appSource);

for (const requiredPath of ["/operations", "/review", "/qualification-insights", "/governance-compliance"]) {
  assert.ok(routePaths.has(requiredPath), `Expected ${requiredPath} in commandCentreRoutes.ts`);
  assert.ok(appPaths.has(requiredPath), `Expected ${requiredPath} in App.jsx`);
}

assert.ok(
  appSource.includes('RequireRole permissions={["view_supplier_quote_intelligence"]}'),
  "Expected supplier quote intelligence route to use the view permission guard",
);
for (const expectedGuard of [
  'path="/operations"',
  'RequireRole permissions={["view_rfqs"]}',
  'path="/review"',
  'RequireRole permissions={["view_operator_queue"]}',
  'path="/operator-operations"',
  'RequireRole permissions={["view_operator_review"]}',
  'path="/governance"',
  'RequireRole permissions={["view_governance"]}',
  'path="/audit-defensibility"',
  'RequireRole permissions={["view_audit"]}',
  'path="/compliance-reporting"',
  'RequireRole permissions={["view_governance", "view_audit"]}',
]) {
  assert.ok(appSource.includes(expectedGuard), `Expected App.jsx to include ${expectedGuard}`);
}

for (const expectedPermission of [
  "view_operator_review",
  "run_operator_assign_supplier",
  "run_operator_mark_reviewed",
  "run_operator_request_clarification",
  "run_operator_reject_rfq",
  "run_operator_escalate_rfq",
  "run_operator_acknowledge_alert",
  "run_submission_package_generate",
]) {
  assert.ok(rolesSource.includes(`"${expectedPermission}"`), `Expected frontend role map to include ${expectedPermission}`);
}

for (const legacyPermission of ["assign_operator", "mark_reviewed", "escalate_review", "archive_rfq", "acknowledge_alert"]) {
  assert.ok(!rolesSource.includes(`"${legacyPermission}"`), `Expected frontend role map to drop legacy permission ${legacyPermission}`);
  assert.ok(!routesSource.includes(`"${legacyPermission}"`), `Expected route metadata to drop legacy permission ${legacyPermission}`);
  assert.ok(!sidebarSource.includes(`"${legacyPermission}"`), `Expected sidebar navigation to drop legacy permission ${legacyPermission}`);
  assert.ok(!appSource.includes(`can("${legacyPermission}")`), `Expected App.jsx to avoid legacy permission check ${legacyPermission}`);
  assert.ok(
    !appSource.includes(`require_permission("${legacyPermission}")`),
    `Expected App.jsx to avoid legacy backend permission check ${legacyPermission}`,
  );
  assert.ok(
    !actionBarSource.includes(`can("${legacyPermission}")`),
    `Expected operator action bar to avoid legacy permission check ${legacyPermission}`,
  );
  assert.ok(
    !actionBarSource.includes(`require_permission("${legacyPermission}")`),
    `Expected operator action bar to avoid legacy backend permission check ${legacyPermission}`,
  );
}

assert.ok(appPaths.has("/__debug/navigation"), "Expected /__debug/navigation in App.jsx");

const visibleOperatorPaths = [
  ...operatorPrimarySidebarNavigationItems,
  ...operatorSupportSidebarNavigationItems,
  ...adminRuntimeSidebarNavigationItems,
].map((item) => item.path);

const missingSidebarPaths = visibleOperatorPaths.filter((routePath) => !routePaths.has(routePath) || !appPaths.has(routePath));

assert.deepEqual(missingSidebarPaths, [], `Sidebar paths missing from registered frontend routes: ${missingSidebarPaths.join(", ")}`);

const operatorSections = getSidebarNavigationSections("operator");
assert.equal(operatorSections.length, 2, "Operator should only see procurement and governance sections");
assert.equal(operatorSections.some((section) => section.label === "Admin Runtime"), false, "Admin Runtime should be hidden from operators");
const operatorGovernanceSection = operatorSections.find((section) => section.label === "Governance");
assert.ok(operatorGovernanceSection, "Operator should see a Governance section");
assert.deepEqual(
  operatorGovernanceSection.items.map((item) => item.path),
  operatorSupportSidebarNavigationItems.map((item) => item.path),
  "Operator Governance section should only expose support routes",
);

const supervisorSections = getSidebarNavigationSections("supervisor");
const supervisorGovernanceSection = supervisorSections.find((section) => section.label === "Governance");
assert.ok(supervisorGovernanceSection, "Supervisor should see a Governance section");
for (const item of adminRuntimeSidebarNavigationItems.filter((navigationItem) => navigationItem.path !== "/admin/demo-seed")) {
  assert.ok(
    supervisorGovernanceSection.items.some((sectionItem) => sectionItem.path === item.path),
    `Supervisor Governance section should expose ${item.path}`,
  );
}

console.log(JSON.stringify({
  status: "passed",
  route_count: routePaths.size,
  app_route_count: appPaths.size,
  sidebar_item_count: visibleOperatorPaths.length,
}, null, 2));
