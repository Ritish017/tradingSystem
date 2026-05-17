import { create } from "zustand";

export type Holding = {
  tradingsymbol: string;
  exchange: string;
  quantity: number;
  averageprice: number;
  ltp: number;
  live_ltp: number;
  current_value: number;
  invested_value: number;
  unrealized_pnl: number;
  pnl_pct: number;
};

export type LivePosition = {
  tradingsymbol: string;
  exchange: string;
  producttype: string;
  netqty: number;
  averageprice: number;
  ltp: number;
  unrealisedprofitloss: number;
  realisedprofitloss: number;
};

export type PnLSnapshot = {
  realized: number;
  unrealized: number;
  total: number;
  available_cash: number;
  used_margin: number;
  net: number;
};

type PortfolioState = {
  holdings: Holding[];
  positions: LivePosition[];
  pnl: PnLSnapshot | null;
  lastUpdated: string | null;
  setHoldings: (h: Holding[]) => void;
  setPositions: (p: LivePosition[]) => void;
  setPnL: (pnl: PnLSnapshot) => void;
  markUpdated: () => void;
};

export const usePortfolioStore = create<PortfolioState>((set) => ({
  holdings: [],
  positions: [],
  pnl: null,
  lastUpdated: null,

  setHoldings: (holdings) => set({ holdings }),
  setPositions: (positions) => set({ positions }),
  setPnL: (pnl) => set({ pnl }),
  markUpdated: () => set({ lastUpdated: new Date().toISOString() }),
}));
