"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

const PLACEHOLDER = [
  { metric: "Accuracy", raw: 52, cleaned: 78 },
  { metric: "Faithfulness", raw: 61, cleaned: 84 },
  { metric: "Hallucination-Free Rate", raw: 64, cleaned: 89 },
];

export default function EvalPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Eval Harness Results</h2>
        <p className="text-sm text-slate-500 mt-1">
          Before vs. after comparison — the proof that knowledge cleaning improves retrieval.
        </p>
      </div>

      <div className="bg-[#161b27] border border-amber-700/40 rounded-xl p-5">
        <p className="text-sm text-amber-400">
          <strong>Placeholder data shown.</strong> Run{" "}
          <code className="bg-slate-800 px-1 rounded">make eval</code> to generate real results,
          then update this page with the output JSON.
        </p>
      </div>

      <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-slate-300 mb-6">Before vs. After (30 Q&A pairs)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={PLACEHOLDER} barCategoryGap="30%">
            <XAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" />
            <Tooltip
              contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
              formatter={(v: number) => [`${v}%`]}
            />
            <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 13 }} />
            <Bar dataKey="raw" name="Raw (no cleaning)" fill="#475569" radius={[4, 4, 0, 0]} />
            <Bar dataKey="cleaned" name="Cleaned (Kortex)" fill="#7c3aed" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-[#161b27] border border-slate-700 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Metric</th>
              <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Raw</th>
              <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Cleaned</th>
              <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Delta</th>
            </tr>
          </thead>
          <tbody>
            {PLACEHOLDER.map(row => (
              <tr key={row.metric} className="border-b border-slate-800 last:border-0">
                <td className="px-5 py-3 text-slate-300">{row.metric}</td>
                <td className="px-5 py-3 text-right text-slate-400">{row.raw}%</td>
                <td className="px-5 py-3 text-right text-violet-300 font-medium">{row.cleaned}%</td>
                <td className="px-5 py-3 text-right text-emerald-400 font-medium">▲ {row.cleaned - row.raw}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
