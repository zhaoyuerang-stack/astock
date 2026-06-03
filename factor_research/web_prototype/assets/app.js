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
    root.innerHTML = `
      <section class="grid metrics-grid">
        ${metricCard("数据最新交易日", data.dataFreshness.latestTradeDate, `应有 ${data.dataFreshness.expectedTradeDate}`, fresh ? "ok" : "danger")}
        ${metricCard("当前择时", data.signal.timing, `${pct(data.signal.smallIndexVsMa16)} vs MA16`, data.signal.inMarket ? "ok" : "warn")}
        ${metricCard("在册策略", "1", "small-cap-size / v2.0", "ok")}
        ${metricCard("候选母策略批", String(data.factory.summary.paretoCandidates), "registry_precheck = 0", "danger")}
      </section>

      <section class="panel split">
        <div>
          <div class="section-title">
            <h2>生产状态</h2>
            <span class="${fresh ? "badge ok" : "badge danger"}">${fresh ? "Fresh" : "Stale"}</span>
          </div>
          <dl class="kv">
            <div><dt>最新信号</dt><dd>${data.signal.date}</dd></div>
            <div><dt>操作</dt><dd>${data.signal.action}</dd></div>
            <div><dt>持仓数</dt><dd>${data.signal.holdings.length}</dd></div>
            <div><dt>数据检查</dt><dd>${data.dataFreshness.sampleQualityOk ? "抽样通过" : "抽样异常"}</dd></div>
          </dl>
        </div>
        <div>
          <div class="section-title">
            <h2>目标差距</h2>
            <span class="badge warn">未达项目目标</span>
          </div>
          <div class="target-row">
            <span>年化 ${pct(data.registry.active[0].annual)}</span>
            ${progress(data.registry.active[0].annual, data.meta.targetAnnual, "ok")}
            <span>目标 ${pct(data.meta.targetAnnual)}</span>
          </div>
          <div class="target-row">
            <span>回撤 ${pct(data.registry.active[0].maxdd)}</span>
            ${progress(Math.abs(data.registry.active[0].maxdd), Math.abs(data.meta.targetMaxdd), "danger")}
            <span>目标 ${pct(data.meta.targetMaxdd)}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>系统层状态</h2>
          <span class="badge neutral">六层架构</span>
        </div>
        <div class="timeline">
          ${data.roadmap.map(item => `
            <div class="timeline-item ${item.status}">
              <span></span>
              <strong>${item.layer}</strong>
              <p>${item.note}</p>
            </div>
          `).join("")}
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
    root.innerHTML = `
      <section class="grid metrics-grid">
        ${metricCard("最近日报", report.runDate, `status=${report.status}`, report.status === "failed" ? "danger" : "ok")}
        ${metricCard("数据新鲜度", report.dataFresh ? "Fresh" : "Stale", `${report.latestAfterUpdate} / ${report.expectedTradeDate}`, report.dataFresh ? "ok" : "danger")}
        ${metricCard("信号生成", report.signalGenerated ? "Yes" : "No", report.signalReason, report.signalGenerated ? "ok" : "warn")}
        ${metricCard("中国时间 Gate", report.chinaGate, "launchd 使用本机时区", "neutral")}
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
