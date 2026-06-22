// 左侧导航配置分组(WEB_DESIGN §2.3 / §0.A)
// 设计原则:导航 = 信息排序系统。分组沿研究→执行生命周期排序,
// 让用户从左栏就读懂"系统在干什么、谁流向谁"。
//   - rd(研发实验室):发现并验证 alpha,顺序对齐 §0.A 生命周期
//     数据素材 → 草案/候选(L0-L3+复核) → 回测验证 → 正式登记台账 → 持续监控
//   - ops(行动桌面):用已登记策略产出信号并执行,顺序对齐执行漏斗
//     信号 → 选股 → 执行前检查 → 签发 → 持仓 → 风控
// desc 为每个页面"我是干什么的"一句话(WEB_DESIGN §2.3 要求的 hover 说明)。
// ready=true 为 Phase 1 已接真 API 的页面。

export interface NavItem {
  href: string;
  label: string;
  desc: string;
  ready: boolean;
  icon: string;
  modes: ("ops" | "rd")[];
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "入口",
    items: [
      { href: "/overview", label: "今日总览", desc: "今日持仓、信号与待办的统一入口", ready: true, icon: "dashboard", modes: ["ops", "rd"] },
    ],
  },
  {
    // rd 阶段一:从数据素材到候选验证
    title: "发现与验证",
    items: [
      { href: "/data", label: "数据中心", desc: "数据完整性与质量审计,研究的素材源头", ready: true, icon: "data", modes: ["rd"] },
      { href: "/experiments", label: "研究实验室", desc: "登记前的草案与候选队列(L0–L3 初筛 → 人工复核)", ready: true, icon: "experiments", modes: ["rd"] },
      { href: "/backtest", label: "策略回测", desc: "候选策略的样本外与压力验证", ready: true, icon: "backtest", modes: ["rd"] },
    ],
  },
  {
    // rd 阶段二:正式登记台账与持续监控
    title: "登记与监控",
    items: [
      { href: "/factors", label: "因子研究", desc: "已登记策略台账、家族血缘与 Nine-Gate 审计", ready: true, icon: "factors", modes: ["rd"] },
      { href: "/governance", label: "模型风险治理", desc: "已登记模型的持续监控与失效治理", ready: true, icon: "settings", modes: ["rd"] },
    ],
  },
  {
    // ops 阶段一:择时信号到选股候选
    title: "信号与选股",
    items: [
      { href: "/signals", label: "策略信号", desc: "择时指标核算、阈值审计与调仓判定", ready: true, icon: "signals", modes: ["ops"] },
      { href: "/candidates", label: "股票候选", desc: "因子选股候选池与泡沫过滤", ready: true, icon: "candidates", modes: ["ops"] },
    ],
  },
  {
    // ops 阶段二:执行前闸门与委托签发
    title: "准备与签发",
    items: [
      { href: "/trade-readiness", label: "交易准备度", desc: "执行前的条件闸门检查", ready: true, icon: "plans", modes: ["ops"] },
      { href: "/trade-plans", label: "交易计划", desc: "执行委托签发与滑点审计", ready: true, icon: "plans", modes: ["ops"] },
    ],
  },
  {
    // ops 阶段三:持仓结果与风控监控
    title: "持仓与风控",
    items: [
      { href: "/portfolio", label: "组合管理", desc: "当前组合 vs 目标组合与暴露分布", ready: true, icon: "portfolio", modes: ["ops"] },
      { href: "/risk", label: "风险控制", desc: "风险敞口、熔断规则与风控建议", ready: true, icon: "risk", modes: ["ops"] },
    ],
  },
  {
    title: "通用",
    items: [
      { href: "/agent", label: "AI助手", desc: "研究对话与报告生成主工作台", ready: true, icon: "agent", modes: ["ops", "rd"] },
      { href: "/settings", label: "系统设置", desc: "数据源、成本、风控规则与模型配置", ready: true, icon: "settings", modes: ["ops", "rd"] },
    ],
  },
];

// 兼容原扁平导出,避免其他模块引用报错
export const NAV = NAV_GROUPS.flatMap((group) => group.items);
