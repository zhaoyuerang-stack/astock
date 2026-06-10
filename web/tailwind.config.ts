import type { Config } from "tailwindcss";

// 配色对齐 WEB_DESIGN §3.1
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#071B3A",      // 左侧导航背景
        brand: "#2563EB",     // 主按钮 / 当前选中
        line: "#3B82F6",      // 图表主线 / 链接
        teal: "#14B8A6",      // 正向 / 健康
        ok: "#22C55E",        // 正常 / 成功
        warn: "#F59E0B",      // 中风险 / 注意
        danger: "#EF4444",    // 高风险 / 亏损 / 超限
        ink: "#0F172A",       // 主文本
        subink: "#64748B",    // 次级文本
        bg: "#F8FAFC",        // 页面背景
        cardline: "#F1F5F9",  // 卡片边界
      },
      borderRadius: { card: "12px" },
    },
  },
  plugins: [],
};

export default config;
