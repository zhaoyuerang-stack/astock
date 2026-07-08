import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

const requiredFiles = [
  "package.json",
  "src/main/main.cjs",
  "src/main/preload.cjs",
  "src/main/piBridge.cjs",
  "src/main/readServiceClient.cjs",
  "src/main/diagnosisService.cjs",
  "src/renderer/App.jsx",
  "src/renderer/main.jsx",
  "src/renderer/styles.css",
  "src/renderer/index.html",
];

for (const relative of requiredFiles) {
  assert(existsSync(join(root, relative)), `Missing required desktop client file: ${relative}`);
}

const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
assert.equal(pkg.name, "astock-lens-desktop");
assert.equal(pkg.main, "src/main/main.cjs");
assert(pkg.scripts.dev.includes("electron"), "dev script must launch Electron");
assert(pkg.scripts.test.includes("node --test"), "test script must use node:test");

const preload = readFileSync(join(root, "src/main/preload.cjs"), "utf8");
assert(preload.includes("contextBridge.exposeInMainWorld"), "preload must expose a narrow API through contextBridge");
assert(preload.includes("runDiagnosis"), "preload must expose runDiagnosis");
assert(!preload.includes("ipcRenderer.send("), "preload must avoid unbounded fire-and-forget IPC");

const main = readFileSync(join(root, "src/main/main.cjs"), "utf8");
assert(main.includes("contextIsolation: true"), "Electron window must enable contextIsolation");
assert(main.includes("nodeIntegration: false"), "Electron window must disable nodeIntegration");
assert(main.includes("diagnosis:run"), "main process must register diagnosis IPC");
assert(main.includes("runtime:status"), "main process must expose runtime status IPC");

const piBridge = readFileSync(join(root, "src/main/piBridge.cjs"), "utf8");
assert(piBridge.includes("--no-tools"), "Pi bridge must disable Pi tools by default");
assert(piBridge.includes("--no-session"), "Pi bridge must keep diagnosis prompts ephemeral by default");
assert(!piBridge.includes("bash"), "Pi bridge must not enable arbitrary shell tools");

const app = readFileSync(join(root, "src/renderer/App.jsx"), "utf8");
const requiredUiMarkers = [
  'data-testid="thread-sidebar"',
  'data-testid="diagnosis-workspace"',
  'data-testid="evidence-panel"',
  'data-testid="bottom-composer"',
  'data-testid="decision-card"',
  "问一只股票，或继续推进当前诊断",
  "如果未持有",
  "如果已持有",
];

for (const marker of requiredUiMarkers) {
  assert(app.includes(marker), `Missing required UI marker/copy: ${marker}`);
}

console.log("desktop client contract passed");
