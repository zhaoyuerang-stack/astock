window.ASTCOK_DATA = {
  meta: {
    asOf: "2026-06-03",
    systemName: "A股策略工厂控制台",
    stage: "阶段 1 多目标工厂化",
    stageStatus: "未验收",
    targetAnnual: 0.35,
    targetMaxdd: -0.15
  },
  dataFreshness: {
    expectedTradeDate: "2026-06-03",
    latestTradeDate: "2026-06-01",
    expectedSource: "weekday_heuristic",
    dataFresh: false,
    sampleQualityOk: true,
    sampleChecked: ["600519", "000001", "300750", "600036", "601398"]
  },
  productionReadiness: {
    allowed: false,
    blockingReasons: ["data_stale", "governance:dsr_pending"],
    warnings: ["decay:unknown"],
    dataDate: "2026-06-01",
    expectedTradeDate: "2026-06-03",
    governanceStatus: "dsr_pending",
    decayStatus: "unknown",
    paperStatus: "ok",
    tradingDayStatus: "trading_day"
  },
  signal: {
    date: "2026-06-01",
    timing: "空仓",
    inMarket: false,
    smallIndexVsMa16: -0.0315,
    action: "空仓观望",
    rebalanceReason: "当前空仓且择时为空，继续观望",
    holdings: [],
    topN: 25,
    leverage: 1.25,
    strategyVersion: "v2.0"
  },
  liveTrading: {
    accountMode: "模拟实盘",
    cashRatio: 1.0,
    investedRatio: 0.0,
    nextDecision: "等待数据补齐后刷新信号",
    tradePlan: [
      { action: "买入", code: "无", name: "当前择时为空", weight: 0, reason: "小盘指数低于 MA16，系统保持空仓" },
      { action: "卖出", code: "无", name: "无持仓", weight: 0, reason: "当前没有需要卖出的持仓" }
    ],
    holdings: [],
    watchlist: [
      { code: "300750", name: "宁德时代", score: 82, factor: "流动性/小盘候选池样例", status: "等待择时转多" },
      { code: "600519", name: "贵州茅台", score: 77, factor: "质量锚点样例", status: "仅展示，不代表买入" },
      { code: "000001", name: "平安银行", score: 73, factor: "低估值候选样例", status: "仅展示，不代表买入" },
      { code: "600036", name: "招商银行", score: 71, factor: "财务质量候选样例", status: "仅展示，不代表买入" }
    ],
    performance: {
      strategyAnnual: 0.2125,
      strategyMaxdd: -0.1621,
      benchmarkAnnual: 0.08,
      benchmarkMaxdd: -0.24,
      costDragPa: 0.11,
      turnoverPa: 32.1,
      equityCurve: [
        { date: "2018", strategy: 1.00, benchmark: 1.00 },
        { date: "2019", strategy: 1.38, benchmark: 1.16 },
        { date: "2020", strategy: 1.76, benchmark: 1.31 },
        { date: "2021", strategy: 2.08, benchmark: 1.22 },
        { date: "2022", strategy: 2.14, benchmark: 1.03 },
        { date: "2023", strategy: 2.47, benchmark: 1.09 },
        { date: "2024", strategy: 2.86, benchmark: 1.15 },
        { date: "2025", strategy: 4.92, benchmark: 1.34 },
        { date: "2026", strategy: 5.08, benchmark: 1.38 }
      ]
    }
  },
  ops: {
    dailyReport: {
      runDate: "2026-06-03",
      status: "failed",
      dryRun: true,
      chinaGate: "16:30 Asia/Shanghai",
      startedAtChina: "2026-06-03T21:43:09+08:00",
      latestAfterUpdate: "2026-06-01",
      expectedTradeDate: "2026-06-03",
      dataFresh: false,
      signalGenerated: false,
      signalReason: "stale_data",
      logPath: "logs/daily_update/2026-06-03.log"
    },
    jobs: [
      {
        name: "com.astcok.daily-update",
        cadence: "周一到周五本机 00:30 / 01:30",
        gate: "脚本按中国时间 16:30 后执行；当天已成功则跳过",
        status: "loaded",
        command: "launchctl print gui/$UID/com.astcok.daily-update"
      },
      {
        name: "com.astcok.weekly-maintenance",
        cadence: "周日本机 02:30",
        gate: "周线/月线、不复权价、完整质量校验",
        status: "loaded",
        command: "launchctl print gui/$UID/com.astcok.weekly-maintenance"
      }
    ],
    commands: [
      "tail -n 100 logs/daily_update/launchd.out.log",
      "tail -n 100 logs/daily_update/launchd.err.log",
      "launchctl kickstart -k gui/$UID/com.astcok.daily-update"
    ]
  },
  registry: {
    active: [
      {
        family: "small-cap-size",
        version: "v2.0",
        name: "小盘成交额因子",
        annual: 0.2125,
        maxdd: -0.1621,
        sharpe: 1.22,
        calmar: 1.31,
        status: "在册",
        notes: "真实成本基线；年均换手约32.1x，成本拖累约11.0%/年"
      }
    ],
    reference: [
      { version: "v1.0", annual: 0.404, maxdd: -0.146, note: "含幸存者偏差水分，仅参考" },
      { version: "v2.1", annual: 0.2312, maxdd: -0.3394, note: "2010-2026 全历史压力测试" }
    ],
    candidateBatchCount: 0,
    retiredCount: 0
  },
  factory: {
    summary: {
      evaluated: 78,
      reviewCandidates: 24,
      registryPrecheck: 0,
      incubate: 23,
      paretoCandidates: 0,
      acceptanceMet: false,
      conclusion: "fundamental/defensive 当前定位为组合分散件，不是独立母策略。"
    },
    islands: [
      { name: "fundamental_industry_long", niche: "fundamental_industry", evaluated: 19, review: 7, precheck: 0 },
      { name: "fundamental_change_long", niche: "fundamental_change", evaluated: 20, review: 3, precheck: 0 },
      { name: "fundamental_value_pctile_long", niche: "fundamental_value_pctile", evaluated: 19, review: 7, precheck: 0 },
      { name: "fundamental_regime_long", niche: "fundamental_regime", evaluated: 20, review: 7, precheck: 0 }
    ],
    topIncubation: [
      {
        rank: 1,
        island: "fundamental_regime_long",
        niche: "fundamental-industry",
        desc: "fund_eps_yield_pctile + fund_bp_value_ind_rank",
        config: "top40 / reb60 / lev1.25",
        annual: 0.1455,
        maxdd: -0.2318,
        oosAnnual: 0.0848,
        pressureMaxdd: -0.5178,
        costUpAnnual: 0.1024,
        corr: 0.7692,
        reason: "收益接近门槛，但压力回撤失控"
      },
      {
        rank: 2,
        island: "fundamental_value_pctile_long",
        niche: "fundamental-industry",
        desc: "fund_eps_yield_pctile + fund_cfo_ind_rank + fund_bp_value",
        config: "top40 / reb60 / lev1",
        annual: 0.0885,
        maxdd: -0.1633,
        oosAnnual: 0.0590,
        pressureMaxdd: -0.3817,
        costUpAnnual: 0.0543,
        corr: 0.6684,
        reason: "回撤较稳，收益不足"
      },
      {
        rank: 3,
        island: "fundamental_change_long",
        niche: "fundamental-change",
        desc: "fund_profit_growth_delta",
        config: "top40 / reb20 / lev1",
        annual: 0.0938,
        maxdd: -0.1822,
        oosAnnual: 0.1186,
        pressureMaxdd: -0.2845,
        costUpAnnual: 0.0596,
        corr: 0.7537,
        reason: "最干净的弱候选，收益未达标"
      },
      {
        rank: 4,
        island: "fundamental_value_pctile_long",
        niche: "fundamental-industry",
        desc: "fund_bp_value_ind_rank",
        config: "top40 / reb20 / lev1",
        annual: 0.1001,
        maxdd: -0.2001,
        oosAnnual: 0.0619,
        pressureMaxdd: -0.2935,
        costUpAnnual: 0.0617,
        corr: 0.8087,
        reason: "行业价值有效，但相关偏高"
      }
    ],
    failureBuckets: [
      { label: "压力回撤过大", count: 15 },
      { label: "收益不足", count: 6 },
      { label: "相关性偏高", count: 2 }
    ]
  },
  roadmap: [
    { layer: "数据基础设施", status: "done", note: "data_lake 全市场+全历史+含退市股" },
    { layer: "统一回测内核", status: "done", note: "真实成本、融资成本、统一指标" },
    { layer: "策略工厂", status: "active", note: "阶段 1 未验收；候选批为空" },
    { layer: "有效策略管理", status: "partial", note: "两层台账已建，监控待定量化" },
    { layer: "中央调度层", status: "partial", note: "launchd 最小定时更新已落地" },
    { layer: "组合层", status: "todo", note: "有效母策略不足，暂未建" }
  ]
};
