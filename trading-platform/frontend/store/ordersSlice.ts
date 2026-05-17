import { create } from "zustand";

export type OrderBook = {
  orderid: string;
  tradingsymbol: string;
  transactiontype: "BUY" | "SELL";
  quantity: number;
  price: number;
  status: string;
  ordertype: string;
  producttype: string;
  exchange: string;
  updatetime: string;
};

export type TradeBook = {
  tradeid: string;
  orderid: string;
  tradingsymbol: string;
  transactiontype: "BUY" | "SELL";
  quantity: number;
  tradeprice: number;
  exchange: string;
  producttype: string;
  tradedate: string;
};

export type OrderFormState = {
  symbol: string;
  token: string;
  exchange: string;
  side: "BUY" | "SELL";
  orderType: "MARKET" | "LIMIT" | "STOPLOSS_LIMIT";
  product: "INTRADAY" | "DELIVERY" | "CARRYFORWARD";
  quantity: number;
  price: number;
  triggerPrice: number;
};

type OrdersState = {
  orderBook: OrderBook[];
  tradeBook: TradeBook[];
  recentEvents: Record<string, unknown>[];
  form: OrderFormState;
  setOrderBook: (orders: OrderBook[]) => void;
  setTradeBook: (trades: TradeBook[]) => void;
  addOrderEvent: (event: Record<string, unknown>) => void;
  updateForm: (patch: Partial<OrderFormState>) => void;
  resetForm: () => void;
};

const defaultForm: OrderFormState = {
  symbol: "",
  token: "",
  exchange: "NSE",
  side: "BUY",
  orderType: "MARKET",
  product: "INTRADAY",
  quantity: 1,
  price: 0,
  triggerPrice: 0,
};

export const useOrdersStore = create<OrdersState>((set) => ({
  orderBook: [],
  tradeBook: [],
  recentEvents: [],
  form: { ...defaultForm },

  setOrderBook: (orderBook) => set({ orderBook }),
  setTradeBook: (tradeBook) => set({ tradeBook }),
  addOrderEvent: (event) =>
    set((s) => ({ recentEvents: [event, ...s.recentEvents].slice(0, 50) })),
  updateForm: (patch) => set((s) => ({ form: { ...s.form, ...patch } })),
  resetForm: () => set({ form: { ...defaultForm } }),
}));
