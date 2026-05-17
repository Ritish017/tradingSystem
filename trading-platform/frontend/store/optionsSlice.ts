import { create } from "zustand";

export type Greeks = {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
};

export type OptionStrike = {
  strikePrice: number;
  CE?: {
    ltp: number;
    openInterest: number;
    changeinOpenInterest: number;
    totalBuyQuantity: number;
    totalSellQuantity: number;
    iv?: number | null;
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
  };
  PE?: {
    ltp: number;
    openInterest: number;
    changeinOpenInterest: number;
    totalBuyQuantity: number;
    totalSellQuantity: number;
    iv?: number | null;
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
  };
};

export type PCR = {
  pcr_oi: number;
  pcr_volume: number;
  total_call_oi: number;
  total_put_oi: number;
  sentiment: string;
};

export type MaxPain = {
  max_pain_strike: number;
  min_total_pain: number;
};

type OptionsState = {
  symbol: string;
  expiry: string;
  spot: number;
  chain: OptionStrike[];
  pcr: PCR | null;
  maxPain: MaxPain | null;
  expiries: string[];
  loading: boolean;
  error: string | null;
  setSymbol: (s: string) => void;
  setExpiry: (e: string) => void;
  setChainData: (data: {
    spot: number;
    chain: OptionStrike[];
    pcr: PCR;
    maxPain: MaxPain;
  }) => void;
  setExpiries: (expiries: string[]) => void;
  setLoading: (v: boolean) => void;
  setError: (e: string | null) => void;
};

export const useOptionsStore = create<OptionsState>((set) => ({
  symbol: "NIFTY",
  expiry: "",
  spot: 0,
  chain: [],
  pcr: null,
  maxPain: null,
  expiries: [],
  loading: false,
  error: null,

  setSymbol: (symbol) => set({ symbol }),
  setExpiry: (expiry) => set({ expiry }),
  setChainData: ({ spot, chain, pcr, maxPain }) =>
    set({ spot, chain, pcr, maxPain }),
  setExpiries: (expiries) => set({ expiries }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
