const { extractStockCode } = require("./readServiceClient.cjs");

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

function unresolvedDiagnosis(prompt) {
  return {
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
    piExplanation: "",
  };
}

function createDiagnosisService({ readClient, piBridge }) {
  if (!readClient) throw new Error("readClient is required");

  return {
    async runDiagnosis(prompt) {
      const code = readClient.resolveStockCode
        ? await readClient.resolveStockCode(prompt)
        : extractStockCode(prompt);
      if (!code) {
        return unresolvedDiagnosis(prompt);
      }

      const profile = await readClient.getStockProfile(code);
      const decision = buildDecision(profile);
      const diagnosis = {
        thread: {
          id: `${profile.code}-${Date.now()}`,
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
        piExplanation: "",
      };

      if (piBridge?.explainDiagnosis) {
        const explanation = await piBridge.explainDiagnosis(diagnosis);
        if (explanation?.text) {
          diagnosis.piExplanation = explanation.text;
        }
      }
      return diagnosis;
    },
  };
}

module.exports = {
  TASK_STEPS,
  createDiagnosisService,
  buildDecision,
  chooseVerdict,
};
