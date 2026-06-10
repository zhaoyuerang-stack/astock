import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/shell/Sidebar";
import TopBar from "@/components/shell/TopBar";
import AgentPanel from "@/components/shell/AgentPanel";

export const metadata: Metadata = {
  title: "Quant Research OS",
  description: "Research-first 量化研究平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        {/* 三栏:左导航 | 中研究区 | 右 Agent(WEB_DESIGN §1.1)*/}
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex-1 min-w-0 flex flex-col">
            <TopBar />
            <main className="flex-1 p-6 overflow-x-hidden">{children}</main>
          </div>
          <AgentPanel />
        </div>
      </body>
    </html>
  );
}
