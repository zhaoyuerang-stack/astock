import type { Config } from "tailwindcss";

// 配色对齐 WEB_DESIGN 与 chinese-color-consultant-v10.skill (白色+橙色风格)
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 传统色五层色彩网络 (清晨·窗前微光·算筹与朱砂)
        qilin: "#FCFAF2",       // [本] 存在基础 (凝脂偏亮)
        jilan: "#F4EFE0",       // [显·环] 环境色 (蜜合偏亮)
        taishi: "#E1C199",      // [显·中] 过渡色 (赤璋)
        qielan: "#E18A3B",      // [显·焦] 品牌橙 (库金)
        guangmingsha: "#CC5D20", // [显·焦] 焦点红橙 (光明砂)
        yinzhu: "#D12920",      // [符] 跌/风控危险 (银朱)
        songshi: "#4B8F98",     // [符] 涨/成功动作 (松石)
        gaoyu: "#31322C",       // [高光] 正文高对比度文本 (京元)
        
        // 兼容已有代码中的老命名
        navy: "#F3EFE0",        // 蜜合
        brand: "#CC5D20",       // 光明砂 (主品牌橙)
        line: "#DFD7C2",        // 蜜合边框
        teal: "#4B8F98",        // 松石
        ok: "#4B8F98",          // 成功动作 (松石)
        warn: "#E18A3B",        // 注意 (库金)
        danger: "#D12920",      // 危险 (银朱)
        ink: "#31322C",         // 主文本 (京元)
        subink: "#555147",      // 次文本 (骖骊)
        bg: "#FCFAF2",          // 大背景 (凝脂)
        cardline: "rgba(223, 215, 194, 0.4)", // 蜜合透明边框
      },
      borderRadius: { card: "12px" },
    },
  },
  plugins: [],
};

export default config;
