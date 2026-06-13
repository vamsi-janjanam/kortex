"use client";
import { useEffect, useRef, useState } from "react";
import { Send, FileText, AlertTriangle, Bot, User } from "lucide-react";
import { api, type ChatMessage, type ChatSource } from "@/lib/api";

interface DisplayMessage extends ChatMessage {
  sources?: ChatSource[];
  error?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    const next: DisplayMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setLoading(true);

    try {
      const res = await api.chat(text, history);
      setMessages([...next, { role: "assistant", content: res.answer, sources: res.sources }]);
    } catch (err) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong.",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const scorePill = (label: string, val: number, good: "high" | "low" = "high") => {
    const pct = Math.round(val * 100);
    const color =
      good === "high"
        ? val >= 0.7 ? "text-emerald-400" : val >= 0.4 ? "text-amber-400" : "text-red-400"
        : val <= 0.3 ? "text-emerald-400" : val <= 0.6 ? "text-amber-400" : "text-red-400";
    return (
      <span className={`text-xs ${color}`}>
        {label} {pct}%
      </span>
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-white">Chat</h2>
        <p className="text-sm text-slate-500 mt-1">
          Ask questions about your knowledge base. Answers are grounded in retrieved, quality-filtered chunks.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto bg-[#161b27] border border-slate-700 rounded-xl p-5 space-y-5">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-500 gap-2">
            <Bot size={32} className="text-violet-400" />
            <p className="text-sm">Ask something like &ldquo;What authentication method does the API use?&rdquo;</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            {m.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-violet-600/20 flex items-center justify-center flex-shrink-0">
                <Bot size={16} className="text-violet-400" />
              </div>
            )}
            <div className={`max-w-[75%] space-y-2 ${m.role === "user" ? "items-end" : "items-start"} flex flex-col`}>
              <div
                className={`rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-violet-600 text-white"
                    : m.error
                      ? "bg-red-950/50 border border-red-800 text-red-300"
                      : "bg-slate-800 text-slate-200"
                }`}
              >
                {m.error && (
                  <div className="flex items-center gap-1.5 mb-1 text-xs font-medium text-red-400">
                    <AlertTriangle size={12} /> Error
                  </div>
                )}
                {m.content}
              </div>

              {m.sources && m.sources.length > 0 && (
                <div className="w-full space-y-1.5">
                  <div className="text-xs text-slate-500 uppercase tracking-wider">Sources</div>
                  {m.sources.map((s) => (
                    <div key={s.chunk_id} className="bg-[#0f1320] border border-slate-800 rounded-lg px-3 py-2">
                      <div className="flex items-center gap-2 mb-1">
                        <FileText size={12} className="text-slate-500" />
                        <span className="text-xs text-slate-400 truncate">{s.document_title || "Untitled"}</span>
                        <span className="px-1.5 py-0.5 text-[10px] bg-slate-800 text-slate-500 rounded">
                          {s.source_type}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2 mb-1.5">{s.text}</p>
                      <div className="flex gap-3">
                        {scorePill("Freshness", s.freshness_score)}
                        {scorePill("Trust", s.trust_score)}
                        {scorePill("Conflict risk", s.conflict_risk, "low")}
                        {scorePill("Hallucination risk", s.hallucination_risk, "low")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {m.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
                <User size={16} className="text-slate-300" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-violet-600/20 flex items-center justify-center flex-shrink-0">
              <Bot size={16} className="text-violet-400" />
            </div>
            <div className="rounded-xl px-4 py-2.5 text-sm bg-slate-800 text-slate-400">Thinking…</div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-3 mt-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your knowledge base…"
          className="flex-1 bg-[#161b27] border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex items-center gap-2 px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors"
        >
          <Send size={14} />
          Send
        </button>
      </form>
    </div>
  );
}
