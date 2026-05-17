import { create } from "zustand";

export type Tick = {
  symbol: string;
  price: number;
  ts: string;
};

export type Quote = {
  token: string;
  symbol: string;
  exchange: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  avg_price: number;
  oi: number;
  upper_circuit: number;
  lower_circuit: number;
  depth: Record<string, unknown>;
};

export type Candle = {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type MarketState = {
  ticks: Record<string, Tick>;
  quotes: Record<string, Quote>;
  candles: Record<string, Candle[]>; // key: "SYMBOL:tf"
  watchlist: string[];
  setTick: (tick: Tick) => void;
  setQuote: (quote: Quote) => void;
  setCandles: (symbol: string, tf: string, candles: Candle[]) => void;
  addWatchlist: (symbol: string) => void;
  removeWatchlist: (symbol: string) => void;
};

export const useMarketStore = create<MarketState>((set) => ({
  ticks: {},
  quotes: {},
  candles: {},
  watchlist: ["RELIANCE", "SBIN", "INFY", "TCS", "BAJFINANCE"],

  setTick: (tick) =>
    set((s) => ({ ticks: { ...s.ticks, [tick.symbol]: tick } })),

  setQuote: (quote) =>
    set((s) => ({ quotes: { ...s.quotes, [quote.symbol]: quote } })),

  setCandles: (symbol, tf, candles) =>
    set((s) => ({ candles: { ...s.candles, [`${symbol}:${tf}`]: candles } })),

  addWatchlist: (symbol) =>
    set((s) => ({
      watchlist: s.watchlist.includes(symbol) ? s.watchlist : [...s.watchlist, symbol],
    })),

  removeWatchlist: (symbol) =>
    set((s) => ({ watchlist: s.watchlist.filter((x) => x !== symbol) })),
}));
