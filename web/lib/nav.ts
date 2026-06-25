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
    title: "控制台与风险",
    items: [
      { href: "/dashboard", label: "今日操作台", desc: "今日是否可交易、建议动作与就绪度门禁", ready: true, icon: "dashboard", modes: ["ops", "rd"] },
      { href: "/portfolio-risk", label: "組合風控", desc: "小盘、流动性与集中度等主要风险暴露", ready: true, icon: "portfolio", modes: ["ops", "rd"] },
      { href: "/signal-audit", label: "信號審計", desc: "信信号追溯与 Top-25 选股流水线审计", ready: true, icon: "signals", modes: ["ops", "rd"] },
    ],
  },
  {
    title: "研发与台账",
    items: [
      { href: "/strategy-registry", label: "策略台帳", desc: "母策略台账管理、生命周期与九门禁状态", ready: true, icon: "candidates", modes: ["ops", "rd"] },
      { href: "/factor-research", label: "因子研究", desc: "因子库规模、IC 时序、分组单调性与相关性", ready: true, icon: "factors", modes: ["ops", "rd"] },
      { href: "/backtest-lab", label: "回測實驗", desc: "历史回测表现、样本外塌陷与真实口径偏差", ready: true, icon: "backtest", modes: ["ops", "rd"] },
    ],
  },
  {
    title: "数据与系统",
    items: [
      { href: "/data-health", label: "數據健康", desc: "最新交易日对齐、PIT 通过率与数据管道状态", ready: true, icon: "data", modes: ["ops", "rd"] },
      { href: "/system-governance", label: "系統治理", desc: "部署状态、CI 守卫通过率与架构依赖拓扑", ready: true, icon: "settings", modes: ["ops", "rd"] },
    ],
  },
  {
    title: "配置",
    items: [
      { href: "/settings", label: "系統設置", desc: "成本、风控阈值与大模型接口密钥配置", ready: true, icon: "settings", modes: ["ops", "rd"] },
    ],
  },
];

export const NAV = NAV_GROUPS.flatMap((group) => group.items);
