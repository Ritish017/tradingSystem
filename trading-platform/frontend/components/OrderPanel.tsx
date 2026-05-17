"use client";
import { useEffect, useRef, useState } from "react";
import { useOrdersStore } from "@/store/ordersSlice";
import { apiBaseUrl } from "@/lib/api";
import { connectLiveWs } from "@/lib/ws";

export function OrderPanel() {
  const { orderBook, tradeBook, form, recentEvents, setOrderBook, setTradeBook, addOrderEvent, updateForm, resetForm } = useOrdersStore();
  const [tab, setTab] = useState<"place" | "book" | "trades">("place");
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const loadBooks = async () => {
    try {
      const [ob, tb] = await Promise.all([
        fetch(`${apiBaseUrl}/api/v1/orders/book`).then((r) => r.json()),
        fetch(`${apiBaseUrl}/api/v1/orders/tradebook`).then((r) => r.json()),
      ]);
      if (Array.isArray(ob)) setOrderBook(ob);
      if (Array.isArray(tb)) setTradeBook(tb);
    } catch {}
  };

  useEffect(() => {
    loadBooks();
    const id = setInterval(loadBooks, 10000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const ws = connectLiveWs("/api/v1/ws/orders");
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try { addOrderEvent(JSON.parse(ev.data)); } catch {}
    };
    return () => ws.close();
  }, []);

  const handlePlace = async () => {
    setSubmitting(true);
    setMsg(null);
    try {
      const r = await fetch(`${apiBaseUrl}/api/v1/orders/place`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tradingsymbol: form.symbol,
          symboltoken: form.token,
          transactiontype: form.side,
          exchange: form.exchange,
          ordertype: form.orderType,
          producttype: form.product,
          quantity: form.quantity,
          price: form.orderType === "MARKET" ? 0 : form.price,
          triggerprice: form.triggerPrice,
        }),
      });
      const data = await r.json();
      if (r.ok) {
        setMsg({ type: "ok", text: `Order placed: ${data.order_id}` });
        resetForm();
        loadBooks();
      } else {
        setMsg({ type: "err", text: data.detail ?? "Order failed" });
      }
    } catch (e) {
      setMsg({ type: "err", text: String(e) });
    }
    setSubmitting(false);
  };

  return (
    <div className="rounded border border-slate-700 bg-slate-900">
      {/* Tabs */}
      <div className="flex border-b border-slate-700">
        {(["place", "book", "trades"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize ${tab === t ? "border-b-2 border-amber-400 text-amber-400" : "text-slate-400 hover:text-slate-200"}`}
          >
            {t === "book" ? "Order Book" : t === "trades" ? "Trade Book" : "Place Order"}
          </button>
        ))}
      </div>

      <div className="p-4">
        {tab === "place" && (
          <div className="space-y-3 max-w-sm">
            {/* Symbol + Token */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-400">Symbol</label>
                <input className="w-full rounded bg-slate-800 border border-slate-700 px-2 py-1.5 text-sm text-slate-200 uppercase"
                  value={form.symbol} onChange={(e) => updateForm({ symbol: e.target.value.toUpperCase() })} placeholder="RELIANCE" />
              </div>
              <div>
                <label className="text-xs text-slate-400">Token</label>
                <input className="w-full rounded bg-slate-800 border border-slate-700 px-2 py-1.5 text-sm text-slate-200"
                  value={form.token} onChange={(e) => updateForm({ token: e.target.value })} placeholder="2885" />
              </div>
            </div>

            {/* Exchange + Product */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-400">Exchange</label>
                <select className="w-full rounded bg-slate-800 border border-slate-700 px-2 py-1.5 text-sm text-slate-200"
                  value={form.exchange} onChange={(e) => updateForm({ exchange: e.target.value as any })}>
                  {["NSE", "BSE", "NFO", "MCX"].map((x) => <option key={x}>{x}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400">Product</label>
                <select className="w-full rounded bg-slate-800 border border-slate-700 px-2 py-1.5 text-sm text-slate-200"
                  value={form.product} onChange={(e) => updateForm({ product: e.target.value as any })}>
                  {["INTRADAY", "DELIVERY", "CARRYFORWARD"].map((p) => <option key={p}>{p}</option>)}
                </select>
              </div>
            </div>

            {/* BUY / SELL toggle */}
            <div className="flex rounded overflow-hidden border border-slate-700">
              {(["BUY", "SELL"] as const).map((s) => (
                <button key={s} onClick={() => updateForm({ side: s })}
                  className={`flex-1 py-2 text-sm font-semibold ${form.side === s ? (s === "BUY" ? "bg-emerald-600 text-white" : "bg-rose-600 text-white") : "text-slate-400 hover:text-slate-200"}`}>
                  {s}
                </button>
              ))}
            </div>

            {/* Order type */}
            <div className="grid grid-cols-3 gap-1">
              {(["MARKET", "LIMIT", "STOPLOSS_LIMIT"] as const).map((t) => (
                <button key={t} onClick={() => updateForm({ orderType: t })}
                  className={`rounded px-2 py-1 text-xs ${form.orderType === t ? "bg-amber-500/20 text-amber-400 border border-amber-500/50" : "bg-slate-800 text-slate-400 border border-slate-700"}`}>
                  {t.replace("_", " ")}
                </button>
              ))}
            </div>

            {/* Qty + Price */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-400">Quantity</label>
                <input type="number" min={1} className="w-full rounded bg-slate-800 border border-slate-700 px-2 py-1.5 text-sm text-slate-200"
                  value={form.quantity} onChange={(e) => updateForm({ quantity: Number(e.target.value) })} />
              </div>
              {form.orderType !== "MARKET" && (
                <div>
                  <label className="text-xs text-slate-400">Price</label>
                  <input type="number" step="0.05" className="w-full rounded bg-slate-800 border border-slate-700 px-2 py-1.5 text-sm text-slate-200"
                    value={form.price} onChange={(e) => updateForm({ price: Number(e.target.value) })} />
                </div>
              )}
            </div>

            {msg && (
              <div className={`rounded px-3 py-2 text-xs ${msg.type === "ok" ? "bg-emerald-900/50 text-emerald-300" : "bg-rose-900/50 text-rose-300"}`}>
                {msg.text}
              </div>
            )}

            <button onClick={handlePlace} disabled={submitting || !form.symbol}
              className={`w-full rounded py-2 text-sm font-semibold transition-colors ${form.side === "BUY" ? "bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-900" : "bg-rose-600 hover:bg-rose-500 disabled:bg-rose-900"} text-white disabled:opacity-50`}>
              {submitting ? "Placing…" : `${form.side} ${form.symbol || "Order"}`}
            </button>
          </div>
        )}

        {tab === "book" && (
          <div className="overflow-x-auto">
            {orderBook.length === 0 ? <p className="text-slate-500 text-sm">No orders</p> : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-500">
                    <th className="px-2 py-1.5 text-left">Symbol</th>
                    <th className="px-2 py-1.5 text-left">Side</th>
                    <th className="px-2 py-1.5 text-right">Qty</th>
                    <th className="px-2 py-1.5 text-right">Price</th>
                    <th className="px-2 py-1.5 text-left">Type</th>
                    <th className="px-2 py-1.5 text-left">Status</th>
                    <th className="px-2 py-1.5 text-left">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {orderBook.map((o) => (
                    <tr key={o.orderid} className="border-b border-slate-800/60">
                      <td className="px-2 py-1.5 font-medium text-slate-200">{o.tradingsymbol}</td>
                      <td className={`px-2 py-1.5 font-semibold ${o.transactiontype === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>{o.transactiontype}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-slate-300">{o.quantity}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-slate-300">₹{Number(o.price).toFixed(2)}</td>
                      <td className="px-2 py-1.5 text-slate-400">{o.ordertype}</td>
                      <td className="px-2 py-1.5">
                        <span className={`rounded px-1.5 py-0.5 text-xs ${o.status === "complete" ? "bg-emerald-900 text-emerald-300" : o.status === "rejected" ? "bg-rose-900 text-rose-300" : "bg-slate-700 text-slate-300"}`}>
                          {o.status}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 text-slate-500">{o.updatetime?.slice(0, 8)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === "trades" && (
          <div className="overflow-x-auto">
            {tradeBook.length === 0 ? <p className="text-slate-500 text-sm">No trades today</p> : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-500">
                    <th className="px-2 py-1.5 text-left">Symbol</th>
                    <th className="px-2 py-1.5 text-left">Side</th>
                    <th className="px-2 py-1.5 text-right">Qty</th>
                    <th className="px-2 py-1.5 text-right">Trade Price</th>
                    <th className="px-2 py-1.5 text-left">Product</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeBook.map((t, i) => (
                    <tr key={i} className="border-b border-slate-800/60">
                      <td className="px-2 py-1.5 font-medium text-slate-200">{t.tradingsymbol}</td>
                      <td className={`px-2 py-1.5 font-semibold ${t.transactiontype === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>{t.transactiontype}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-slate-300">{t.quantity}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-slate-300">₹{Number(t.tradeprice).toFixed(2)}</td>
                      <td className="px-2 py-1.5 text-slate-400">{t.producttype}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
