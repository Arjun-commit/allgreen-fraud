/**
 * Dashboard metric card — top row of the alert feed.
 */

import type { ReactNode } from "react";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  color?: string; // tailwind text color class
}

export default function MetricCard({ title, value, icon, color = "text-gray-900" }: MetricCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-3">
      <div className="p-2 rounded-lg bg-gray-50">{icon}</div>
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wide">{title}</p>
        <p className={`text-2xl font-semibold ${color}`}>{value}</p>
      </div>
    </div>
  );
}
