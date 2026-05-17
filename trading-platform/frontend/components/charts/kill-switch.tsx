"use client";

import { useState } from "react";

export function KillSwitch() {
  const [loading, setLoading] = useState(false);
  const [halted, setHalted] = useState(false);

  async function activateKillSwitch() {
    if (!confirm("Are you sure you want to HALT ALL TRADING? This cannot be undone automatically.")) {
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch("/api/fastapi/risk/kill-switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "manual_halt" }),
      });
      
      if (response.ok) {
        setHalted(true);
        alert("Kill switch activated. All trading halted.");
      } else {
        alert("Failed to activate kill switch");
      }
    } catch (error) {
      alert(`Error: ${error}`);
    } finally {
      setLoading(false);
    }
  }

  async function resumeTrading() {
    if (!confirm("Resume trading? Ensure all issues are resolved.")) {
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch("/api/fastapi/risk/resume", {
        method: "POST",
      });
      
      if (response.ok) {
        setHalted(false);
        alert("Trading resumed");
      } else {
        alert("Failed to resume trading");
      }
    } catch (error) {
      alert(`Error: ${error}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex gap-4 items-center">
      <button
        className="rounded bg-red-700 px-6 py-3 font-bold text-white hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed text-lg"
        onClick={activateKillSwitch}
        disabled={loading || halted}
        type="button"
      >
        {loading ? "Processing..." : halted ? "HALTED" : "🛑 KILL SWITCH"}
      </button>
      
      {halted && (
        <button
          className="rounded bg-green-700 px-6 py-3 font-bold text-white hover:bg-green-600 disabled:opacity-50 text-lg"
          onClick={resumeTrading}
          disabled={loading}
          type="button"
        >
          {loading ? "Processing..." : "✅ Resume Trading"}
        </button>
      )}
      
      {halted && (
        <span className="text-red-600 font-bold text-lg animate-pulse">
          ⚠️ ALL TRADING HALTED
        </span>
      )}
    </div>
  );
}

