"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const NAV = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/market", label: "Market", icon: "📉" },
  { href: "/trading", label: "Trading", icon: "⚡" },
  { href: "/options", label: "Options", icon: "🎯" },
  { href: "/portfolio", label: "Portfolio", icon: "💼" },
  { href: "/positions", label: "Positions", icon: "📈" },
  { href: "/strategies", label: "Strategies", icon: "⚙️" },
  { href: "/risk", label: "Risk", icon: "🛡️" },
  { href: "/backtest", label: "Backtest", icon: "🔬" },
  { href: "/learning", label: "Learning", icon: "🧠" },
  { href: "/intelligence", label: "Intelligence", icon: "🤖" },
  { href: "/macro", label: "Macro", icon: "🌐" },
  { href: "/commodities", label: "Commodities", icon: "🏭" },
  { href: "/gold-silver", label: "Gold & Silver", icon: "🥇" },
  { href: "/crypto", label: "Crypto", icon: "₿" },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="w-52 shrink-0 border-r border-slate-800 flex flex-col py-4">
        <div className="px-4 mb-6">
          <span className="text-lg font-bold text-amber-400">⚡ TradePlatform</span>
        </div>
        <nav className="flex flex-col gap-1 px-2">
          {NAV.map(({ href, label, icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-amber-500/20 text-amber-400 font-medium"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-800"
                }`}
              >
                <span>{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
