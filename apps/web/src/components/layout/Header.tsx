"use client";
import { useEffect, useState } from "react";
import { CheckCircle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

export default function Header() {
  const [health, setHealth] = useState<{ status: string } | null>(null);

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth({ status: "error" }));
  }, []);

  return (
    <header className="h-14 border-b border-slate-800 bg-[#161b27] flex items-center justify-between px-6">
      <h1 className="text-sm font-medium text-slate-400">Knowledge Reliability Platform</h1>
      <div className="flex items-center gap-2 text-xs">
        {health?.status === "healthy" ? (
          <span className="flex items-center gap-1 text-emerald-400">
            <CheckCircle size={13} /> All systems operational
          </span>
        ) : health?.status === "degraded" ? (
          <span className="flex items-center gap-1 text-amber-400">
            <AlertCircle size={13} /> Degraded
          </span>
        ) : (
          <span className="text-slate-600">Checking status…</span>
        )}
      </div>
    </header>
  );
}
