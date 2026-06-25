import { create } from "zustand";

export type DataStatus = "fresh" | "stale" | "error";

interface AppState {
  currentDate: string;
  latestDataDate: string;
  selectedStrategyId: string;
  selectedStrategyVersion: string;
  dataStatus: DataStatus;
  
  setCurrentDate: (date: string) => void;
  setLatestDataDate: (date: string) => void;
  setSelectedStrategy: (id: string, version: string) => void;
  setDataStatus: (status: DataStatus) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentDate: "2026-06-24", // Default as per doc
  latestDataDate: "2026-06-23",
  selectedStrategyId: "illiquidity",
  selectedStrategyVersion: "v3.1",
  dataStatus: "fresh",

  setCurrentDate: (currentDate) => set({ currentDate }),
  setLatestDataDate: (latestDataDate) => set({ latestDataDate }),
  setSelectedStrategy: (selectedStrategyId, selectedStrategyVersion) =>
    set({ selectedStrategyId, selectedStrategyVersion }),
  setDataStatus: (dataStatus) => set({ dataStatus }),
}));
