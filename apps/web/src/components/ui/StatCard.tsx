interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "default" | "green" | "amber" | "red" | "violet";
}

const accents = {
  default: "border-slate-700",
  green: "border-emerald-700",
  amber: "border-amber-600",
  red: "border-red-700",
  violet: "border-violet-600",
};

export default function StatCard({ label, value, sub, accent = "default" }: StatCardProps) {
  return (
    <div className={`bg-[#161b27] border ${accents[accent]} rounded-xl p-5 flex flex-col gap-1`}>
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
      <span className="text-3xl font-bold text-white tabular-nums">{value}</span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  );
}
