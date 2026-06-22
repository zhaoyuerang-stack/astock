// 模拟器只渲染真实模拟盘数据 —— 合成演示(demo)模式与美股 mock 已彻底移除(源码不变量,无需 DOM)。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const sim = readFileSync(join(here, "TimeTravelSimulator.tsx"), "utf8");
const page = readFileSync(join(here, "../../app/portfolio/page.tsx"), "utf8");

test("无任何合成美股 mock(AAPL/NVDA/TSLA/MSFT/DEMO_DATA)", () => {
  assert.ok(!/AAPL|NVDA|TSLA|MSFT|DEMO_DATA/.test(sim), "源码不得残留美股合成数据");
});

test("demo(沙盒)模式已彻底移除:无 mode 状态、无 demo 切换", () => {
  assert.ok(!/"real"\s*\|\s*"demo"/.test(sim), "不应再有 real|demo 模式状态");
  assert.ok(!/setMode|mode === "demo"/.test(sim), "不应再有 demo 切换逻辑");
});

test("SimulationModeBanner 死文件已删除", () => {
  assert.ok(!existsSync(join(here, "SimulationModeBanner.tsx")), "合成数据水印 banner 应已删");
  assert.ok(!/SimulationModeBanner/.test(sim), "不应再引用 banner");
});

test("数据只从真实 nav/trades 派生(realPoints)", () => {
  assert.match(sim, /const realPoints[^=]*=\s*useMemo/);
  assert.match(sim, /const activeData = realPoints/);
});

test("portfolio 页仍渲染模拟器,且 tab 已非「时空穿梭机」", () => {
  assert.match(page, /<TimeTravelSimulator/);
  assert.ok(!page.includes("时空穿梭机"));
});
