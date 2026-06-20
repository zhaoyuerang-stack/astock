import { create } from "zustand";
import { persist } from "zustand/middleware";

// 三栏宽度约束(像素)。默认值刻意等于原硬编码值,保证 SSR 首屏一致、无水合告警。
export const SIDEBAR_DEFAULT = 220;
export const SIDEBAR_MIN = 180;
export const SIDEBAR_MAX = 360;
export const AGENT_DEFAULT = 320;
export const AGENT_MIN = 280;
export const AGENT_MAX = 560;

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

interface LayoutState {
  sidebarWidth: number;
  agentWidth: number;
  sidebarCollapsed: boolean;
  agentCollapsed: boolean;
  setSidebarWidth: (w: number) => void;
  setAgentWidth: (w: number) => void;
  resetSidebar: () => void;
  resetAgent: () => void;
  toggleSidebar: () => void;
  toggleAgent: () => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      sidebarWidth: SIDEBAR_DEFAULT,
      agentWidth: AGENT_DEFAULT,
      sidebarCollapsed: false,
      agentCollapsed: false,
      // clamp 收敛在唯一写入口,任何调用方都越不了界
      setSidebarWidth: (w) => set({ sidebarWidth: clamp(w, SIDEBAR_MIN, SIDEBAR_MAX) }),
      setAgentWidth: (w) => set({ agentWidth: clamp(w, AGENT_MIN, AGENT_MAX) }),
      resetSidebar: () => set({ sidebarWidth: SIDEBAR_DEFAULT }),
      resetAgent: () => set({ agentWidth: AGENT_DEFAULT }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      toggleAgent: () => set((s) => ({ agentCollapsed: !s.agentCollapsed })),
    }),
    {
      name: "quant-os-layout",
      // 手动 rehydrate(见 LayoutHydrator),避免 Next.js SSR 首屏水合不一致
      skipHydration: true,
    },
  ),
);
