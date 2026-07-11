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
  "src/renderer/visualizations/VisualizationWorkspace.jsx",
  "src/shared/skills.json",
  "src/main/piSkills/single-stock-diagnosis.md",
  "src/main/piSkills/valuation-snapshot.md",
  "src/main/piSkills/holding-risk-check.md",
  "src/main/piSkills/strategy-precheck.md",
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
assert(preload.includes("apiVersion: 2"), "preload must expose the structured IPC API version");
assert(preload.includes("runDiagnosis"), "preload must expose runDiagnosis");
assert(!preload.includes("ipcRenderer.send("), "preload must avoid unbounded fire-and-forget IPC");

const main = readFileSync(join(root, "src/main/main.cjs"), "utf8");
assert(main.includes("contextIsolation: true"), "Electron window must enable contextIsolation");
assert(main.includes("nodeIntegration: false"), "Electron window must disable nodeIntegration");
assert(main.includes("diagnosis:run"), "main process must register diagnosis IPC");
assert(main.includes("runtime:status"), "main process must expose runtime status IPC");
assert(main.includes("apiVersion"), "runtime status must include IPC API version");
assert(main.includes("readService"), "runtime status must include read service health");

const piBridge = readFileSync(join(root, "src/main/piBridge.cjs"), "utf8");
assert(piBridge.includes("--no-tools"), "Pi bridge must disable Pi tools by default");
assert(piBridge.includes("--no-session"), "Pi bridge must keep diagnosis prompts ephemeral by default");
assert(piBridge.includes("orchestrateSkillExecution"), "Pi bridge must expose skill orchestration");
assert(piBridge.includes("ALLOWED_SKILL_TOOLS"), "Pi bridge must define a tool whitelist");
assert(piBridge.includes("record_strategy_precheck"), "Pi bridge must include strategy precheck as a whitelisted tool");
assert(!piBridge.includes("bash"), "Pi bridge must not enable arbitrary shell tools");

const app = readFileSync(join(root, "src/renderer/App.jsx"), "utf8");
const visualization = readFileSync(join(root, "src/renderer/visualizations/VisualizationWorkspace.jsx"), "utf8");
const skillCatalog = readFileSync(join(root, "src/shared/skills.json"), "utf8");
const rendererSurface = `${app}\n${visualization}\n${skillCatalog}`;
const requiredUiMarkers = [
  'data-testid="thread-sidebar"',
  'data-testid="diagnosis-workspace"',
  'data-testid="bottom-composer"',
  'data-testid="conversation-workspace"',
  'data-testid="conversation-history"',
  'data-testid="visualization-entry"',
  'data-testid="visualization-workspace"',
  'data-testid="conversation-end"',
  'data-testid="composer-skill-button"',
  'data-testid="skill-picker"',
  'data-testid="active-skill-bar"',
  "structuredIpcAvailable",
  "legacyDiagnosisPrompt",
  "diagnosisContext",
  "keepActiveWorkspace",
  "pendingDiagnosis",
  "conversationTurnsForDisplay",
  "ensureResultTurns",
  "sameThreadIdentity",
  "upsertThreadList",
  "dedupeThreadList",
  "正在编排 Skill",
  "问一只股票，或继续推进当前诊断",
  "图形化展示",
  "选择 Skill",
  "已启用 Skill",
  "策略预检",
  "不展示伪造曲线",
  "等待输入",
  "本地数据服务不可用",
];

for (const marker of requiredUiMarkers) {
  assert(rendererSurface.includes(marker), `Missing required UI marker/copy: ${marker}`);
}

assert(!rendererSurface.includes("600519-demo"), "renderer must not ship hard-coded demo diagnosis threads");
assert(!rendererSurface.includes("seedThreads"), "renderer must not seed fake thread history");
assert(!app.includes("slice(-8)"), "conversation history must not be visually clamped to the last eight turns");
assert(app.includes("conversationEndRef"), "conversation history should auto-scroll as turns are appended");
assert(app.includes("diagnosisConversationReply"), "diagnosed workspaces must synthesize an assistant turn when result turns are missing");
assert(!app.includes('data-testid="evidence-panel"'), "conversation shell must not render a persistent right evidence sidebar");
assert(!app.includes('data-testid="decision-card"'), "conversation shell must not render the diagnosis card under the chat");
assert(!app.includes('data-testid="task-timeline"'), "conversation shell must not render a task timeline card under the chat");
assert(!app.includes('className="summary-grid"'), "conversation shell must keep the center workspace chat-only");
assert(!app.includes('className="system-task-strip"'), "conversation shell must not render status strips inside the chat canvas");
assert(!app.includes('className="conversation-main-header"'), "conversation shell must not render a secondary explanatory header");
assert(!app.includes('className="empty-conversation"'), "empty conversation state must not render a card-like prompt block");
assert(!app.includes('className="prompt-example"'), "empty conversation state must not render example cards");
assert(!app.includes("当前对话流"), "conversation shell must avoid persistent explanatory copy");
assert(!app.includes("连续追问"), "conversation shell must avoid persistent explanatory copy");

const parsedSkills = JSON.parse(skillCatalog);
assert(parsedSkills.some((skill) => skill.id === "single-stock-diagnosis"), "skill catalog must include single-stock diagnosis");
assert(parsedSkills.some((skill) => skill.id === "strategy-precheck"), "skill catalog must include strategy precheck");

console.log("desktop client contract passed");
