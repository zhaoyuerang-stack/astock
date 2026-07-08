import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import assert from "node:assert/strict";

const __dirname = dirname(fileURLToPath(import.meta.url));
const htmlPath = join(__dirname, "index.html");

assert(existsSync(htmlPath), "Missing prototype entrypoint: index.html");

const html = readFileSync(htmlPath, "utf8");

const requiredSelectors = [
  'data-testid="thread-sidebar"',
  'data-testid="diagnosis-workspace"',
  'data-testid="evidence-panel"',
  'data-testid="bottom-composer"',
  'data-testid="decision-card"',
  'data-testid="task-timeline"',
];

for (const marker of requiredSelectors) {
  assert(html.includes(marker), `Missing required UI marker: ${marker}`);
}

const requiredCopy = [
  "股票诊断线程",
  "贵州茅台 600519",
  "观察",
  "如果未持有",
  "如果已持有",
  "问一只股票，或继续推进当前诊断",
  "证据",
  "限制",
  "可追问",
];

for (const text of requiredCopy) {
  assert(html.includes(text), `Missing required UI copy: ${text}`);
}

assert(
  html.indexOf('data-testid="bottom-composer"') > html.indexOf('data-testid="diagnosis-workspace"'),
  "Bottom composer should live inside the middle diagnosis workspace, after the main content.",
);

console.log("stock diagnosis client contract passed");
