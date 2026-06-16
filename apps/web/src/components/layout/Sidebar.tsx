"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, Search, BarChart2, Zap, Activity, Network, MessageSquare, Bot } from "lucide-react";
import { clsx } from "clsx";

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/search", label: "Search", icon: Search },
  { href: "/eval", label: "Eval Results", icon: BarChart2 },
  { href: "/observability", label: "Observability", icon: Activity },
  { href: "/graph", label: "Knowledge Graph", icon: Network },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 bg-[#161b27] border-r border-slate-800 flex flex-col">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-800">
        <Zap size={20} className="text-violet-400" />
        <span className="font-semibold text-lg tracking-tight text-white">Kortex</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === href
                ? "bg-violet-600/20 text-violet-300 font-medium"
                : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-slate-800 text-xs text-slate-600">
        Phase 0 + 1 · v0.1.0
      </div>
    </aside>
  );
}
