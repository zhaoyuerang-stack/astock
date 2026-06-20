"use client";

// Task 18: 沙盒模式常驻水印 —— 合成演示数据(可能含美股示例)必须显式标注,
// 永不能被误当真实 A 股生产状态。production 视图不渲染本 banner。
export default function SimulationModeBanner() {
  return (
    <div
      role="alert"
      className="mb-3 rounded border border-amber-500/60 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-300"
    >
      ⚠️ 策略模拟沙盒 —— 合成演示数据(含美股示例),仅用于教学演示,
      <span className="font-medium"> 不可用于交易,也不代表真实 A 股持仓</span>。
    </div>
  );
}
