"use client";
import { useState } from "react";
import { Bot, Brain, Sparkles, ListOrdered } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

interface MemoryRef {
  id: string;
  agent_role: string;
  memory_type: string;
  content: string;
  shared: boolean;
}

interface AgentRunResult {
  answer: string;
  plan: string;
  recalled_memories: MemoryRef[];
  created_memories: MemoryRef[];
  sources: Record<string, unknown>[];
  agent_trace: string[];
}

export default function AgentsPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AgentRunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [ran, setRan] = useState(false);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setRan(true);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (API_KEY) headers["X-API-Key"] = API_KEY;
      const res = await fetch(`${API_URL}/api/v1/agents/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setResult(await res.json());
    } catch (err) {
      console.error(err);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const memoryCard = (m: MemoryRef) => (
    <div key={m.id || m.content} className="bg-[#161b27] border border-slate-700 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="px-1.5 py-0.5 text-xs bg-slate-800 text-slate-400 rounded">{m.agent_role}</span>
        <span className="px-1.5 py-0.5 text-xs bg-slate-800 text-slate-400 rounded">{m.memory_type}</span>
        {m.shared && <span className="text-xs text-violet-400">shared</span>}
      </div>
      <p className="text-sm text-slate-300 leading-relaxed">{m.content}</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Agent Workflow</h2>
        <p className="text-sm text-slate-500 mt-1">
          A multi-agent run with a shared memory store. Agents recall prior knowledge and learn new facts.
        </p>
      </div>

      <form onSubmit={handleRun} className="flex gap-3">
        <div className="flex-1 relative">
          <Bot size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="What authentication method does the API use?"
            className="w-full bg-[#161b27] border border-slate-700 rounded-lg pl-9 pr-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors"
        >
          {loading ? "Running…" : "Run"}
        </button>
      </form>

      {ran && !loading && !result && (
        <div className="text-slate-500 text-sm">No result. Make sure the API is running and the corpus is ingested.</div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={15} className="text-violet-400" />
              <h3 className="text-sm font-medium text-white">Answer</h3>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{result.answer}</p>
            {result.plan && <p className="text-xs text-slate-500 mt-3">Plan: {result.plan}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Brain size={15} className="text-amber-400" />
                <h3 className="text-sm font-medium text-white">Recalled memories ({result.recalled_memories.length})</h3>
              </div>
              {result.recalled_memories.length === 0 ? (
                <div className="text-slate-500 text-sm">None recalled this run.</div>
              ) : (
                result.recalled_memories.map(memoryCard)
              )}
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles size={15} className="text-emerald-400" />
                <h3 className="text-sm font-medium text-white">New memories learned ({result.created_memories.length})</h3>
              </div>
              {result.created_memories.length === 0 ? (
                <div className="text-slate-500 text-sm">None learned this run.</div>
              ) : (
                result.created_memories.map(memoryCard)
              )}
            </div>
          </div>

          <div className="bg-[#161b27] border border-slate-700 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <ListOrdered size={15} className="text-slate-400" />
              <h3 className="text-sm font-medium text-white">Agent trace</h3>
            </div>
            <ol className="space-y-1.5">
              {result.agent_trace.map((step, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-slate-400">
                  <span className="text-xs font-medium text-violet-400 tabular-nums">{i + 1}.</span>
                  <span className="font-mono text-xs">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}
