import { useEffect, useRef, useState } from "react";

const initialDiagnosis = {
  thread: { id: "empty", name: "等待输入", code: "", status: "等待输入" },
  taskSteps: [
    { name: "识别股票", desc: "等待输入股票名称或 6 位代码。", status: "pending" },
    { name: "检查数据新鲜度", desc: "提交后读取本地 Python read service。", status: "pending" },
    { name: "读取风险快照", desc: "汇总真实股价、估值、收益和资金流。", status: "pending" },
    { name: "生成保守诊断卡", desc: "拆分未持有与已持有两种动作语境。", status: "pending" },
  ],
  decision: {
    verdict: "等待输入",
    note: "还没有读取任何股票画像。",
    summary: "输入股票名或 6 位代码后，客户端会先解析代码，再从本地 Python read service 读取真实数据。",
    notHeld: "先输入目标股票，再进入观察池判断。",
    held: "先读取本地画像，再讨论持有风险。",
  },
  risks: ["尚未选择股票。"],
  evidence: ["尚未读取本地数据。"],
  limits: [
    "本结果不构成交易建议。",
    "客户端只读本地数据，不连接交易执行。",
  ],
  sourceChips: ["等待输入", "read-only"],
  piExplanation: "",
  turns: [],
};

function statusClass(status) {
  if (status === "谨慎持有") return "hold";
  if (status === "等待输入") return "waiting";
  if (status === "错误") return "error";
  if (status === "数据不足") return "insufficient";
  return "observe";
}

function unavailableDiagnosis(prompt, message) {
  return {
    thread: { id: `error-${Date.now()}`, name: "本地数据服务不可用", code: "", status: "错误" },
    taskSteps: [
      { name: "识别股票", desc: "请求已收到。", status: "done" },
      { name: "连接本地数据服务", desc: "读取 Python read service 失败。", status: "blocked" },
      { name: "读取风险快照", desc: "未读取到真实数据。", status: "pending" },
      { name: "生成保守诊断卡", desc: "已停止，避免用假数据填充。", status: "blocked" },
    ],
    decision: {
      verdict: "错误",
      note: "本地数据服务不可用。",
      summary: `用户问题：“${prompt}”。客户端没有拿到真实数据，因此不会展示 demo 结论。错误: ${message}`,
      notHeld: "先不要进入候选。",
      held: "先不要按当前失败结果调整仓位。",
    },
    risks: ["未读取到本地 Python read service。", "当前界面没有使用假数据兜底。"],
    evidence: [`用户输入: ${prompt}`, `错误: ${message}`],
    limits: ["需要启动本地 read service 后才能诊断。"],
    sourceChips: ["offline", "no-demo"],
    piExplanation: "",
    turns: [{ role: "user", content: prompt }, { role: "assistant", content: `本地数据服务不可用: ${message}` }],
  };
}

function browserPreviewDiagnosis(prompt) {
  return unavailableDiagnosis(prompt, "未连接 Electron preload，请通过 AStock Lens.app 打开。");
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
        {threads.length === 0 && (
          <div className="thread-empty">
            <div>暂无诊断线程</div>
            <div>从底部输入股票名或代码开始。</div>
          </div>
        )}
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
              <div className={`step-dot ${step.status}`}>
                {step.status === "done" ? "✓" : step.status === "blocked" ? "!" : "·"}
              </div>
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

function ConversationHistory({ turns = [] }) {
  if (!turns.length) return null;
  return (
    <section className="card conversation-card" data-testid="conversation-history">
      <div className="card-header">
        <div>
          <div className="card-title">连续追问</div>
          <div className="card-subtitle">围绕当前股票保留上下文，不新开线程。</div>
        </div>
      </div>
      <div className="conversation-list">
        {turns.slice(-8).map((turn, index) => (
          <div className={`turn ${turn.role}`} key={`${turn.role}-${index}-${turn.content}`}>
            <div className="turn-role">{turn.role === "user" ? "你" : "AStock Lens"}</div>
            <div className="turn-content">{turn.content}</div>
          </div>
        ))}
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
        <div>
          Read service: {runtime?.readServiceUrl || "http://127.0.0.1:8011"}
          {runtime?.readService ? ` (${runtime.readService.available ? "ready" : "offline"})` : ""}
        </div>
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
          <span className={`status-dot ${runtime?.readService?.available === false ? "offline" : ""}`} aria-hidden="true"></span>
          <span>{runtime?.readService?.available === false ? "Read service offline" : "Local API mode"}</span>
        </div>
      </header>
      <section className="workspace-scroll" aria-label="当前诊断任务">
        <ConversationHistory turns={diagnosis.turns} />
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
  const [diagnoses, setDiagnoses] = useState([initialDiagnosis]);
  const [threads, setThreads] = useState([]);
  const [activeId, setActiveId] = useState(initialDiagnosis.thread.id);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [runtime, setRuntime] = useState(null);
  const inputRef = useRef(null);

  const activeDiagnosis = diagnoses.find((item) => item.thread.id === activeId) || initialDiagnosis;

  useEffect(() => {
    window.astock?.getRuntimeStatus?.().then(setRuntime).catch(() => undefined);
  }, []);

  async function submit(event) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || loading) return;
    setLoading(true);
    try {
      const context = activeDiagnosis.thread?.code
        ? {
            currentThread: activeDiagnosis.thread,
            turns: activeDiagnosis.turns || [],
          }
        : {};
      const result = window.astock?.runDiagnosis
        ? await window.astock.runDiagnosis({ prompt: text, context })
        : browserPreviewDiagnosis(text);
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
    } catch (error) {
      const result = unavailableDiagnosis(text, error?.message || String(error));
      setDiagnoses((prev) => [result, ...prev.filter((item) => item.thread.id !== result.thread.id)]);
      setThreads((prev) => [
        {
          ...result.thread,
          updated: "刚刚",
        },
        ...prev.filter((thread) => thread.id !== result.thread.id),
      ]);
      setActiveId(result.thread.id);
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
        onNew={() => {
          setActiveId(initialDiagnosis.thread.id);
          setPrompt("");
          inputRef.current?.focus();
        }}
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
