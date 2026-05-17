export default function MacroPage() {
  const indicators = [
    { label: "India CPI YoY", value: "4.85%", status: "normal", note: "RBI target: 4%" },
    { label: "India GDP Growth", value: "6.4%", status: "good", note: "FY25 estimate" },
    { label: "RBI Repo Rate", value: "6.25%", status: "normal", note: "Neutral stance" },
    { label: "Fed Funds Rate", value: "5.25–5.50%", status: "high", note: "Restrictive" },
    { label: "US CPI YoY", value: "3.2%", status: "normal", note: "Above 2% target" },
    { label: "US 10Y Yield", value: "4.52%", status: "high", note: "EM pressure" },
    { label: "USD/INR", value: "83.62", status: "normal", note: "RBI managed float" },
    { label: "DXY Index", value: "104.2", status: "high", note: "Strong dollar" },
    { label: "Brent Crude", value: "$82.4", status: "normal", note: "India import cost" },
    { label: "India 10Y Yield", value: "7.08%", status: "normal", note: "G-Sec benchmark" },
  ];

  const statusColor: Record<string, string> = {
    good: "text-emerald-400",
    normal: "text-slate-300",
    high: "text-yellow-400",
    warning: "text-red-400",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Macro Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {indicators.map(({ label, value, status, note }) => (
          <div key={label} className="bg-slate-900 rounded-xl p-4 border border-slate-800 flex justify-between items-center">
            <div>
              <p className="text-xs text-slate-500">{label}</p>
              <p className="text-xs text-slate-600 mt-0.5">{note}</p>
            </div>
            <p className={`text-xl font-bold font-mono ${statusColor[status]}`}>{value}</p>
          </div>
        ))}
      </div>

      <section className="bg-slate-900 rounded-xl p-5 border border-slate-800">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Central Bank Calendar</h2>
        <div className="space-y-3">
          {[
            { date: "Jun 6, 2025", event: "RBI MPC Decision", expected: "Hold at 6.25%" },
            { date: "Jun 11, 2025", event: "US CPI Release", expected: "3.1% YoY est." },
            { date: "Jun 18, 2025", event: "Fed FOMC Decision", expected: "Hold 5.25–5.50%" },
            { date: "Jun 20, 2025", event: "India WPI Release", expected: "2.8% YoY est." },
          ].map(({ date, event, expected }) => (
            <div key={event} className="flex items-center justify-between py-2 border-b border-slate-800/50">
              <div>
                <p className="text-sm font-medium text-slate-200">{event}</p>
                <p className="text-xs text-slate-500">{expected}</p>
              </div>
              <span className="text-xs text-slate-500 font-mono">{date}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
