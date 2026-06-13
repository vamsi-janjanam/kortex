"use client";
import { useEffect, useState } from "react";
import { api, type GraphResponse } from "@/lib/api";
import StatCard from "@/components/ui/StatCard";
import GraphCanvas from "@/components/graph/GraphCanvas";

export default function GraphPage() {
  const [data, setData] = useState<GraphResponse>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getGraph()
      .then((res) => setData(res))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-slate-500 text-sm">Loading knowledge graph…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Knowledge Graph</h2>
        <p className="text-sm text-slate-500 mt-1">
          Entities and relationships extracted from your knowledge base.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="Entities" value={data.nodes.length} />
        <StatCard label="Relationships" value={data.edges.length} />
      </div>

      <GraphCanvas nodes={data.nodes} edges={data.edges} />
    </div>
  );
}
