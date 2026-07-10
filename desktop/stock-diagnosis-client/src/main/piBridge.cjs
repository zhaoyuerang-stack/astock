const { execFile } = require("node:child_process");
const path = require("node:path");
const { promisify } = require("node:util");

const execFileAsync = promisify(execFile);
const ALLOWED_SKILL_TOOLS = ["resolve_stock_code", "get_stock_profile", "record_strategy_precheck"];

function buildPiArgs(prompt, options = {}) {
  const args = ["--no-tools", "--no-session", "--mode", options.mode || "text"];
  if (options.model) {
    args.push("--model", options.model);
  }
  for (const skillPath of options.skillPaths || []) {
    args.push("--skill", skillPath);
  }
  args.push("-p", String(prompt || ""));
  return args;
}

async function detectPi(command = "pi") {
  try {
    const { stdout } = await execFileAsync("which", [command], { timeout: 1500 });
    return { available: true, command: stdout.trim() || command };
  } catch (error) {
    return { available: false, command, error: error.message };
  }
}

function createPiBridge(options = {}) {
  const command = options.command || process.env.ASTOCK_PI_COMMAND || "pi";
  const model = options.model || process.env.ASTOCK_PI_MODEL || "";
  const timeout = Number(options.timeout || process.env.ASTOCK_PI_TIMEOUT_MS || 12000);

  return {
    async getStatus() {
      return detectPi(command);
    },

    async explainDiagnosis(diagnosis) {
      const status = await detectPi(command);
      if (!status.available) {
        return { ready: false, text: "", error: status.error };
      }

      const prompt = [
        "你是股票诊断客户端里的解释层，只能解释已有证据，不能生成交易指令。",
        "请用三句话解释这个保守诊断，并保留限制边界。",
        JSON.stringify({
          stock: diagnosis.thread,
          verdict: diagnosis.decision.verdict,
          evidence: diagnosis.evidence,
          limits: diagnosis.limits,
        }),
      ].join("\n");

      try {
        const args = buildPiArgs(prompt, { model: model || undefined });
        const { stdout } = await execFileAsync(status.command, args, {
          timeout,
          env: {
            ...process.env,
            PI_OFFLINE: process.env.PI_OFFLINE || "1",
            PI_CODING_AGENT_DIR:
              process.env.ASTOCK_PI_CONFIG_DIR || process.env.PI_CODING_AGENT_DIR || process.cwd(),
          },
          maxBuffer: 1024 * 128,
        });
        return { ready: true, text: stdout.trim() };
      } catch (error) {
        return { ready: false, text: "", error: error.message };
      }
    },

    async orchestrateSkillExecution({ prompt, context = {}, skills = [], selectedSkill = null } = {}) {
      const status = await detectPi(command);
      if (!status.available) {
        return { ready: false, error: status.error, toolRequests: [], blockedToolRequests: [] };
      }

      const orchestrationPrompt = buildSkillOrchestrationPrompt({
        prompt,
        context,
        skills,
        selectedSkill,
      });

      try {
        const args = buildPiArgs(orchestrationPrompt, {
          model: model || undefined,
          skillPaths: resolveSkillPaths(skills, selectedSkill),
        });
        const { stdout } = await execFileAsync(status.command, args, {
          timeout,
          env: {
            ...process.env,
            PI_OFFLINE: process.env.PI_OFFLINE || "1",
            PI_CODING_AGENT_DIR:
              process.env.ASTOCK_PI_CONFIG_DIR || process.env.PI_CODING_AGENT_DIR || process.cwd(),
          },
          maxBuffer: 1024 * 128,
        });
        return sanitizeOrchestrationPlan(stdout, skills);
      } catch (error) {
        return { ready: false, error: error.message, toolRequests: [], blockedToolRequests: [] };
      }
    },
  };
}

function publicSkillForPrompt(skill) {
  return {
    id: skill.id,
    name: skill.name,
    category: skill.category,
    description: skill.description,
    boundary: skill.boundary,
    requiresStock: Boolean(skill.requiresStock),
    mode: skill.mode,
  };
}

function buildSkillOrchestrationPrompt({ prompt, context = {}, skills = [], selectedSkill = null }) {
  return [
    "你是 AStock Lens 的 Pi agent 编排层。",
    "你只负责选择 skill 和提出白名单工具请求；真实工具由 Electron 主进程执行。",
    "禁止编造行情、估值、收益、资金流、回测、净值曲线或交易结论。",
    `允许的工具名: ${ALLOWED_SKILL_TOOLS.join(", ")}。`,
    "必须只输出 JSON，不要 Markdown，不要解释文字。",
    "JSON schema:",
    JSON.stringify({
      selectedSkillId: "one of skill ids or empty string",
      toolRequests: [
        { tool: "resolve_stock_code", args: { query: "user text" } },
        { tool: "get_stock_profile", args: { code: "600519" } },
        { tool: "record_strategy_precheck", args: { prompt: "strategy idea" } },
      ],
      rationale: "short reason",
    }),
    "规则:",
    "- 用户显式选择 skill 时，不要改选其他 skill。",
    "- stock_profile skill 通常需要 resolve_stock_code 和 get_stock_profile。",
    "- strategy_precheck 只能请求 record_strategy_precheck，不能请求 get_stock_profile 来伪造回测。",
    "- 如果证据不足，只请求工具或返回空 toolRequests；不要自行补全数据。",
    JSON.stringify({
      userPrompt: String(prompt || ""),
      selectedSkillId: selectedSkill?.id || "",
      currentThread: context.currentThread || context.thread || null,
      skills: skills.map(publicSkillForPrompt),
    }),
  ].join("\n");
}

function resolveSkillPaths(skills = [], selectedSkill = null) {
  const candidates = selectedSkill ? [selectedSkill] : skills;
  return candidates
    .map((skill) => skill?.piSkillFile)
    .filter(Boolean)
    .map((relativePath) => path.resolve(__dirname, relativePath));
}

function extractJsonObject(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch (_error) {
    const start = trimmed.indexOf("{");
    const end = trimmed.lastIndexOf("}");
    if (start === -1 || end === -1 || end <= start) return null;
    try {
      return JSON.parse(trimmed.slice(start, end + 1));
    } catch (_parseError) {
      return null;
    }
  }
}

function sanitizeOrchestrationPlan(stdout, skills = []) {
  const parsed = extractJsonObject(stdout) || {};
  const skillIds = new Set(skills.map((skill) => skill.id));
  const requestedSkillId = typeof parsed.selectedSkillId === "string" && skillIds.has(parsed.selectedSkillId)
    ? parsed.selectedSkillId
    : "";
  const rawRequests = Array.isArray(parsed.toolRequests) ? parsed.toolRequests : [];
  const toolRequests = [];
  const blockedToolRequests = [];

  for (const request of rawRequests) {
    const tool = typeof request?.tool === "string" ? request.tool : "";
    const args = request?.args && typeof request.args === "object" && !Array.isArray(request.args)
      ? request.args
      : {};
    if (ALLOWED_SKILL_TOOLS.includes(tool)) {
      toolRequests.push({ tool, args });
    } else if (tool) {
      blockedToolRequests.push({ tool, reason: "tool is not whitelisted" });
    }
  }

  return {
    ready: true,
    selectedSkillId: requestedSkillId,
    toolRequests,
    blockedToolRequests,
    rationale: typeof parsed.rationale === "string" ? parsed.rationale.slice(0, 500) : "",
  };
}

module.exports = {
  ALLOWED_SKILL_TOOLS,
  buildPiArgs,
  buildSkillOrchestrationPrompt,
  createPiBridge,
  detectPi,
  sanitizeOrchestrationPlan,
};
