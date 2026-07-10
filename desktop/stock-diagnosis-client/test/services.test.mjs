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
          price_cny: 1182.19,
          basic_date: "20260709",
          latest_price: { date: "2026-07-09", amount: 123456789, close: 8352.0053, close_is_adjusted: true },
          returns: { ret_20d: 0.035, ret_60d: -0.021 },
          daily_basic: { pe_ttm: 17.8666, pb: 5.4554, ps_ttm: 8.5848, total_mv: 147783396.6704, turnover_rate: 0.2728 },
          moneyflow: { net_mf_amount: -39120.75 },
          warnings: ["price/daily 为后复权价(回测口径),非真实股价"],
          data_sources: ["price/daily/600519.parquet", "daily_basic/daily_basic_all.parquet", "moneyflow/moneyflow_all.parquet"],
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
  assert.equal(result.thread.id, "stock-600519");
  assert.equal(result.thread.code, "600519");
  assert.equal(result.thread.name, "贵州茅台");
  assert.equal(result.decision.verdict, "观察");
  assert(result.decision.notHeld.includes("等待"));
  assert(result.decision.held.includes("控制仓位"));
  assert(result.evidence.some((item) => item.includes("真实股价")));
  assert(result.evidence.some((item) => item.includes("PE_TTM")));
  assert(result.evidence.some((item) => item.includes("资金流净额")));
  assert(result.evidence.some((item) => item.includes("price/daily/600519.parquet")));
  assert(result.limits.some((item) => item.includes("不构成交易建议")));
  assert.equal(result.turns.at(-2).role, "user");
  assert.equal(result.turns.at(-1).role, "assistant");
});

test("diagnosis service keeps follow-up questions in the current stock thread", async () => {
  const { createDiagnosisService } = await import("../src/main/diagnosisService.cjs");
  const calls = [];
  const service = createDiagnosisService({
    readClient: {
      async resolveStockCode() {
        return null;
      },
      async getStockProfile(code) {
        calls.push(code);
        return {
          code,
          name: "贵州茅台",
          price_cny: 1182.19,
          basic_date: "20260709",
          latest_price: { date: "2026-07-09", close: 8352.0053 },
          returns: { ret_20d: -0.041, ret_60d: -0.153 },
          daily_basic: { pe_ttm: 17.8666, pb: 5.4554, ps_ttm: 8.5848, total_mv: 147783396.6704 },
          moneyflow: { net_mf_amount: -39120.75 },
          data_sources: ["price/daily/600519.parquet"],
          warnings: [],
        };
      },
    },
    piBridge: {
      async explainDiagnosis() {
        return { ready: false, text: "" };
      },
    },
  });

  const result = await service.runDiagnosis("最大下行风险是什么", {
    currentThread: { id: "stock-600519", code: "600519", name: "贵州茅台" },
    turns: [{ role: "user", content: "600519 最近怎么样" }],
  });

  assert.deepEqual(calls, ["600519"]);
  assert.equal(result.thread.id, "stock-600519");
  assert.equal(result.thread.code, "600519");
  assert.equal(result.turns.length, 3);
  assert.equal(result.turns.at(-2).content, "最大下行风险是什么");
});

test("diagnosis service records selected stock skills from the local registry", async () => {
  const { createDiagnosisService } = await import("../src/main/diagnosisService.cjs");
  const service = createDiagnosisService({
    readClient: {
      async getStockProfile(code) {
        return {
          code,
          name: "贵州茅台",
          price_cny: 1182.19,
          basic_date: "20260709",
          latest_price: { date: "2026-07-09", close: 8352.0053 },
          returns: { ret_20d: -0.041, ret_60d: -0.153 },
          daily_basic: { pe_ttm: 17.8666, pb: 5.4554, ps_ttm: 8.5848, total_mv: 147783396.6704 },
          moneyflow: {},
          data_sources: ["price/daily/600519.parquet"],
          warnings: [],
        };
      },
    },
    piBridge: {
      async explainDiagnosis() {
        return { ready: false, text: "" };
      },
    },
  });

  const result = await service.runDiagnosis("600519 当前估值贵不贵", {
    selectedSkillId: "valuation-snapshot",
  });

  assert.equal(result.activeSkills[0].id, "valuation-snapshot");
  assert(result.taskSteps[0].name.includes("估值快照"));
  assert(result.evidence[0].includes("选中 Skill: 估值快照"));
  assert(result.sourceChips[0].includes("Skill: 估值"));
  assert(result.limits.some((item) => item.includes("Skill 边界")));
});

test("diagnosis service lets Pi orchestrate a whitelisted stock skill plan", async () => {
  const { createDiagnosisService } = await import("../src/main/diagnosisService.cjs");
  const profileCalls = [];
  const service = createDiagnosisService({
    readClient: {
      async resolveStockCode() {
        throw new Error("direct resolver should not run when Pi supplied profile code");
      },
      async getStockProfile(code) {
        profileCalls.push(code);
        return {
          code,
          name: "贵州茅台",
          price_cny: 1182.19,
          basic_date: "20260709",
          latest_price: { date: "2026-07-09", close: 8352.0053 },
          returns: { ret_20d: -0.041, ret_60d: -0.153 },
          daily_basic: { pe_ttm: 17.8666, pb: 5.4554, ps_ttm: 8.5848, total_mv: 147783396.6704 },
          moneyflow: {},
          data_sources: ["price/daily/600519.parquet"],
          warnings: [],
        };
      },
    },
    piBridge: {
      async orchestrateSkillExecution() {
        return {
          ready: true,
          selectedSkillId: "valuation-snapshot",
          toolRequests: [{ tool: "get_stock_profile", args: { code: "600519" } }],
          blockedToolRequests: [],
          rationale: "用户询问估值，先读取股票画像。",
        };
      },
      async explainDiagnosis() {
        return { ready: false, text: "" };
      },
    },
  });

  const result = await service.runDiagnosis("茅台估值贵不贵");

  assert.deepEqual(profileCalls, ["600519"]);
  assert.equal(result.activeSkills[0].id, "valuation-snapshot");
  assert.equal(result.agentTrace.orchestrator, "pi");
  assert(result.taskSteps[0].name.includes("Pi agent 编排"));
  assert(result.evidence.some((item) => item.includes("白名单工具 get_stock_profile")));
  assert(result.limits.some((item) => item.includes("Pi agent 工具白名单")));
  assert(result.sourceChips.includes("tool-whitelist"));
});

test("diagnosis service supports strategy precheck skill without fake backtest data", async () => {
  const { createDiagnosisService } = await import("../src/main/diagnosisService.cjs");
  const service = createDiagnosisService({
    readClient: {
      async resolveStockCode() {
        return null;
      },
      async getStockProfile() {
        throw new Error("strategy precheck must not fetch a stock profile");
      },
    },
    piBridge: {
      async explainDiagnosis() {
        return { ready: false, text: "" };
      },
    },
  });

  const result = await service.runDiagnosis("低估值 + 资金流转正，每周调仓", {
    selectedSkillId: "strategy-precheck",
    currentThread: { id: "stock-600519", code: "600519", name: "贵州茅台" },
  });

  assert.equal(result.thread.name, "策略想法预检");
  assert.equal(result.thread.status, "待模拟盘");
  assert.equal(result.activeSkills[0].id, "strategy-precheck");
  assert(result.decision.summary.includes("不会生成伪收益曲线"));
  assert(result.limits.some((item) => item.includes("不执行回测")));
  assert(result.sourceChips.includes("no-fake-curve"));
});

test("Pi bridge uses an ephemeral no-tools command by default", async () => {
  const { buildPiArgs } = await import("../src/main/piBridge.cjs");

  const args = buildPiArgs("解释当前诊断", { model: "openai/gpt-4o-mini", skillPaths: ["/tmp/safe-skill.md"] });

  assert(args.includes("--no-tools"));
  assert(args.includes("--no-session"));
  assert(args.includes("--mode"));
  assert(args.includes("text"));
  assert(args.includes("--skill"));
  assert(args.includes("/tmp/safe-skill.md"));
  assert(args.includes("-p"));
  assert(!args.includes("bash"));
  assert(!args.includes("write"));
});

test("Pi bridge sanitizes skill orchestration plans to whitelisted tools", async () => {
  const { sanitizeOrchestrationPlan } = await import("../src/main/piBridge.cjs");
  const plan = sanitizeOrchestrationPlan(JSON.stringify({
    selectedSkillId: "valuation-snapshot",
    toolRequests: [
      { tool: "get_stock_profile", args: { code: "600519" } },
      { tool: "bash", args: { cmd: "curl example.com" } },
    ],
    rationale: "read profile",
  }), [{ id: "valuation-snapshot" }]);

  assert.equal(plan.selectedSkillId, "valuation-snapshot");
  assert.deepEqual(plan.toolRequests, [{ tool: "get_stock_profile", args: { code: "600519" } }]);
  assert.equal(plan.blockedToolRequests.length, 1);
  assert.equal(plan.blockedToolRequests[0].tool, "bash");
});

test("read service client resolves common stock names before hitting the local API", async () => {
  const { extractStockCode } = await import("../src/main/readServiceClient.cjs");

  assert.equal(extractStockCode("帮我看看贵州茅台还能不能买"), "600519");
  assert.equal(extractStockCode("宁德时代今天风险大吗"), "300750");
  assert.equal(extractStockCode("601012 可以观察吗"), "601012");
  assert.equal(extractStockCode("完全不知道是哪只票"), null);
});

test("read service client can resolve non-hardcoded stock names through the local Python resolver", async () => {
  const { createReadServiceClient } = await import("../src/main/readServiceClient.cjs");
  const calls = [];
  const client = createReadServiceClient({
    resolveStockCodeFn: async (query) => {
      assert.equal(query, "汇川技术现在怎么样");
      return "300124";
    },
    fetchFn: async (url, init = {}) => {
      calls.push({ url, init });
      if (String(url).endsWith("/data/stocks/300124")) {
        return {
          ok: true,
          async json() {
            return { code: "300124", name: "汇川技术", latest_price: { date: "2026-07-09" }, returns: {}, data_sources: [] };
          },
        };
      }
      throw new Error(`unexpected url ${url}`);
    },
  });

  const profile = await client.getStockProfile("汇川技术现在怎么样");

  assert.equal(profile.code, "300124");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.method, "GET");
});
