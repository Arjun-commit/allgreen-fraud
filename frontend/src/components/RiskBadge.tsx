/**
 * Color-coded risk level badge. Used everywhere.
 */

const COLORS: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

export default function RiskBadge({ level }: { level: string }) {
  const cls = COLORS[level] ?? "bg-gray-100 text-gray-800";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {level}
    </span>
  );
}
