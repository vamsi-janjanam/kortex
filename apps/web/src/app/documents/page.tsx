"use client";
import { useEffect, useState } from "react";
import { FileText, Plus } from "lucide-react";
import { api, type Document } from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", source_url: "", source_type: "markdown" });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    api.getDocuments().then(setDocs).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.createDocument(form);
      setShowForm(false);
      setForm({ title: "", source_url: "", source_type: "markdown" });
      load();
    } catch (err) {
      alert("Failed to create document: " + String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const sourceColors: Record<string, string> = {
    pdf: "bg-red-900/30 text-red-300",
    markdown: "bg-blue-900/30 text-blue-300",
    github: "bg-slate-700 text-slate-300",
    slack: "bg-purple-900/30 text-purple-300",
    confluence: "bg-indigo-900/30 text-indigo-300",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Documents</h2>
          <p className="text-sm text-slate-500 mt-1">{docs.length} document{docs.length !== 1 ? "s" : ""} in corpus</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={15} /> Add Document
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-[#161b27] border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-medium text-slate-300">Register New Document</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Title</label>
              <input
                value={form.title}
                onChange={e => setForm({ ...form, title: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
                placeholder="My Document"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Source Type</label>
              <select
                value={form.source_type}
                onChange={e => setForm({ ...form, source_type: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
              >
                {["markdown", "pdf", "github", "slack", "confluence", "other"].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Source URL or Path</label>
            <input
              required
              value={form.source_url}
              onChange={e => setForm({ ...form, source_url: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-violet-500"
              placeholder="/data/seed_corpus/api_docs_v2.md"
            />
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors"
            >
              {submitting ? "Registering…" : "Register & Ingest"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-slate-400 text-sm hover:text-slate-200">
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm">Loading documents…</div>
      ) : docs.length === 0 ? (
        <div className="bg-[#161b27] border border-slate-700 rounded-xl p-10 text-center">
          <FileText size={36} className="mx-auto text-slate-700 mb-3" />
          <p className="text-slate-500 text-sm">No documents yet. Run <code className="bg-slate-800 px-1 rounded">make seed</code> to load the corpus.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {docs.map(doc => (
            <div key={doc.id} className="bg-[#161b27] border border-slate-700 rounded-xl p-4 flex items-center gap-4">
              <FileText size={18} className="text-slate-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">{doc.title || "Untitled"}</p>
                <p className="text-xs text-slate-600 truncate">{doc.source_url}</p>
              </div>
              <span className={`px-2 py-0.5 text-xs rounded-full ${sourceColors[doc.source_type] || "bg-slate-700 text-slate-300"}`}>
                {doc.source_type}
              </span>
              <span className="text-xs text-slate-500">{doc.chunk_count} chunks</span>
              <span className="text-xs text-slate-600">{new Date(doc.ingested_at).toLocaleDateString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
