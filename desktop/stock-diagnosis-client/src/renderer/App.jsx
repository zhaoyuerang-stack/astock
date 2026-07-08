import { useEffect, useRef, useState } from "react";

const demoDiagnosis = {
  thread: { id: "600519-demo", name: "贵州茅台", code: "600519", status: "观察" },
  taskSteps: [
    { name: "识别股票", desc: "解析名称、代码和市场。", status: "done" },
    { name: "检查数据新鲜度", desc: "确认可用交易日、PIT 对齐和缺口。", status: "done" },
    { name: "读取风险快照", desc: "汇总流动性、波动、行业和估值风险。", status: "done" },
    { name: "生成保守诊断卡", desc: "拆分未持有与已持有两种动作语境。", status: "done" },
  ],
  decision: {
    verdict: "观察",
    note: "有证据支撑继续跟踪，但缺少足够安全边际。",
    summary: "估值、流动性和趋势状态未给出明确进场信号。当前更适合作为观察对象，而不是交易动作。",
    notHeld: "等待更清晰的风险补偿；不要因为品牌确定性替代买入条件。",
    held: "控制仓位，继续观察趋势和估值修复，不把诊断卡当作加仓指令。",
  },
  risks: [
    "20 日收益和 60 日收益未形成一致方向。",
    "消费基本面修复节奏仍需验证。",
    "诊断只覆盖当前可用数据，不包含盘中交易执行。",
  ],
  evidence: [
    "股票画像: 贵州茅台 600519",
    "最新价格数据日期: 2026-07-08",
    "来源: price/daily/600519.parquet",
    "来源: daily_basic/daily_basic_all.parquet",
  ],
  limits: [
    "本结果不构成交易建议。",
    "当前版本只读本地数据，不连接交易执行。",
    "Agent 只能解释证据，不能替代确定性读模型。",
  ],
  sourceChips: ["数据截至 2026-07-08", "PIT 检查", "风险快照", "read-only"],
  piExplanation: "",
};

const seedThreads = [
  { id: "600519-demo", name: "贵州茅台", code: "600519", status: "观察", updated: "刚刚" },
  { id: "300750-demo", name: "宁德时代", code: "300750", status: "谨慎持有", updated: "12 分钟前" },
  { id: "601012-demo", name: "隆基绿能", code: "601012", status: "数据不足", updated: "昨天" },
];

function statusClass(status) {
  if (status === "谨慎持有") return "hold";
  if (status === "数据不足") return "insufficient";
  return "observe";
}

function fallbackDiagnosis(prompt) {
  const base = structuredClone(demoDiagnosis);
  base.thread = { id: `local-${Date.now()}`, name: "待接本地 API", code: "", status: "数据不足" };
  base.decision = {
    verdict: "数据不足",
    note: "当前运行在浏览器预览模式，未连接 Electron preload。",
    summary: `用户问题：“${prompt}”。启动 Electron 后会通过本地 Python read service 返回真实证据。`,
    notHeld: "先不要进入候选。",
    held: "先不要按预览模式调整仓位。",
  };
  base.risks = ["未连接 Electron 主进程。", "未读取本地 Python read service。"];
  base.evidence = [`用户输入: ${prompt}`];
  base.limits = ["浏览器预览只用于界面检查。"];
  base.sourceChips = ["preview", "read-only"];
  return base;
}

function ThreadSidebar({ threads, activeId, onSelect, onNew }) {
  return (
    <aside className="sidebar" data-testid="thread-sidebar" aria-label="股票诊断线程">
      <div className="brand">
        <div className="brand-mark">AL</div>
        <div>
          <div className="brand-title">AStock Lens</div>
          <div className="brand-subtitle">本地优先 · 股票诊断客户端</div>
        </div>
      </div>
      <div className="sidebar-toolbar">
        <button className="new-thread" type="button" onClick={onNew}>
          <span aria-hidden="true">+</span>
          <span>新诊断</span>
        </button>
      </div>
      <div className="thread-list">
        {threads.map((thread) => (
          <button
            key={thread.id}
            className={`thread ${thread.id === activeId ? "active" : ""}`}
            type="button"
            onClick={() => onSelect(thread.id)}
          >
            <div className="thread-title-row">
              <span className="thread-name">
                {thread.name} {thread.code}
              </span>
              <span className={`badge ${statusClass(thread.status)}`}>{thread.status}</span>
            </div>
            <div className="thread-meta">{thread.updated}</div>
          </button>
        ))}
      </div>
      <div className="sidebar-footer">
        <div>股票诊断线程</div>
        <div className="mono">Local engine · read-only</div>
      </div>
    </aside>
  );
}

function DecisionCard({ diagnosis }) {
  const decision = diagnosis.decision;
  return (
    <section className="card" data-testid="decision-card">
      <div className="card-header">
        <div>
          <div className="card-title">保守单股诊断卡</div>
          <div className="card-subtitle">结论只来自已检查证据，保留证据边界。</div>
        </div>
        <span className={`badge ${statusClass(decision.verdict)}`}>{decision.verdict}</span>
      </div>
      <div className="card-body">
        <div className="decision-hero">
          <div className={`verdict-box ${statusClass(decision.verdict)}`}>
            <div className="verdict-label">当前结论</div>
            <div className="verdict">{decision.verdict}</div>
            <div className="verdict-note">{decision.note}</div>
          </div>
          <div>
            <p className="decision-copy">{decision.summary}</p>
            <div className="action-grid">
              <div className="action-card">
                <div className="action-title">如果未持有</div>
                <div className="action-text">{decision.notHeld}</div>
              </div>
              <div className="action-card">
                <div className="action-title">如果已持有</div>
                <div className="action-text">{decision.held}</div>
              </div>
            </div>
          </div>
        </div>
        <ul className="risk-list" aria-label="主要风险">
          {diagnosis.risks.map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function TaskTimeline({ steps }) {
  return (
    <section className="card" data-testid="task-timeline">
      <div className="card-header">
        <div>
          <div className="card-title">任务步骤</div>
          <div className="card-subtitle">Agent 推进诊断，不替代裁决。</div>
        </div>
      </div>
      <div className="card-body">
        <div className="timeline">
          {steps.map((step) => (
            <div className="step" key={step.name}>
              <div className={`step-dot ${step.status}`}>{step.status === "blocked" ? "!" : "✓"}</div>
              <div>
                <div className="step-name">{step.name}</div>
                <div className="step-desc">{step.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function EvidencePanel({ diagnosis, runtime }) {
  return (
    <aside className="evidence" data-testid="evidence-panel" aria-label="证据与 Agent 上下文">
      <div className="panel-section">
        <div className="panel-heading">
          <span>证据</span>
          <span className={`badge ${statusClass(diagnosis.decision.verdict)}`}>当前线程</span>
        </div>
        <div className="chip-row">
          {diagnosis.sourceChips.map((chip) => (
            <span className="chip" key={chip}>
              {chip}
            </span>
          ))}
        </div>
        <ul className="evidence-list">
          {diagnosis.evidence.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div className="panel-section">
        <div className="panel-heading">限制</div>
        <ul className="evidence-list">
          {diagnosis.limits.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      {diagnosis.piExplanation && (
        <div className="panel-section">
          <div className="panel-heading">Pi 解释</div>
          <p className="panel-copy">{diagnosis.piExplanation}</p>
        </div>
      )}
      <div className="panel-section">
        <div className="panel-heading">可追问</div>
        <ul className="question-list">
          <li>这只股票最大的下行风险是什么？</li>
          <li>如果我已经持有，什么情况需要降低仓位？</li>
          <li>这个结论依赖哪些数据，哪些还没覆盖？</li>
        </ul>
      </div>
      <div className="prototype-note">
        <div>Read service: {runtime?.readServiceUrl || "http://127.0.0.1:8011"}</div>
        <div>Pi: {runtime?.pi?.available ? "available" : "not connected"}</div>
      </div>
    </aside>
  );
}

function Workspace({ diagnosis, prompt, setPrompt, onSubmit, loading, inputRef, runtime }) {
  return (
    <main className="workspace" data-testid="diagnosis-workspace">
      <header className="topbar">
        <div>
          <div className="top-title">
            {diagnosis.thread.name} {diagnosis.thread.code}
          </div>
          <div className="top-meta">
            <span>{diagnosis.sourceChips[0] || "数据日期未知"}</span>
            <span>·</span>
            <span>本地诊断</span>
          </div>
        </div>
        <div className="top-meta">
          <span className="status-dot" aria-hidden="true"></span>
          <span>{runtime?.pi?.available ? "Pi ready" : "Local API mode"}</span>
        </div>
      </header>
      <section className="workspace-scroll" aria-label="当前诊断任务">
        <div className="diagnosis-grid">
          <DecisionCard diagnosis={diagnosis} />
          <TaskTimeline steps={diagnosis.taskSteps} />
        </div>
      </section>
      <footer className="composer-shell" data-testid="bottom-composer">
        <form className="composer" onSubmit={onSubmit}>
          <button className="icon-button" type="button" aria-label="添加上下文">
            +
          </button>
          <input
            ref={inputRef}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="问一只股票，或继续推进当前诊断…"
            aria-label="诊断输入"
            disabled={loading}
          />
          <button className="send-button" type="submit" disabled={loading}>
            {loading ? "诊断中" : "发送"}
          </button>
        </form>
      </footer>
    </main>
  );
}

export default function App() {
  const [diagnoses, setDiagnoses] = useState([demoDiagnosis]);
  const [threads, setThreads] = useState(seedThreads);
  const [activeId, setActiveId] = useState(demoDiagnosis.thread.id);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [runtime, setRuntime] = useState(null);
  const inputRef = useRef(null);

  const activeDiagnosis = diagnoses.find((item) => item.thread.id === activeId) || diagnoses[0];

  useEffect(() => {
    window.astock?.getRuntimeStatus?.().then(setRuntime).catch(() => undefined);
  }, []);

  async function submit(event) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || loading) return;
    setLoading(true);
    try {
      const result = window.astock?.runDiagnosis
        ? await window.astock.runDiagnosis(text)
        : fallbackDiagnosis(text);
      setDiagnoses((prev) => [result, ...prev.filter((item) => item.thread.id !== result.thread.id)]);
      setThreads((prev) => [
        {
          ...result.thread,
          updated: "刚刚",
        },
        ...prev.filter((thread) => thread.id !== result.thread.id),
      ]);
      setActiveId(result.thread.id);
      setPrompt("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-frame">
      <ThreadSidebar
        threads={threads}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={() => inputRef.current?.focus()}
      />
      <Workspace
        diagnosis={activeDiagnosis}
        prompt={prompt}
        setPrompt={setPrompt}
        onSubmit={submit}
        loading={loading}
        inputRef={inputRef}
        runtime={runtime}
      />
      <EvidencePanel diagnosis={activeDiagnosis} runtime={runtime} />
    </div>
  );
}
