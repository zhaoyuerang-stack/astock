(function () {
  const data = window.ASTCOK_DATA;

  const pct = (value, digits = 1) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "";
    const sign = value > 0 ? "+" : "";
    return `${sign}${(value * 100).toFixed(digits)}%`;
  };

  const num = (value, digits = 2) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "";
    return Number(value).toFixed(digits);
  };

  const badgeClass = (status) => {
    if (["done", "ok", "在册", "loaded"].includes(status)) return "badge ok";
    if (["active", "partial"].includes(status)) return "badge warn";
    if (["failed", "未验收", false].includes(status)) return "badge danger";
    return "badge neutral";
  };

  const setText = (id, text) => {
    const node = document.getElementById(id);
    if (node) node.textContent = text;
  };

  const metricCard = (label, value, sub, tone = "") => `
    <article class="metric ${tone}">
      <span class="metric-label">${label}</span>
      <strong>${value}</strong>
      <small>${sub || ""}</small>
    </article>`;

  const progress = (value, max, tone = "") => {
    const width = Math.max(0, Math.min(100, (value / max) * 100));
    return `<span class="bar ${tone}"><span style="width:${width}%"></span></span>`;
  };

  const readinessTone = (readiness) => readiness.allowed ? "ok" : "danger";

  const reasonList = (items) => {
    if (!items || !items.length) return `<span class="muted">无</span>`;
    return `<div class="reason-list">${items.map(item => `<span>${item}</span>`).join("")}</div>`;
  };

  const equityBars = (curve) => {
    const max = Math.max(...curve.map(point => point.strategy), ...curve.map(point => point.benchmark));
    return `
      <div class="equity-chart">
        ${curve.map(point => `
          <div class="equity-year">
            <div class="equity-bars">
              <span class="strategy" style="height:${Math.max(8, point.strategy / max * 100)}%"></span>
              <span class="benchmark" style="height:${Math.max(8, point.benchmark / max * 100)}%"></span>
            </div>
            <small>${point.date}</small>
          </div>
        `).join("")}
      </div>`;
  };

  function renderShell() {
    setText("asOf", `Snapshot ${data.meta.asOf}`);
    setText("systemName", data.meta.systemName);
    const page = document.body.dataset.page;
    document.querySelectorAll(".nav-link").forEach((link) => {
      if (link.dataset.page === page) link.classList.add("active");
    });
  }

  function renderDashboard() {
    const root = document.getElementById("dashboard");
    if (!root) return;
    const fresh = data.dataFreshness.dataFresh;
    const live = data.liveTrading;
    const readiness = data.productionReadiness;
    root.innerHTML = `
      <section class="grid metrics-grid">
        ${metricCard("今日建议", data.signal.action, data.signal.rebalanceReason, data.signal.inMarket ? "ok" : "warn")}
        ${metricCard("当前仓位", `${pct(live.investedRatio, 0)} 股票`, `${pct(live.cashRatio, 0)} 现金`, data.signal.inMarket ? "ok" : "warn")}
        ${metricCard("策略年化", pct(live.performance.strategyAnnual), `回撤 ${pct(live.performance.strategyMaxdd)}`, "ok")}
        ${metricCard("生产 Gate", readiness.allowed ? "Allowed" : "Blocked", `${readiness.dataDate} / ${readiness.expectedTradeDate}`, readinessTone(readiness))}
      </section>

      <section class="panel live-summary">
        <div>
          <div class="section-title">
            <h2>实盘信号</h2>
            <span class="${data.signal.inMarket ? "badge ok" : "badge warn"}">${data.signal.timing}</span>
          </div>
          <dl class="kv">
            <div><dt>信号日期</dt><dd>${data.signal.date}</dd></div>
            <div><dt>策略版本</dt><dd>${data.signal.strategyVersion}</dd></div>
            <div><dt>小盘指数</dt><dd>${pct(data.signal.smallIndexVsMa16)} vs MA16</dd></div>
            <div><dt>下一步</dt><dd>${live.nextDecision}</dd></div>
          </dl>
        </div>
        <div>
          <div class="section-title">
            <h2>交易指令</h2>
            <span class="badge neutral">${live.accountMode}</span>
          </div>
          <div class="trade-list">
            ${live.tradePlan.map(plan => `
              <article class="trade-card ${plan.action === "买入" ? "buy" : "sell"}">
                <strong>${plan.action}</strong>
                <div><span>${plan.code}</span><b>${plan.name}</b></div>
                <small>${plan.reason}</small>
              </article>
            `).join("")}
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>生产发布 Gate</h2>
          <span class="${readiness.allowed ? "badge ok" : "badge danger"}">${readiness.allowed ? "正式信号可发布" : "只生成草稿"}</span>
        </div>
        <div class="readiness-grid">
          <dl class="kv">
            <div><dt>数据日</dt><dd>${readiness.dataDate || "未知"}</dd></div>
            <div><dt>应有交易日</dt><dd>${readiness.expectedTradeDate || "未知"}</dd></div>
            <div><dt>治理状态</dt><dd>${readiness.governanceStatus}</dd></div>
            <div><dt>衰减状态</dt><dd>${readiness.decayStatus}</dd></div>
          </dl>
          <div>
            <h3>阻断原因</h3>
            ${reasonList(readiness.blockingReasons)}
            <h3>Warning</h3>
            ${reasonList(readiness.warnings)}
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>策略收益</h2>
          <span class="badge ok">small-cap-size / v2.0</span>
        </div>
        <div class="performance-grid">
          <div>
            ${equityBars(live.performance.equityCurve)}
            <div class="legend"><span class="strategy"></span>策略净值 <span class="benchmark"></span>基准净值</div>
          </div>
          <div class="mini-metrics">
            <span>策略年化 <strong>${pct(live.performance.strategyAnnual)}</strong></span>
            <span>最大回撤 <strong>${pct(live.performance.strategyMaxdd)}</strong></span>
            <span>换手/年 <strong>${num(live.performance.turnoverPa, 1)}x</strong></span>
            <span>成本拖累 <strong>${pct(live.performance.costDragPa)}</strong></span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>候选股票池预览</h2>
          <span class="badge warn">当前空仓，不代表买入</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>代码</th><th>名称</th><th>评分</th><th>因子来源</th><th>状态</th></tr></thead>
            <tbody>
              ${live.watchlist.map(row => `
                <tr>
                  <td>${row.code}</td>
                  <td><strong>${row.name}</strong></td>
                  <td>${row.score}</td>
                  <td>${row.factor}</td>
                  <td>${row.status}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </section>`;
  }

  function renderFactory() {
    const root = document.getElementById("factory");
    if (!root) return;
    root.innerHTML = `
      <section class="grid metrics-grid">
        ${metricCard("评估候选", String(data.factory.summary.evaluated), "1.12 四岛合计", "neutral")}
        ${metricCard("Review", String(data.factory.summary.reviewCandidates), "进入审计", "warn")}
        ${metricCard("孵化池", String(data.factory.summary.incubate), "弱候选", "warn")}
        ${metricCard("预审通过", String(data.factory.summary.registryPrecheck), "candidate_batch 为空", "danger")}
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>岛屿搜索</h2>
          <span class="badge danger">acceptance = false</span>
        </div>
        <div class="island-grid">
          ${data.factory.islands.map(island => `
            <article class="island-card">
              <strong>${island.name}</strong>
              <small>${island.niche}</small>
              <div class="island-bars">
                <label>review ${island.review}</label>${progress(island.review, 10, "warn")}
                <label>precheck ${island.precheck}</label>${progress(island.precheck, 2, "danger")}
              </div>
            </article>
          `).join("")}
        </div>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>Top 孵化候选</h2>
          <span class="badge warn">组合分散件定位</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>#</th><th>候选</th><th>年化</th><th>回撤</th><th>样本外</th><th>压力回撤</th><th>成本上浮</th><th>相关</th><th>判断</th></tr>
            </thead>
            <tbody>
              ${data.factory.topIncubation.map(row => `
                <tr>
                  <td>${row.rank}</td>
                  <td><strong>${row.desc}</strong><small>${row.config}</small></td>
                  <td>${pct(row.annual)}</td>
                  <td class="${row.maxdd < -0.2 ? "negative" : ""}">${pct(row.maxdd)}</td>
                  <td>${pct(row.oosAnnual)}</td>
                  <td class="${row.pressureMaxdd < -0.35 ? "negative" : ""}">${pct(row.pressureMaxdd)}</td>
                  <td>${pct(row.costUpAnnual)}</td>
                  <td>${num(row.corr)}</td>
                  <td>${row.reason}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>失败原因分布</h2><span class="badge neutral">孵化池 23</span></div>
        <div class="bucket-list">
          ${data.factory.failureBuckets.map(bucket => `
            <div class="bucket">
              <span>${bucket.label}</span>
              ${progress(bucket.count, 23, bucket.label.includes("回撤") ? "danger" : "warn")}
              <strong>${bucket.count}</strong>
            </div>
          `).join("")}
        </div>
      </section>`;
  }

  function renderOps() {
    const root = document.getElementById("ops");
    if (!root) return;
    const report = data.ops.dailyReport;
    const readiness = data.productionReadiness;
    root.innerHTML = `
      <section class="grid metrics-grid">
        ${metricCard("最近日报", report.runDate, `status=${report.status}`, report.status === "failed" ? "danger" : "ok")}
        ${metricCard("数据新鲜度", report.dataFresh ? "Fresh" : "Stale", `${report.latestAfterUpdate} / ${report.expectedTradeDate}`, report.dataFresh ? "ok" : "danger")}
        ${metricCard("信号生成", report.signalGenerated ? "Yes" : "No", report.signalReason, report.signalGenerated ? "ok" : "warn")}
        ${metricCard("生产 Gate", readiness.allowed ? "Allowed" : "Blocked", readiness.blockingReasons.join(", ") || "no blockers", readinessTone(readiness))}
      </section>

      <section class="panel">
        <div class="section-title"><h2>launchd 任务</h2><span class="badge ok">loaded</span></div>
        <div class="job-list">
          ${data.ops.jobs.map(job => `
            <article class="job-card">
              <div><strong>${job.name}</strong><span class="${badgeClass(job.status)}">${job.status}</span></div>
              <p>${job.cadence}</p>
              <small>${job.gate}</small>
              <code>${job.command}</code>
            </article>
          `).join("")}
        </div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>只读操作</h2><span class="badge neutral">复制到终端</span></div>
        <div class="command-list">
          ${data.ops.commands.map(command => `<code>${command}</code>`).join("")}
        </div>
      </section>`;
  }

  function renderRegistry() {
    const root = document.getElementById("registry");
    if (!root) return;
    const active = data.registry.active[0];
    root.innerHTML = `
      <section class="grid metrics-grid">
        ${metricCard("Active", "1", "small-cap-size", "ok")}
        ${metricCard("Candidate", String(data.registry.candidateBatchCount), "candidate_batch 为空", "danger")}
        ${metricCard("Incubate", String(data.factory.summary.incubate), "不入册", "warn")}
        ${metricCard("Retired", String(data.registry.retiredCount), "暂未启用退役监控", "neutral")}
      </section>

      <section class="panel">
        <div class="section-title"><h2>在册母策略</h2><span class="badge ok">${active.status}</span></div>
        <div class="registry-card">
          <div>
            <h3>${active.family} / ${active.version}</h3>
            <p>${active.name}</p>
            <small>${active.notes}</small>
          </div>
          <div class="mini-metrics">
            <span>年化 <strong>${pct(active.annual)}</strong></span>
            <span>回撤 <strong>${pct(active.maxdd)}</strong></span>
            <span>Sharpe <strong>${num(active.sharpe)}</strong></span>
            <span>Calmar <strong>${num(active.calmar)}</strong></span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>版本参考</h2><span class="badge neutral">不作为主线口径</span></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>版本</th><th>年化</th><th>回撤</th><th>备注</th></tr></thead>
            <tbody>
              ${data.registry.reference.map(row => `
                <tr><td>${row.version}</td><td>${pct(row.annual)}</td><td>${pct(row.maxdd)}</td><td>${row.note}</td></tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>孵化池失败原因</h2><span class="badge warn">继续证伪</span></div>
        <div class="bucket-list">
          ${data.factory.failureBuckets.map(bucket => `
            <div class="bucket">
              <span>${bucket.label}</span>
              ${progress(bucket.count, 23, bucket.label.includes("回撤") ? "danger" : "warn")}
              <strong>${bucket.count}</strong>
            </div>
          `).join("")}
        </div>
      </section>`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    renderShell();
    renderDashboard();
    renderFactory();
    renderOps();
    renderRegistry();
  });
})();
