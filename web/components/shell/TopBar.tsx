export default function TopBar() {
  return (
    <header className="h-14 shrink-0 bg-white border-b border-cardline flex items-center justify-between px-6">
      <input
        placeholder="搜索因子 / 策略 / 数据集 / 实验…"
        className="w-80 max-w-[40vw] text-sm bg-bg border border-cardline rounded-lg px-3 py-1.5 outline-none focus:border-brand"
      />
      <div className="flex items-center gap-4 text-sm text-subink">
        <span className="text-xs">数据更新:2026-06-10</span>
        <span className="w-7 h-7 rounded-full bg-brand text-white grid place-items-center text-xs">K</span>
      </div>
    </header>
  );
}
