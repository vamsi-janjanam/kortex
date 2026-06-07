"use client";
import { useState } from "react";
import { Search, AlertTriangle, CheckCircle } from "lucide-react";
import { api, type SearchResult } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"raw" | "cleaned">("cleaned");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const minFreshness = mode === "cleaned" ? 0.3 : 0;
      const maxConflict = mode === "cleaned" ? 0.7 : 1;
      setResults(await api.search(query, minFreshness, maxConflict));
    } catch (err) {
      console.error(err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const scoreBar = (val: number, good: "high" | "low" = "high") => {
    const pct = Math.round(val * 100);
    const color = good === "high"
      ? val >= 0.7 ? "bg-emerald-500" : val >= 0.4 ? "bg-amber-500" : "bg-red-500"
      : val <= 0.3 ? "bg-emerald-500" : val <= 0.6 ? "bg-amber-500" : "bg-red-500";
    return (
      <div className="flex items-center gap-2">
        <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs text-slate-500 tabular-nums">{pct}%</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Semantic Search</h2>
        <p className="text-sm text-slate-500 mt-1">Query the knowledge base with optional quality filtering.</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="What authentication method does the API use?"
            className="w-full bg-[#161b27] border border-slate-700 rounded-lg pl-9 pr-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
          />
        </div>
        <select
          value={mode}
          onChange={e => setMode(e.target.value as "raw" | "cleaned")}
          className="bg-[#161b27] border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-violet-500"
        >
          <option value="cleaned">Cleaned (filtered)</option>
          <option value="raw">Raw (no filter)</option>
        </select>
        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {searched && !loading && (
        <div className="space-y-3">
          {results.length === 0 ? (
            <div className="text-slate-500 text-sm">No results found. Make sure the corpus is ingested.</div>
          ) : (
            results.map((r, i) => (
              <div key={r.chunk_id} className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-violet-400">#{i + 1}</span>
                      <span className="text-xs text-slate-500">{r.document_title || "Untitled"}</span>
                      <span className="px-1.5 py-0.5 text-xs bg-slate-800 text-slate-400 rounded">{r.source_type}</span>
                      {r.conflict_risk > 0.5 && (
                        <span className="flex items-center gap-1 text-xs text-red-400">
                          <AlertTriangle size={11} /> Conflict risk
                        </span>
                      )}
                      {r.freshness_score >= 0.7 && r.conflict_risk <= 0.3 && (
                        <span className="flex items-center gap-1 text-xs text-emerald-400">
                          <CheckCircle size={11} /> High quality
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">{r.text}</p>
                  </div>
                </div>
                <div className="flex gap-6 text-xs text-slate-500">
                  <div>Relevance {scoreBar(r.score)}</div>
                  <div>Freshness {scoreBar(r.freshness_score)}</div>
                  <div>Trust {scoreBar(r.trust_score)}</div>
                  <div>Conflict risk {scoreBar(r.conflict_risk, "low")}</div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
