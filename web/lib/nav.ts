// 左侧一级导航(WEB_DESIGN §2.3)。ready=true 为 Phase 1 已接真 API 的页面。
export const NAV = [
  { href: "/overview", label: "总览", ready: true },
  { href: "/data", label: "数据中心", ready: true },
  { href: "/factors", label: "因子研究", ready: true },
  { href: "/backtest", label: "策略回测", ready: true },
  { href: "/portfolio", label: "组合管理", ready: true },
  { href: "/risk", label: "风险控制", ready: true },
  { href: "/experiments", label: "研究实验", ready: false },
  { href: "/agent", label: "AI研究助手", ready: false },
  { href: "/settings", label: "系统设置", ready: false },
] as const;
