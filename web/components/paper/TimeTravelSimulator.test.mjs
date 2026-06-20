// Task 18: 生产视图默认不渲染合成美股数据 —— 源码不变量测试(无需 DOM)。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const sim = readFileSync(join(here, "TimeTravelSimulator.tsx"), "utf8");
const page = readFileSync(join(here, "../../app/portfolio/page.tsx"), "utf8");
const banner = readFileSync(join(here, "SimulationModeBanner.tsx"), "utf8");

test("模拟器默认 real(真实模拟盘),不默认渲染 demo", () => {
  assert.match(sim, /useState<"real"\s*\|\s*"demo">\("real"\)/);
});

test("real 模式无数据时不回退到美股 demo(显式守卫)", () => {
  assert.match(sim, /mode === "real" && realPoints\.length === 0/);
});

test("demo(沙盒)模式渲染常驻水印 banner", () => {
  assert.match(sim, /mode === "demo" && <SimulationModeBanner/);
});

test("AAPL/NVDA/TSLA 只存在于 DEMO_DATA,不进入 realPoints 构建逻辑", () => {
  const realBlock = sim.split("const realPoints")[1].split("activeData")[0];
  assert.ok(!/AAPL|NVDA|TSLA/.test(realBlock), "realPoints 构建里不得出现美股 mock");
});

test("portfolio tab 已从「时空穿梭机」重命名为「策略模拟沙盒」", () => {
  assert.ok(!page.includes("时空穿梭机"), "production tab 不应再叫时空穿梭机");
  assert.match(page, /策略模拟沙盒/);
});

test("沙盒 banner 明确标注不可用于交易", () => {
  assert.match(banner, /不可用于交易/);
});
