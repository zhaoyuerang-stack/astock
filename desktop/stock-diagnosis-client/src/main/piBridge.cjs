const { execFile } = require("node:child_process");
const { promisify } = require("node:util");

const execFileAsync = promisify(execFile);

function buildPiArgs(prompt, options = {}) {
  const args = ["--no-tools", "--no-session", "--mode", "text"];
  if (options.model) {
    args.push("--model", options.model);
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
  };
}

module.exports = {
  buildPiArgs,
  createPiBridge,
  detectPi,
};
