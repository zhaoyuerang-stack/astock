// 左侧导航配置分组(WEB_DESIGN §2.3)
// ready=true 为 Phase 1 已接真 API 的页面。

export interface NavItem {
  href: string;
  label: string;
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
    title: "信号与执行",
    items: [
      { href: "/overview", label: "今日总览", ready: true, icon: "dashboard", modes: ["ops", "rd"] },
      { href: "/trade-readiness", label: "交易准备度", ready: true, icon: "plans", modes: ["ops"] },
      { href: "/signals", label: "策略信号", ready: true, icon: "signals", modes: ["ops"] },
      { href: "/candidates", label: "股票候选", ready: true, icon: "candidates", modes: ["ops"] },
      { href: "/trade-plans", label: "交易计划", ready: true, icon: "plans", modes: ["ops"] },
    ],
  },
  {
    title: "策略实验室",
    items: [
      { href: "/data", label: "数据中心", ready: true, icon: "data", modes: ["rd"] },
      { href: "/factors", label: "因子研究", ready: true, icon: "factors", modes: ["rd"] },
      { href: "/backtest", label: "策略回测", ready: true, icon: "backtest", modes: ["rd"] },
      { href: "/experiments", label: "研究实验", ready: true, icon: "experiments", modes: ["rd"] },
    ],
  },
  {
    title: "组合与风控",
    items: [
      { href: "/portfolio", label: "组合管理", ready: true, icon: "portfolio", modes: ["ops"] },
      { href: "/risk", label: "风险控制", ready: true, icon: "risk", modes: ["ops"] },
      { href: "/governance", label: "模型风险治理", ready: true, icon: "settings", modes: ["rd"] },
    ],
  },
  {
    title: "系统与智能",
    items: [
      { href: "/agent", label: "AI助手", ready: true, icon: "agent", modes: ["ops", "rd"] },
      { href: "/settings", label: "系统设置", ready: true, icon: "settings", modes: ["ops", "rd"] },
    ],
  },
];

// 兼容原扁平导出,避免其他模块引用报错
export const NAV = NAV_GROUPS.flatMap((group) => group.items);
