import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { secondarySidebarNavigationItems } from "../frontend/command-centre/src/routes/sidebarNavigation.js";

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

const routePaths = extractRoutePaths(routesSource);
const appPaths = extractRoutePaths(appSource);

for (const requiredPath of ["/operations", "/review", "/qualification-insights", "/governance-compliance"]) {
  assert.ok(routePaths.has(requiredPath), `Expected ${requiredPath} in commandCentreRoutes.ts`);
  assert.ok(appPaths.has(requiredPath), `Expected ${requiredPath} in App.jsx`);
}

assert.ok(appPaths.has("/__debug/navigation"), "Expected /__debug/navigation in App.jsx");

const missingSidebarPaths = secondarySidebarNavigationItems
  .map((item) => item.path)
  .filter((routePath) => !routePaths.has(routePath) || !appPaths.has(routePath));

assert.deepEqual(missingSidebarPaths, [], `Sidebar paths missing from registered frontend routes: ${missingSidebarPaths.join(", ")}`);

console.log(JSON.stringify({
  status: "passed",
  route_count: routePaths.size,
  app_route_count: appPaths.size,
  sidebar_item_count: secondarySidebarNavigationItems.length,
}, null, 2));
