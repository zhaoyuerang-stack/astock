import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(ROOT, relative), "utf8");
}

test("current product routes are the only route contracts under test", () => {
  for (const relative of [
    "app/dashboard/page.tsx",
    "app/portfolio-risk/page.tsx",
    "app/signal-audit/page.tsx",
    "app/strategy-registry/page.tsx",
    "app/factor-research/page.tsx",
    "app/backtest-lab/page.tsx",
    "app/data-health/page.tsx",
    "app/system-governance/page.tsx",
  ]) {
    assert.equal(fs.existsSync(path.join(ROOT, relative)), true, `${relative} must exist`);
  }

  assert.equal(fs.existsSync(path.join(ROOT, "app/portfolio/page.tsx")), false);
  assert.equal(fs.existsSync(path.join(ROOT, "app/factors/page.tsx")), false);
});

test("frontend pages do not keep obvious fake-data scaffolds", () => {
  const pages = [
    "app/factor-research/page.tsx",
    "app/backtest-lab/page.tsx",
    "app/data-health/page.tsx",
    "app/system-governance/page.tsx",
    "app/dashboard/page.tsx",
    "app/signal-audit/page.tsx",
    "app/strategy-registry/page.tsx",
  ];

  for (const relative of pages) {
    const source = read(relative);
    assert.doesNotMatch(source, /Mock|mock keys|fallback|硬编码|all PASS|全部 PASS/);
    assert.doesNotMatch(source, /\|\|\s*['"]0\.012['"]|\|\|\s*1\.58|\|\|\s*1\.85/);
  }
});

test("ops pages do not ship static operational facts", () => {
  const dataHealth = read("app/data-health/page.tsx");
  assert.doesNotMatch(dataHealth, /Wind|萬得|同花順|中證指數公司|2026-06-2[34]|07:0[0-9]|0\.02%|0\.45%/);

  const dashboard = read("app/dashboard/page.tsx");
  assert.doesNotMatch(dashboard, /18\.5 bps|0\.082%|325|"-67"|"-42"|"-191"|LOW \(低\)|0\.45%|信息技术/);
});

test("shell and registry pages do not ship static environment metadata", () => {
  const sources = [
    read("components/shell/TopBar.tsx"),
    read("components/shell/Sidebar.tsx"),
    read("lib/appStore.ts"),
    read("app/signal-audit/page.tsx"),
    read("app/strategy-registry/page.tsx"),
  ].join("\n");

  assert.doesNotMatch(
    sources,
    /2026-06-2[345]|deploy_20260624|v2\.3\.0|researcher|Fallback static|模擬刷新|還有 12 個交易日|evidence_\{/
  );
});

test("factor research page does not ship static evidence charts", () => {
  const factorResearch = read("app/factor-research/page.tsx");
  assert.doesNotMatch(
    factorResearch,
    /324\.5%|12\.5 天|18\.5 bps|22\.40%|-8\.65%|42\.1%|Newey-West 校正已啟用/
  );
});
