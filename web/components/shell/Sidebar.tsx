"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/nav";

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-[240px] shrink-0 bg-navy text-white flex flex-col h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-white/10">
        <div className="text-base font-semibold">Quant Research OS</div>
        <div className="text-[11px] text-white/50 mt-0.5">Research-first 量化研究平台</div>
      </div>
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center justify-between px-5 py-2.5 text-sm transition-colors ${
                active ? "bg-brand text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
              }`}
            >
              <span>{item.label}</span>
              {!item.ready && (
                <span className="text-[10px] text-white/30 border border-white/15 rounded px-1">建设中</span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-3 border-t border-white/10 text-[11px] text-white/40">
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-ok" />
          系统运行正常
        </div>
        <div className="mt-1">本地模式 · Phase 1</div>
      </div>
    </aside>
  );
}
