function toneForStatus(status) {
  if (status === "done" || status === "谨慎持有") return "ready";
  if (status === "blocked" || status === "错误") return "blocked";
  if (status === "pending" || status === "等待输入") return "pending";
  return "neutral";
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

export default function VisualizationWorkspace({ diagnosis, runtime, onBackToConversation }) {
  const evidence = asList(diagnosis.evidence);
  const risks = asList(diagnosis.risks);
  const steps = asList(diagnosis.taskSteps);
  const chips = asList(diagnosis.sourceChips);
  const hasStock = Boolean(diagnosis.thread?.code);
  const readServiceAvailable = runtime?.readService?.available;
  const readServiceTone = readServiceAvailable === false ? "blocked" : readServiceAvailable === true ? "ready" : "pending";
  const readServiceLabel = readServiceAvailable === false
    ? "read service offline"
    : readServiceAvailable === true
      ? "read service ready"
      : "checking read service";

  return (
    <section className="visualization-workspace" data-testid="visualization-workspace" aria-label="图形化展示">
      <div className="visual-header">
        <div>
          <div className="workspace-kicker">图形化展示</div>
          <div className="workspace-title">{hasStock ? `${diagnosis.thread.name} ${diagnosis.thread.code}` : "等待诊断对象"}</div>
          <div className="workspace-subtitle">这里只展示本地后端已经确认的诊断证据和任务状态，不展示伪造曲线。</div>
        </div>
        <button className="secondary-button" type="button" onClick={onBackToConversation}>
          回到对话
        </button>
      </div>

      <div className="viz-metrics" aria-label="当前诊断指标">
        <div className="viz-metric">
          <div className="metric-label">对象</div>
          <div className="metric-value">{hasStock ? diagnosis.thread.code : "未选择"}</div>
        </div>
        <div className="viz-metric">
          <div className="metric-label">结论</div>
          <div className="metric-value">{diagnosis.decision?.verdict || "等待输入"}</div>
        </div>
        <div className="viz-metric">
          <div className="metric-label">证据</div>
          <div className="metric-value">{evidence.length}</div>
        </div>
        <div className="viz-metric">
          <div className="metric-label">风险</div>
          <div className="metric-value">{risks.length}</div>
        </div>
      </div>

      <div className="viz-grid">
        <div className="viz-panel">
          <div className="viz-panel-header">
            <div>
              <div className="viz-title">诊断链路</div>
              <div className="viz-subtitle">来自 Electron 主进程和本地 Python read service 的任务状态。</div>
            </div>
            <span className={`state-pill ${readServiceTone}`}>
              {readServiceLabel}
            </span>
          </div>
          <div className="pipeline-map">
            {steps.map((step) => (
              <div className="pipeline-step" key={step.name}>
                <div className={`pipeline-node ${toneForStatus(step.status)}`}>{step.status === "done" ? "✓" : step.status === "blocked" ? "!" : "·"}</div>
                <div>
                  <div className="pipeline-name">{step.name}</div>
                  <div className="pipeline-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="viz-panel">
          <div className="viz-panel-header">
            <div>
              <div className="viz-title">证据地图</div>
              <div className="viz-subtitle">按当前诊断返回内容展开，数量和文本都来自后端。</div>
            </div>
          </div>
          <div className="source-map">
            {chips.map((chip) => (
              <span className="source-token" key={chip}>{chip}</span>
            ))}
          </div>
          <ul className="viz-list">
            {evidence.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="viz-grid">
        <div className="viz-panel">
          <div className="viz-panel-header">
            <div>
              <div className="viz-title">风险摘要</div>
              <div className="viz-subtitle">当前只做证据归纳，不输出买卖指令。</div>
            </div>
          </div>
          <ul className="viz-list">
            {risks.slice(0, 5).map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </div>

        <div className="viz-panel boundary-panel">
          <div className="viz-panel-header">
            <div>
              <div className="viz-title">策略 Shadow 模拟盘</div>
              <div className="viz-subtitle">能力边界</div>
            </div>
            <span className="state-pill pending">预留</span>
          </div>
          <p>
            用户策略想法可以先进入对话澄清和证据拆解。后端尚未暴露用户策略的 Shadow 模拟盘 read model，
            当前桌面端不会生成伪收益曲线；接入后再展示组合净值、回撤、换手、持仓解释和失败样本。
          </p>
        </div>
      </div>
    </section>
  );
}
