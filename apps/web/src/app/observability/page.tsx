"use client";
import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  api,
  type ConflictTrendResponse,
  type QualityBySourceResponse,
  type QualityDistributionResponse,
  type StalenessByAgeResponse,
} from "@/lib/api";

export default function ObservabilityPage() {
  const [conflictTrend, setConflictTrend] = useState<ConflictTrendResponse | null>(null);
  const [qualityBySource, setQualityBySource] = useState<QualityBySourceResponse | null>(null);
  const [qualityDistribution, setQualityDistribution] = useState<QualityDistributionResponse | null>(null);
  const [stalenessByAge, setStalenessByAge] = useState<StalenessByAgeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getConflictTrend(),
      api.getQualityBySource(),
      api.getQualityDistribution(),
      api.getStalenessByAge(),
    ])
      .then(([trend, bySource, distribution, staleness]) => {
        setConflictTrend(trend);
        setQualityBySource(bySource);
        setQualityDistribution(distribution);
        setStalenessByAge(staleness);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-slate-500 text-sm">Loading observability data…</div>;
  }

  const qualityBySourceData = (qualityBySource?.data ?? []).map((d) => ({
    source_type: d.source_type,
    avg_freshness_score: Math.round(d.avg_freshness_score * 100),
    avg_trust_score: Math.round(d.avg_trust_score * 100),
    avg_conflict_risk: Math.round(d.avg_conflict_risk * 100),
  }));

  const stalenessData = (stalenessByAge?.data ?? []).map((d) => ({
    age_bucket: d.age_bucket,
    avg_freshness_score: Math.round(d.avg_freshness_score * 100),
    chunk_count: d.chunk_count,
  }));

  const freshnessDistribution = qualityDistribution?.freshness ?? [];
  const trustDistribution = qualityDistribution?.trust ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Knowledge Observability</h2>
        <p className="text-sm text-slate-500 mt-1">
          Trends and distributions for conflict detection, source quality, and content staleness.
        </p>
      </div>

      <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Conflict Trend ({conflictTrend?.days ?? 30} days)</h3>
        {conflictTrend && conflictTrend.data.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={conflictTrend.data}>
              <CartesianGrid stroke="#2d3748" />
              <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
              />
              <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 13 }} />
              <Area
                type="monotone"
                dataKey="detected"
                name="Detected"
                stroke="#7c3aed"
                fill="#7c3aed"
                fillOpacity={0.25}
              />
              <Area
                type="monotone"
                dataKey="closed"
                name="Closed"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.25}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
            No conflict activity yet
          </div>
        )}
      </div>

      <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Quality by Source</h3>
        {qualityBySourceData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={qualityBySourceData} barCategoryGap="30%">
              <CartesianGrid stroke="#2d3748" />
              <XAxis dataKey="source_type" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" />
              <Tooltip
                contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
                formatter={(v: number) => [`${v}%`]}
              />
              <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 13 }} />
              <Bar dataKey="avg_freshness_score" name="Avg Freshness" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              <Bar dataKey="avg_trust_score" name="Avg Trust" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="avg_conflict_risk" name="Avg Conflict Risk" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
            Ingest documents to see quality metrics
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Freshness Distribution</h3>
          {freshnessDistribution.length > 0 && freshnessDistribution.some((b) => b.count > 0) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={freshnessDistribution} barCategoryGap="30%">
                <CartesianGrid stroke="#2d3748" />
                <XAxis dataKey="bucket" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
                />
                <Bar dataKey="count" name="Chunks" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
              Ingest documents to see quality metrics
            </div>
          )}
        </div>

        <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Trust Distribution</h3>
          {trustDistribution.length > 0 && trustDistribution.some((b) => b.count > 0) ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={trustDistribution} barCategoryGap="30%">
                <CartesianGrid stroke="#2d3748" />
                <XAxis dataKey="bucket" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
                />
                <Bar dataKey="count" name="Chunks" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
              Ingest documents to see quality metrics
            </div>
          )}
        </div>
      </div>

      <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Staleness by Age</h3>
        {stalenessData.length > 0 && stalenessData.some((b) => b.chunk_count > 0) ? (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={stalenessData} barCategoryGap="30%">
              <CartesianGrid stroke="#2d3748" />
              <XAxis dataKey="age_bucket" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" />
              <Tooltip
                contentStyle={{ background: "#1e2535", border: "1px solid #374151", borderRadius: 8 }}
                formatter={(v: number, name: string, props) => {
                  if (name === "Avg Freshness") {
                    return [`${v}% (${props.payload.chunk_count} chunks)`, name];
                  }
                  return [v, name];
                }}
              />
              <Bar dataKey="avg_freshness_score" name="Avg Freshness" fill="#7c3aed" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
            Ingest documents to see staleness metrics
          </div>
        )}
      </div>
    </div>
  );
}
