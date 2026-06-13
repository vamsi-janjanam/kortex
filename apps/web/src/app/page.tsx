"use client";
import { useEffect, useState } from "react";
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from "recharts";
import StatCard from "@/components/ui/StatCard";
import { api, type KnowledgeStats } from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const radarData = stats
    ? [
        { metric: "Freshness", score: Math.round(stats.avg_freshness_score * 100) },
        { metric: "Trust", score: Math.round(stats.avg_trust_score * 100) },
        { metric: "Coverage", score: stats.coverage_pct },
        { metric: "Conflict-Free", score: Math.round((1 - stats.avg_conflict_risk) * 100) },
        { metric: "Low Hallucination Risk", score: Math.round((1 - stats.avg_hallucination_risk) * 100) },
      ]
    : [];

  if (loading) {
    return <div className="text-slate-500 text-sm">Loading knowledge health…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Knowledge Health</h2>
        <p className="text-sm text-slate-500 mt-1">Real-time quality metrics across your knowledge base.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Documents" value={stats?.document_count ?? 0} accent="violet" />
        <StatCard label="Chunks" value={stats?.chunk_count ?? 0} />
        <StatCard
          label="Open Conflicts"
          value={stats?.open_conflict_count ?? 0}
          accent={stats && stats.open_conflict_count > 0 ? "red" : "green"}
        />
        <StatCard
          label="Avg Freshness"
          value={`${Math.round((stats?.avg_freshness_score ?? 0) * 100)}%`}
          accent={stats && stats.avg_freshness_score < 0.5 ? "amber" : "green"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Knowledge Quality Radar</h3>
          {radarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#2d3748" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <Radar name="Score" dataKey="score" stroke="#7c3aed" fill="#7c3aed" fillOpacity={0.25} />
                <Tooltip
                  contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
                  formatter={(v: number) => [`${v}%`, "Score"]}
                />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
              Ingest documents to see quality metrics
            </div>
          )}
        </div>

        <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Health Summary</h3>
          <dl className="space-y-3">
            {[
              { label: "Avg Trust Score", val: `${Math.round((stats?.avg_trust_score ?? 0) * 100)}%` },
              { label: "Avg Conflict Risk", val: `${Math.round((stats?.avg_conflict_risk ?? 0) * 100)}%` },
              { label: "Avg Hallucination Risk", val: `${Math.round((stats?.avg_hallucination_risk ?? 0) * 100)}%` },
              { label: "High-Quality Coverage", val: `${stats?.coverage_pct ?? 0}%` },
            ].map(({ label, val }) => (
              <div key={label} className="flex justify-between text-sm">
                <dt className="text-slate-500">{label}</dt>
                <dd className="text-slate-200 font-medium">{val}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-6 pt-4 border-t border-slate-800 text-xs text-slate-600">
            Run <code className="bg-slate-800 px-1 rounded">make seed</code> then{" "}
            <code className="bg-slate-800 px-1 rounded">make eval</code> to populate metrics.
          </div>
        </div>
      </div>
    </div>
  );
}
