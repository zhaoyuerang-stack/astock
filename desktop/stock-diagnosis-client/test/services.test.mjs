import test from "node:test";
import assert from "node:assert/strict";

test("diagnosis service builds a conservative stock diagnosis from a read-service profile", async () => {
  const { createDiagnosisService } = await import("../src/main/diagnosisService.cjs");
  const calls = [];
  const service = createDiagnosisService({
    readClient: {
      async getStockProfile(code) {
        calls.push(code);
        return {
          code,
          name: "贵州茅台",
          latest_price: { date: "2026-07-08", amount: 123456789 },
          returns: { ret_20d: 0.035, ret_60d: -0.021 },
          warnings: ["price/daily 为后复权价(回测口径),非真实股价"],
          data_sources: ["price/daily/600519.parquet", "daily_basic/daily_basic_all.parquet"],
        };
      },
    },
    piBridge: {
      async explainDiagnosis() {
        return { ready: false, text: "" };
      },
    },
  });

  const result = await service.runDiagnosis("帮我看看贵州茅台还能不能买");

  assert.deepEqual(calls, ["600519"]);
  assert.equal(result.thread.code, "600519");
  assert.equal(result.thread.name, "贵州茅台");
  assert.equal(result.decision.verdict, "观察");
  assert(result.decision.notHeld.includes("等待"));
  assert(result.decision.held.includes("控制仓位"));
  assert(result.evidence.some((item) => item.includes("price/daily/600519.parquet")));
  assert(result.limits.some((item) => item.includes("不构成交易建议")));
});

test("Pi bridge uses an ephemeral no-tools command by default", async () => {
  const { buildPiArgs } = await import("../src/main/piBridge.cjs");

  const args = buildPiArgs("解释当前诊断", { model: "openai/gpt-4o-mini" });

  assert(args.includes("--no-tools"));
  assert(args.includes("--no-session"));
  assert(args.includes("--mode"));
  assert(args.includes("text"));
  assert(args.includes("-p"));
  assert(!args.includes("bash"));
  assert(!args.includes("write"));
});

test("read service client resolves common stock names before hitting the local API", async () => {
  const { extractStockCode } = await import("../src/main/readServiceClient.cjs");

  assert.equal(extractStockCode("帮我看看贵州茅台还能不能买"), "600519");
  assert.equal(extractStockCode("宁德时代今天风险大吗"), "300750");
  assert.equal(extractStockCode("601012 可以观察吗"), "601012");
  assert.equal(extractStockCode("完全不知道是哪只票"), null);
});
