const { extractStockCode } = require("./readServiceClient.cjs");
const { ALLOWED_SKILL_TOOLS } = require("./piBridge.cjs");
const skillDefinitions = require("../shared/skills.json");

const TASK_STEPS = [
  { name: "识别股票", desc: "解析名称、代码和市场。", status: "done" },
  { name: "检查数据新鲜度", desc: "确认可用交易日、PIT 对齐和缺口。", status: "done" },
  { name: "读取风险快照", desc: "汇总流动性、波动、行业和估值风险。", status: "done" },
  { name: "生成保守诊断卡", desc: "拆分未持有与已持有两种动作语境。", status: "done" },
];

function pct(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未知";
  return `${(value * 100).toFixed(2)}%`;
}

function number(value, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未知";
  return value.toFixed(digits);
}

function tradeDate(value) {
  const text = String(value || "");
  if (/^\d{8}$/.test(text)) {
    return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  }
  return text || "未知";
}

function marketCapYi(totalMvWan) {
  if (typeof totalMvWan !== "number" || !Number.isFinite(totalMvWan)) return "未知";
  return `${(totalMvWan / 10000).toFixed(0)} 亿元`;
}

function moneyWan(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未知";
  return `${value.toFixed(2)} 万元`;
}

function chooseVerdict(profile) {
  const returns = profile.returns || {};
  const ret20 = returns.ret_20d;
  const ret60 = returns.ret_60d;
  if (!profile.latest_price?.date) return "数据不足";
  if (typeof ret20 === "number" && typeof ret60 === "number" && ret20 > 0 && ret60 > 0) {
    return "谨慎持有";
  }
  return "观察";
}

function publicSkill(skill) {
  if (!skill) return null;
  return {
    id: skill.id,
    name: skill.name,
    shortName: skill.shortName,
    category: skill.category,
    description: skill.description,
    boundary: skill.boundary,
    requiresStock: Boolean(skill.requiresStock),
    mode: skill.mode,
  };
}

function normalizeSelectedSkill(context = {}) {
  const requestedId = typeof context.selectedSkillId === "string"
    ? context.selectedSkillId
    : typeof context.selectedSkill?.id === "string"
      ? context.selectedSkill.id
      : "";
  return skillDefinitions.find((skill) => skill.id === requestedId) || null;
}

function skillById(skillId) {
  return skillDefinitions.find((skill) => skill.id === skillId) || null;
}

function skillTaskStep(skill) {
  return {
    name: `启用 Skill: ${skill.name}`,
    desc: skill.description,
    status: "done",
  };
}

function withSkillContext(diagnosis, skill) {
  if (!skill) {
    return { ...diagnosis, activeSkills: diagnosis.activeSkills || [] };
  }
  const skillInfo = publicSkill(skill);
  return {
    ...diagnosis,
    activeSkills: [skillInfo],
    taskSteps: [skillTaskStep(skill), ...(diagnosis.taskSteps || [])],
    evidence: [`选中 Skill: ${skill.name}`, ...(diagnosis.evidence || [])],
    limits: [...(diagnosis.limits || []), `Skill 边界: ${skill.boundary}`],
    sourceChips: [`Skill: ${skill.shortName || skill.name}`, ...(diagnosis.sourceChips || [])],
  };
}

function attachPiOrchestration(diagnosis, orchestration, toolResult = {}) {
  if (!orchestration?.ready) return diagnosis;
  const blockedTools = orchestration.blockedToolRequests || [];
  return {
    ...diagnosis,
    agentTrace: {
      orchestrator: "pi",
      selectedSkillId: orchestration.selectedSkillId || diagnosis.activeSkills?.[0]?.id || "",
      toolWhitelist: ALLOWED_SKILL_TOOLS,
      toolRequests: orchestration.toolRequests || [],
      blockedToolRequests: blockedTools,
      rationale: orchestration.rationale || "",
    },
    taskSteps: [
      {
        name: "Pi agent 编排 Skill",
        desc: `已按白名单工具计划执行；允许工具: ${ALLOWED_SKILL_TOOLS.join(", ")}。`,
        status: "done",
      },
      ...(diagnosis.taskSteps || []),
    ],
    evidence: [
      `Pi agent 编排: ${orchestration.rationale || "已返回白名单工具计划"}`,
      ...(toolResult.toolEvidence || []),
      ...(toolResult.toolErrors || []).map((item) => `白名单工具失败: ${item}`),
      ...(diagnosis.evidence || []),
    ],
    limits: [
      ...(diagnosis.limits || []),
      `Pi agent 工具白名单: ${ALLOWED_SKILL_TOOLS.join(", ")}。`,
      ...blockedTools.map((item) => `已阻止 Pi 请求的非白名单工具: ${item.tool}`),
    ],
    sourceChips: ["Pi agent", "tool-whitelist", ...(diagnosis.sourceChips || [])],
  };
}

function buildDecision(profile) {
  const verdict = chooseVerdict(profile);
  if (verdict === "谨慎持有") {
    return {
      verdict,
      note: "趋势证据尚可，但需要控制单一股票暴露。",
      summary: "当前数据支持继续跟踪持仓，但不支持把诊断结果升级为主动加仓指令。",
      notHeld: "等待更好的风险补偿，不追逐短期强势。",
      held: "控制仓位，保留风险边界，观察趋势能否延续。",
    };
  }
  if (verdict === "数据不足") {
    return {
      verdict,
      note: "关键证据缺失，不能给出稳定判断。",
      summary: "当前诊断缺少足够数据支持，应先补齐证据再讨论操作。",
      notHeld: "暂不进入候选，等待数据补齐。",
      held: "降低对模型结论的信任，优先人工复核风险。",
    };
  }
  return {
    verdict,
    note: "有证据支撑继续跟踪，但缺少足够安全边际。",
    summary: "估值、流动性和趋势状态未给出明确进场信号。当前更适合作为观察对象，而不是交易动作。",
    notHeld: "等待更清晰的风险补偿；不要因为品牌确定性替代买入条件。",
    held: "控制仓位，继续观察趋势和估值修复，不把诊断卡当作加仓指令。",
  };
}

function buildRisks(profile) {
  const basic = profile.daily_basic || {};
  const moneyflow = profile.moneyflow || {};
  const risks = [
    `20 日收益: ${pct(profile.returns?.ret_20d)}；60 日收益: ${pct(profile.returns?.ret_60d)}。`,
  ];
  if (typeof basic.pe_ttm === "number" || typeof basic.pb === "number") {
    risks.push(`估值快照: PE_TTM ${number(basic.pe_ttm)}；PB ${number(basic.pb)}；PS_TTM ${number(basic.ps_ttm)}。`);
  }
  if (typeof moneyflow.net_mf_amount === "number") {
    risks.push(`最新资金流净额: ${moneyWan(moneyflow.net_mf_amount)}。`);
  }
  if (profile.warnings?.length) {
    risks.push(...profile.warnings);
  }
  if (!profile.moneyflow || Object.keys(profile.moneyflow).length === 0) {
    risks.push("资金流证据缺失或不可用。");
  }
  return risks;
}

function buildEvidence(profile) {
  const sources = (profile.data_sources || []).filter(Boolean);
  const basic = profile.daily_basic || {};
  const moneyflow = profile.moneyflow || {};
  const evidence = [
    `股票画像: ${profile.name || profile.code} ${profile.code}`,
    `最新价格数据日期: ${profile.latest_price?.date || "未知"}`,
  ];
  if (typeof profile.price_cny === "number") {
    evidence.push(`真实股价(不复权): ${number(profile.price_cny)} 元；对应估值日期: ${tradeDate(profile.basic_date)}。`);
  }
  if (profile.latest_price?.close !== undefined) {
    evidence.push(`后复权收盘价(仅用于收益计算): ${number(profile.latest_price.close, 4)}；不可当真实股价展示。`);
  }
  if (Object.keys(basic).length) {
    evidence.push(`估值: PE_TTM ${number(basic.pe_ttm)}；PB ${number(basic.pb)}；PS_TTM ${number(basic.ps_ttm)}；总市值 ${marketCapYi(basic.total_mv)}。`);
  }
  if (typeof moneyflow.net_mf_amount === "number") {
    evidence.push(`资金流净额: ${moneyWan(moneyflow.net_mf_amount)}。`);
  }
  return [
    ...evidence,
    ...sources.map((source) => `来源: ${source}`),
  ];
}

function strategyPrecheckDiagnosis(prompt, skill) {
  return {
    thread: { id: `skill-${skill.id}-${Date.now()}`, name: "策略想法预检", code: "", status: "待模拟盘" },
    taskSteps: [
      skillTaskStep(skill),
      { name: "记录策略想法", desc: "已把用户输入作为待验证假设保存到当前对话。", status: "done" },
      { name: "拆解验证口径", desc: "下一步需要明确因子、股票池、调仓频率、成本和样本区间。", status: "pending" },
      { name: "连接 Shadow 模拟盘", desc: "等待后端 read model 暴露组合净值、回撤、换手和失败样本。", status: "pending" },
    ],
    decision: {
      verdict: "待模拟盘",
      note: "策略想法已记录，但还没有进入可审计模拟盘。",
      summary: "当前只能做策略预检：拆清楚假设、数据需求和验证边界；不会生成伪收益曲线。",
      notHeld: "不要把该策略直接作为候选，先补齐可验证定义和失败条件。",
      held: "已有持仓不要按该策略想法调整仓位，先等待 Shadow 模拟盘证据。",
    },
    risks: [
      "缺少可执行的股票池、调仓频率、交易成本和样本区间。",
      "后端尚未暴露用户策略 Shadow 模拟盘 read model。",
    ],
    evidence: [`选中 Skill: ${skill.name}`, `用户输入: ${prompt}`],
    limits: [
      "本结果不构成交易建议。",
      "当前只做策略想法预检，不执行回测，不生成收益曲线。",
      `Skill 边界: ${skill.boundary}`,
    ],
    sourceChips: [`Skill: ${skill.shortName || skill.name}`, "strategy-precheck", "no-fake-curve", "read-only"],
    activeSkills: [publicSkill(skill)],
    piExplanation: "",
  };
}

function unresolvedDiagnosis(prompt, skill = null) {
  const diagnosis = {
    thread: { id: `diagnosis-unresolved-${Date.now()}`, name: "待识别股票", code: "", status: "数据不足" },
    taskSteps: TASK_STEPS.map((step, index) => (index === 0 ? { ...step, status: "blocked" } : { ...step, status: "pending" })),
    decision: {
      verdict: "数据不足",
      note: "未能识别股票代码。",
      summary: "请补充股票名称或 6 位代码。若输入的是简称，本地数据湖必须能在 codes.parquet 中匹配到它。",
      notHeld: "先不要进入候选。",
      held: "先不要按该问题调整仓位。",
    },
    risks: ["无法解析股票代码。"],
    evidence: [`用户输入: ${prompt}`],
    limits: ["本结果不构成交易建议。", "未读取本地 Python read service 的股票画像。"],
    sourceChips: ["待澄清", "read-only"],
    activeSkills: [],
    piExplanation: "",
  };
  return withSkillContext(diagnosis, skill);
}

function normalizeTurns(turns) {
  if (!Array.isArray(turns)) return [];
  return turns
    .filter((turn) => turn && typeof turn.content === "string" && ["user", "assistant"].includes(turn.role))
    .map((turn) => ({ role: turn.role, content: turn.content.slice(0, 800) }))
    .slice(-10);
}

function contextStockCode(context) {
  const thread = context?.currentThread || context?.thread || {};
  return extractStockCode(thread.code || "");
}

function stableThreadId(profile, context) {
  const thread = context?.currentThread || context?.thread || {};
  if (thread.code === profile.code && typeof thread.id === "string" && thread.id) {
    return thread.id;
  }
  return `stock-${profile.code}`;
}

function appendTurns(context, prompt, diagnosis) {
  return [
    ...normalizeTurns(context?.turns || context?.messages),
    { role: "user", content: String(prompt || "").slice(0, 800) },
    { role: "assistant", content: diagnosis.decision.summary },
  ];
}

async function requestPiOrchestration(piBridge, prompt, context, selectedSkill) {
  if (!piBridge?.orchestrateSkillExecution) {
    return { ready: false, toolRequests: [], blockedToolRequests: [] };
  }
  try {
    return await piBridge.orchestrateSkillExecution({
      prompt,
      context,
      skills: skillDefinitions,
      selectedSkill,
    });
  } catch (error) {
    return { ready: false, error: error.message, toolRequests: [], blockedToolRequests: [] };
  }
}

async function executeWhitelistedToolRequests(readClient, toolRequests = [], prompt, context = {}) {
  const result = {
    resolvedCode: "",
    profile: null,
    strategyPrecheckRequested: false,
    toolEvidence: [],
    toolErrors: [],
  };

  for (const request of toolRequests) {
    if (request.tool === "resolve_stock_code") {
      try {
        const query = String(request.args?.query || prompt || "");
        const code = await (readClient.resolveStockCode
          ? readClient.resolveStockCode(query)
          : extractStockCode(query));
        if (code) {
          result.resolvedCode = code;
          result.toolEvidence.push(`白名单工具 resolve_stock_code: ${code}`);
        } else {
          result.toolEvidence.push("白名单工具 resolve_stock_code: 未识别股票代码");
        }
      } catch (error) {
        result.toolErrors.push(`resolve_stock_code: ${error.message}`);
      }
      continue;
    }

    if (request.tool === "get_stock_profile") {
      try {
        const requestedCode = extractStockCode(request.args?.code || "") || result.resolvedCode || contextStockCode(context);
        const codeOrQuery = requestedCode || String(request.args?.query || prompt || "");
        if (!codeOrQuery) {
          result.toolErrors.push("get_stock_profile 缺少股票代码或查询文本");
          continue;
        }
        result.profile = await readClient.getStockProfile(codeOrQuery);
        result.resolvedCode = result.profile?.code || requestedCode || "";
        result.toolEvidence.push(`白名单工具 get_stock_profile: ${result.profile?.name || result.resolvedCode} ${result.resolvedCode}`);
      } catch (error) {
        result.toolErrors.push(`get_stock_profile: ${error.message}`);
      }
      continue;
    }

    if (request.tool === "record_strategy_precheck") {
      result.strategyPrecheckRequested = true;
      result.toolEvidence.push("白名单工具 record_strategy_precheck: 已记录策略想法，等待 Shadow 模拟盘 read model。");
    }
  }

  return result;
}

async function explainWithPi(piBridge, diagnosis) {
  if (!piBridge?.explainDiagnosis) return diagnosis;
  try {
    const explanation = await piBridge.explainDiagnosis(diagnosis);
    if (explanation?.text) {
      return { ...diagnosis, piExplanation: explanation.text };
    }
  } catch (_error) {
    return diagnosis;
  }
  return diagnosis;
}

function createDiagnosisService({ readClient, piBridge }) {
  if (!readClient) throw new Error("readClient is required");

  return {
    async runDiagnosis(prompt, context = {}) {
      const requestedSkill = normalizeSelectedSkill(context);
      const orchestration = await requestPiOrchestration(piBridge, prompt, context, requestedSkill);
      const toolResult = await executeWhitelistedToolRequests(readClient, orchestration.toolRequests, prompt, context);
      const selectedSkill = requestedSkill || skillById(orchestration.selectedSkillId) || (toolResult.strategyPrecheckRequested ? skillById("strategy-precheck") : null);

      if (selectedSkill && selectedSkill.mode === "strategy_precheck") {
        let diagnosis = strategyPrecheckDiagnosis(prompt, selectedSkill);
        diagnosis = attachPiOrchestration(diagnosis, orchestration, toolResult);
        diagnosis.turns = appendTurns(context, prompt, diagnosis);
        return explainWithPi(piBridge, diagnosis);
      }

      let resolveError;
      const promptCode = toolResult.resolvedCode || await (async () => {
        try {
          return readClient.resolveStockCode
            ? await readClient.resolveStockCode(prompt)
            : extractStockCode(prompt);
        } catch (error) {
          resolveError = error;
          return null;
        }
      })();
      const code = promptCode || contextStockCode(context);
      if (!code) {
        if (resolveError) throw resolveError;
        const diagnosis = unresolvedDiagnosis(prompt, selectedSkill);
        diagnosis.turns = appendTurns(context, prompt, diagnosis);
        return diagnosis;
      }

      const profile = toolResult.profile || await readClient.getStockProfile(code);
      const decision = buildDecision(profile);
      let diagnosis = {
        thread: {
          id: stableThreadId(profile, context),
          name: profile.name || profile.code,
          code: profile.code,
          status: decision.verdict,
        },
        taskSteps: TASK_STEPS,
        decision,
        risks: buildRisks(profile),
        evidence: buildEvidence(profile),
        limits: [
          "本结果不构成交易建议。",
          "当前版本只读本地数据，不连接交易执行。",
          "Agent 只能解释证据，不能替代确定性读模型。",
        ],
        sourceChips: [
          profile.latest_price?.date ? `数据截至 ${profile.latest_price.date}` : "数据日期未知",
          typeof profile.price_cny === "number" ? `真实股价 ${number(profile.price_cny)} 元` : "真实股价未知",
          "PIT 检查",
          "风险快照",
          "read-only",
        ],
        activeSkills: [],
        piExplanation: "",
      };
      diagnosis = withSkillContext(diagnosis, selectedSkill);
      diagnosis = attachPiOrchestration(diagnosis, orchestration, toolResult);
      diagnosis.turns = appendTurns(context, prompt, diagnosis);
      return explainWithPi(piBridge, diagnosis);
    },
  };
}

module.exports = {
  TASK_STEPS,
  createDiagnosisService,
  buildDecision,
  chooseVerdict,
  executeWhitelistedToolRequests,
  normalizeSelectedSkill,
};
