/**
 * Model Analytics page.
 *
 * Blueprint spec:
 *  - AUC/Precision/Recall display
 *  - Friction effectiveness stats
 *  - Score distribution histogram (current week vs last week)
 *  - Model drift alert placeholder
 */

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { TrendingUp, AlertCircle } from "lucide-react";
import {
  getModelPerformance,
  getScoreDistribution,
  type ModelPerformance,
  type ScoreDistribution,
} from "../api/client";

export default function Analytics() {
  const [perf, setPerf] = useState<ModelPerformance | null>(null);
  const [dist, setDist] = useState<ScoreDistribution | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getModelPerformance(), getScoreDistribution()])
      .then(([p, d]) => {
        setPerf(p);
        setDist(d);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-6 text-gray-400">Loading analytics...</div>;
  }

  // Build histogram chart data
  const histData = dist
    ? dist.buckets.map((bucket, i) => ({
        bucket,
        "This Week": dist.current_week[i],
        "Last Week": dist.last_week[i],
      }))
    : [];

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-xl font-semibold text-gray-800">Model Analytics</h1>

      {/* Model performance cards */}
      <div className="grid grid-cols-3 gap-4">
        <ModelCard title="LSTM (Behavioral)" metrics={perf?.lstm} />
        <ModelCard title="XGBoost (Context)" metrics={perf?.xgboost} />
        <div className="bg-white rounded-lg border p-4">
          <h3 className="text-sm text-gray-500 mb-2">Ensemble</h3>
          <MetricRow label="AUC" value={perf?.ensemble?.auc} />
          <div className="mt-3 pt-3 border-t">
            <h4 className="text-xs text-gray-500 uppercase mb-1">Friction Effectiveness</h4>
            <MetricRow
              label="Soft abandon rate"
              value={perf?.friction_effectiveness?.soft_friction_abandon_rate}
              format="pct"
            />
            <MetricRow
              label="Hard block confirm rate"
              value={perf?.friction_effectiveness?.hard_block_scam_confirmation_rate}
              format="pct"
            />
          </div>
        </div>
      </div>

      {/* Model drift alert placeholder */}
      <DriftAlert />

      {/* Score distribution histogram */}
      <div className="bg-white rounded-lg border p-4">
        <h2 className="text-sm font-medium text-gray-600 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Score Distribution — This Week vs Last Week
        </h2>
        {histData.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={histData}>
              <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="This Week" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Last Week" fill="#d1d5db" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-gray-400">No distribution data available</p>
        )}
      </div>

      {/* TODO: AUC over time line chart — needs historical metrics storage */}
      <div className="bg-white rounded-lg border p-4">
        <h2 className="text-sm font-medium text-gray-600 mb-2">
          AUC / Precision / Recall Over Time
        </h2>
        <p className="text-xs text-gray-400">
          Coming soon — requires historical metrics pipeline (MLflow integration in phase 6)
        </p>
        <div className="h-40 flex items-center justify-center bg-gray-50 rounded mt-2 text-gray-300 text-sm">
          Line chart placeholder
        </div>
      </div>
    </div>
  );
}

// ---- Sub-components ----

function ModelCard({
  title,
  metrics,
}: {
  title: string;
  metrics?: { auc: number | null; precision: number | null; recall: number | null } | null;
}) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <h3 className="text-sm text-gray-500 mb-2">{title}</h3>
      <MetricRow label="AUC" value={metrics?.auc} />
      <MetricRow label="Precision" value={metrics?.precision} />
      <MetricRow label="Recall" value={metrics?.recall} />
    </div>
  );
}

function MetricRow({
  label,
  value,
  format = "decimal",
}: {
  label: string;
  value?: number | null;
  format?: "decimal" | "pct";
}) {
  const formatted =
    value != null
      ? format === "pct"
        ? `${(value * 100).toFixed(1)}%`
        : value.toFixed(4)
      : "—";

  const color =
    value != null
      ? value > 0.85
        ? "text-green-600"
        : value > 0.7
        ? "text-yellow-600"
        : "text-red-600"
      : "text-gray-400";

  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`text-sm font-medium ${color}`}>{formatted}</span>
    </div>
  );
}

function DriftAlert() {
  // Placeholder — in prod this would check if AUC dropped >5% in 7 days
  const hasDrift = false;

  if (!hasDrift) return null;

  return (
    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-medium text-orange-800">Model Drift Detected</p>
        <p className="text-xs text-orange-600 mt-1">
          Ensemble AUC has dropped by more than 5% in the last 7 days.
          Consider retraining with recent data.
        </p>
      </div>
    </div>
  );
}
