import { create } from "zustand";
import type { Receipt } from "./api";

type UI = {
  projectId: number | null;
  setProject: (id: number | null) => void;
  receipt: Receipt | null;
  openReceipt: (r: Receipt) => void;
  closeReceipt: () => void;
  paletteOpen: boolean;
  setPalette: (v: boolean) => void;
  rulesOpen: boolean;
  setRules: (v: boolean) => void;
  scenario: any | null;
  setScenario: (s: any | null) => void;
  linkSearch: string;
  setLinkSearch: (s: string) => void;
};

const saved = typeof localStorage !== "undefined" ? Number(localStorage.getItem("bomerang.project")) || null : null;

export const useUI = create<UI>((set) => ({
  projectId: saved,
  setProject: (id) => {
    try {
      if (id) localStorage.setItem("bomerang.project", String(id));
      else localStorage.removeItem("bomerang.project");
    } catch {
      /* storage unavailable */
    }
    set({ projectId: id });
  },
  receipt: null,
  openReceipt: (r) => set({ receipt: r }),
  closeReceipt: () => set({ receipt: null }),
  paletteOpen: false,
  setPalette: (v) => set({ paletteOpen: v }),
  rulesOpen: false,
  setRules: (v) => set({ rulesOpen: v }),
  scenario: null,
  setScenario: (s) => set({ scenario: s }),
  linkSearch: "",
  setLinkSearch: (s) => set({ linkSearch: s }),
}));
