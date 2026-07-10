import { useEffect, useRef, useState } from "react";
import skillDefinitions from "../shared/skills.json";
import VisualizationWorkspace from "./visualizations/VisualizationWorkspace.jsx";

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
  activeSkills: [],
  piExplanation: "",
  turns: [],
};

const skillById = new Map(skillDefinitions.map((skill) => [skill.id, skill]));

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

function statusClass(status) {
  if (status === "谨慎持有") return "hold";
  if (status === "等待输入") return "waiting";
  if (status === "错误") return "error";
  if (status === "数据不足" || status === "待模拟盘") return "insufficient";
  return "observe";
}

function unavailableDiagnosis(prompt, message, selectedSkill = null) {
  const activeSkills = selectedSkill ? [publicSkill(selectedSkill)] : [];
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
    evidence: [...(selectedSkill ? [`选中 Skill: ${selectedSkill.name}`] : []), `用户输入: ${prompt}`, `错误: ${message}`],
    limits: ["需要启动本地 read service 后才能诊断。", ...(selectedSkill ? [`Skill 边界: ${selectedSkill.boundary}`] : [])],
    sourceChips: [...(selectedSkill ? [`Skill: ${selectedSkill.shortName || selectedSkill.name}`] : []), "offline", "no-demo"],
    activeSkills,
    piExplanation: "",
    turns: [{ role: "user", content: prompt }, { role: "assistant", content: `本地数据服务不可用: ${message}` }],
  };
}

function browserPreviewDiagnosis(prompt, selectedSkill = null) {
  return unavailableDiagnosis(prompt, "未连接 Electron preload，请通过 AStock Lens.app 打开。", selectedSkill);
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
          <span>新对象</span>
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
        <div>对象线程</div>
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

function SkillPicker({ skills, selectedSkillId, onSelect, onClose }) {
  return (
    <div className="skill-popover" id="skill-picker" data-testid="skill-picker" role="dialog" aria-label="选择 Skill">
      <div className="skill-popover-header">
        <div>
          <div className="skill-popover-title">选择 Skill</div>
          <div className="skill-popover-subtitle">像插件一样为当前问题附加专业诊断方式。</div>
        </div>
        <button className="skill-close" type="button" aria-label="关闭 Skill 菜单" onClick={onClose}>
          x
        </button>
      </div>
      <div className="skill-list">
        {skills.map((skill) => (
          <button
            className={`skill-option ${selectedSkillId === skill.id ? "active" : ""}`}
            type="button"
            key={skill.id}
            onClick={() => onSelect(skill.id)}
          >
            <span className="skill-option-top">
              <span className="skill-name">{skill.name}</span>
              <span className="skill-category">{skill.category}</span>
            </span>
            <span className="skill-desc">{skill.description}</span>
            <span className="skill-hint">{skill.promptHint}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ActiveSkillBar({ skill, onClear }) {
  if (!skill) return null;
  return (
    <div className="active-skill-bar" data-testid="active-skill-bar">
      <div>
        <span className="active-skill-label">已启用 Skill</span>
        <span className="active-skill-name">{skill.name}</span>
      </div>
      <button type="button" onClick={onClear}>移除</button>
    </div>
  );
}

const starterPrompts = [
  "诊断 600519，现在只适合观察还是可以进入候选？",
  "如果我已经持有宁德时代，哪些证据会触发减仓？",
  "我想验证低估值 + 资金流策略，当前系统能先检查什么？",
];

function ConversationWorkspace({ diagnosis, onOpenVisual }) {
  const turns = diagnosis.turns || [];
  const hasTurns = turns.length > 0;
  const lastStep = [...(diagnosis.taskSteps || [])].reverse().find((step) => step.status === "done") || diagnosis.taskSteps?.[0];

  return (
    <section className="conversation-workspace" data-testid="conversation-workspace">
      <div className="conversation-main-header">
        <div>
          <div className="workspace-kicker">当前对话流</div>
          <div className="workspace-title">用对话推进诊断和策略验证</div>
          <div className="workspace-subtitle">中间区域优先保留给用户、模型和系统任务沟通；图形化结果收纳到独立视图。</div>
        </div>
        <button className="secondary-button" data-testid="visualization-entry" type="button" onClick={onOpenVisual}>
          图形化展示
        </button>
      </div>
      <div className="conversation-flow" data-testid="conversation-history">
        <div className="flow-label">连续追问</div>
        {hasTurns ? (
          turns.slice(-8).map((turn, index) => (
            <div className={`turn ${turn.role}`} key={`${turn.role}-${index}-${turn.content}`}>
              <div className="turn-role">{turn.role === "user" ? "你" : "AStock Lens"}</div>
              <div className="turn-content">{turn.content}</div>
            </div>
          ))
        ) : (
          <div className="empty-conversation">
            <div>
              <div className="empty-title">先告诉系统你关心的对象或想法</div>
              <div className="empty-copy">可以是一只股票、一个持仓问题，或一个需要验证的策略假设。</div>
            </div>
            <div className="prompt-examples" aria-label="可输入示例">
              {starterPrompts.map((item) => (
                <div className="prompt-example" key={item}>{item}</div>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="system-task-strip" aria-label="系统任务状态">
        <div>
          <div className="strip-label">系统当前状态</div>
          <div className="strip-title">{diagnosis.thread.status}</div>
        </div>
        <div>
          <div className="strip-label">当前对象</div>
          <div className="strip-title">{diagnosis.thread.code ? `${diagnosis.thread.name} ${diagnosis.thread.code}` : "等待输入"}</div>
        </div>
        <div>
          <div className="strip-label">最近完成</div>
          <div className="strip-title">{lastStep?.name || "等待任务"}</div>
        </div>
      </div>
    </section>
  );
}

function EvidencePanel({ diagnosis, runtime, onOpenVisual }) {
  const activeSkills = diagnosis.activeSkills || [];
  return (
    <aside className="evidence" data-testid="evidence-panel" aria-label="证据与 Agent 上下文">
      <div className="panel-section">
        <div className="panel-heading">
          <span>上下文</span>
          <span className={`badge ${statusClass(diagnosis.decision.verdict)}`}>当前线程</span>
        </div>
        <div className="context-object">
          <div className="context-name">{diagnosis.thread.code ? `${diagnosis.thread.name} ${diagnosis.thread.code}` : "未选择对象"}</div>
          <div className="context-desc">{diagnosis.decision.note}</div>
        </div>
        <button className="panel-action" type="button" onClick={onOpenVisual}>
          打开图形化视图
        </button>
      </div>
      <div className="panel-section">
        <div className="panel-heading">Skill</div>
        {activeSkills.length ? (
          <div className="active-skill-list">
            {activeSkills.map((skill) => (
              <div className="active-skill-card" key={skill.id}>
                <div className="active-skill-title">{skill.name}</div>
                <div className="active-skill-desc">{skill.description}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="panel-copy">点击输入框左侧加号，可以为当前问题启用单股诊断、估值快照、持仓风险检查或策略预检。</p>
        )}
      </div>
      <div className="panel-section">
        <div className="panel-heading">证据来源</div>
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
        <div className="panel-heading">可继续追问</div>
        <ul className="question-list">
          <li>这只股票最大的下行风险是什么？</li>
          <li>如果我已经持有，什么情况需要降低仓位？</li>
          <li>我这个策略想法，系统现在能验证到哪一步？</li>
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

function Workspace({
  diagnosis,
  prompt,
  setPrompt,
  onSubmit,
  loading,
  inputRef,
  runtime,
  viewMode,
  setViewMode,
  skills,
  selectedSkill,
  selectedSkillId,
  onSelectSkill,
  onClearSkill,
}) {
  const [skillMenuOpen, setSkillMenuOpen] = useState(false);
  const readServiceOffline = runtime?.readService?.available === false;
  const runtimeLabel = runtime?.readService
    ? readServiceOffline
      ? "Read service offline"
      : "Local API mode"
    : "Checking local API";

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
        <div className="top-actions">
          <div className="view-switch" aria-label="工作区视图">
            <button
              className={viewMode === "conversation" ? "active" : ""}
              type="button"
              aria-pressed={viewMode === "conversation"}
              onClick={() => setViewMode("conversation")}
            >
              对话
            </button>
            <button
              className={viewMode === "visualization" ? "active" : ""}
              type="button"
              aria-pressed={viewMode === "visualization"}
              onClick={() => setViewMode("visualization")}
            >
              图形化展示
            </button>
          </div>
          <div className="top-meta">
            <span className={`status-dot ${readServiceOffline ? "offline" : ""}`} aria-hidden="true"></span>
            <span>{runtimeLabel}</span>
          </div>
        </div>
      </header>
      <section className="workspace-scroll" aria-label="当前诊断任务">
        {viewMode === "visualization" ? (
          <VisualizationWorkspace
            diagnosis={diagnosis}
            runtime={runtime}
            onBackToConversation={() => setViewMode("conversation")}
          />
        ) : (
          <div className="conversation-layout">
            <ConversationWorkspace diagnosis={diagnosis} onOpenVisual={() => setViewMode("visualization")} />
            <div className="summary-grid">
              <DecisionCard diagnosis={diagnosis} />
              <TaskTimeline steps={diagnosis.taskSteps} />
            </div>
          </div>
        )}
      </section>
      <footer className="composer-shell" data-testid="bottom-composer">
        <div className="composer-stack">
          {skillMenuOpen && (
            <SkillPicker
              skills={skills}
              selectedSkillId={selectedSkillId}
              onSelect={(skillId) => {
                onSelectSkill(skillId);
                setSkillMenuOpen(false);
                inputRef.current?.focus();
              }}
              onClose={() => setSkillMenuOpen(false)}
            />
          )}
          <ActiveSkillBar
            skill={selectedSkill}
            onClear={() => {
              onClearSkill();
              setSkillMenuOpen(false);
              inputRef.current?.focus();
            }}
          />
          <form className="composer" onSubmit={onSubmit}>
            <button
              className={`icon-button ${selectedSkill ? "active" : ""}`}
              data-testid="composer-skill-button"
              type="button"
              title="添加 Skill"
              aria-label="添加 Skill"
              aria-expanded={skillMenuOpen}
              aria-controls="skill-picker"
              onClick={() => setSkillMenuOpen((open) => !open)}
            >
              +
            </button>
            <input
              ref={inputRef}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder={selectedSkill ? `${selectedSkill.name}: ${selectedSkill.promptHint}` : "问一只股票，或继续推进当前诊断…"}
              aria-label="诊断输入"
              disabled={loading}
            />
            <button className="send-button" type="submit" disabled={loading}>
              {loading ? "诊断中" : "发送"}
            </button>
          </form>
        </div>
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
  const [viewMode, setViewMode] = useState("conversation");
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const inputRef = useRef(null);

  const activeDiagnosis = diagnoses.find((item) => item.thread.id === activeId) || initialDiagnosis;
  const selectedSkill = skillById.get(selectedSkillId) || null;

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
            selectedSkillId: selectedSkill?.id || "",
          }
        : {
            selectedSkillId: selectedSkill?.id || "",
          };
      const result = window.astock?.runDiagnosis
        ? await window.astock.runDiagnosis({ prompt: text, context })
        : browserPreviewDiagnosis(text, selectedSkill);
      setDiagnoses((prev) => [result, ...prev.filter((item) => item.thread.id !== result.thread.id)]);
      setThreads((prev) => [
        {
          ...result.thread,
          updated: "刚刚",
        },
        ...prev.filter((thread) => thread.id !== result.thread.id),
      ]);
      setActiveId(result.thread.id);
      setViewMode("conversation");
      setSelectedSkillId(result.activeSkills?.[0]?.id || selectedSkill?.id || "");
      setPrompt("");
    } catch (error) {
      const result = unavailableDiagnosis(text, error?.message || String(error), selectedSkill);
      setDiagnoses((prev) => [result, ...prev.filter((item) => item.thread.id !== result.thread.id)]);
      setThreads((prev) => [
        {
          ...result.thread,
          updated: "刚刚",
        },
        ...prev.filter((thread) => thread.id !== result.thread.id),
      ]);
      setActiveId(result.thread.id);
      setViewMode("conversation");
      setSelectedSkillId(result.activeSkills?.[0]?.id || selectedSkill?.id || "");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-frame">
      <ThreadSidebar
        threads={threads}
        activeId={activeId}
        onSelect={(threadId) => {
          setActiveId(threadId);
          setViewMode("conversation");
          const nextDiagnosis = diagnoses.find((item) => item.thread.id === threadId);
          setSelectedSkillId(nextDiagnosis?.activeSkills?.[0]?.id || "");
        }}
        onNew={() => {
          setActiveId(initialDiagnosis.thread.id);
          setViewMode("conversation");
          setSelectedSkillId("");
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
        viewMode={viewMode}
        setViewMode={setViewMode}
        skills={skillDefinitions}
        selectedSkill={selectedSkill}
        selectedSkillId={selectedSkillId}
        onSelectSkill={setSelectedSkillId}
        onClearSkill={() => setSelectedSkillId("")}
      />
      <EvidencePanel diagnosis={activeDiagnosis} runtime={runtime} onOpenVisual={() => setViewMode("visualization")} />
    </div>
  );
}
