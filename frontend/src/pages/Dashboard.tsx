/**
 * Live Alert Feed — main dashboard page.
 *
 * Blueprint spec:
 *  - Top row: 4 metric cards (Active Sessions, Flagged Today, Friction Applied, Confirmed Fraud)
 *  - Main: real-time table of flagged transactions, auto-refreshes every 10s
 *  - Clickable rows → CaseDetail
 */

import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";
import { listCases, type CaseSummary, type CaseListResponse } from "../api/client";
import MetricCard from "../components/MetricCard";
import RiskBadge from "../components/RiskBadge";

const REFRESH_INTERVAL = 10_000; // 10s auto-refresh

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<CaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const fetchCases = useCallback(async () => {
    try {
      const params: Record<string, string> = { page: String(page), limit: "20" };
      if (statusFilter) params.status = statusFilter;
      const result = await listCases(params);
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  // Initial load + auto-refresh
  useEffect(() => {
    fetchCases();
    const interval = setInterval(fetchCases, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchCases]);

  const cases = data?.items ?? [];

  // Compute metric cards from current data
  const activeSessions = cases.filter((c) => c.status === "open" || c.status === "investigating").length;
  const flaggedToday = cases.length; // TODO: filter by today's date when real data
  const frictionApplied = cases.filter((c) => c.friction_applied && c.friction_applied !== "none").length;
  const confirmedFraud = cases.filter((c) => c.status === "closed_fraud").length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-800">Live Alert Feed</h1>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Auto-refreshing every 10s
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          title="Active Sessions"
          value={activeSessions}
          icon={<Activity className="w-5 h-5 text-blue-500" />}
        />
        <MetricCard
          title="Flagged Today"
          value={flaggedToday}
          icon={<AlertTriangle className="w-5 h-5 text-yellow-500" />}
        />
        <MetricCard
          title="Friction Applied"
          value={frictionApplied}
          icon={<ShieldAlert className="w-5 h-5 text-orange-500" />}
        />
        <MetricCard
          title="Confirmed Fraud"
          value={confirmedFraud}
          icon={<ShieldCheck className="w-5 h-5 text-red-500" />}
          color="text-red-600"
        />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-500">Status:</label>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="text-sm border rounded px-2 py-1"
        >
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="investigating">Investigating</option>
          <option value="closed_fraud">Closed (Fraud)</option>
          <option value="closed_legit">Closed (Legit)</option>
        </select>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-50 text-red-700 px-4 py-2 rounded text-sm">
          {error} — showing cached data if available
        </div>
      )}

      {/* Alert table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Time</th>
              <th className="px-4 py-3 text-left">User</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-left">Type</th>
              <th className="px-4 py-3 text-left">Risk Score</th>
              <th className="px-4 py-3 text-left">Friction</th>
              <th className="px-4 py-3 text-left">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && cases.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : cases.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No cases found
                </td>
              </tr>
            ) : (
              cases.map((c) => (
                <CaseRow
                  key={c.case_id}
                  caseData={c}
                  onClick={() => navigate(`/cases/${c.case_id}`)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > data.limit && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            Showing {(page - 1) * data.limit + 1}–{Math.min(page * data.limit, data.total)} of{" "}
            {data.total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * data.limit >= data.total}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Alert table row ----

function CaseRow({ caseData: c, onClick }: { caseData: CaseSummary; onClick: () => void }) {
  const riskPct = Math.min(100, c.risk_score);

  return (
    <tr
      onClick={onClick}
      className="hover:bg-gray-50 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
        {new Date(c.created_at).toLocaleString()}
      </td>
      <td className="px-4 py-3 font-mono text-xs">{c.user_id_masked}</td>
      <td className="px-4 py-3 text-right font-medium">
        ${c.amount.toLocaleString()}
      </td>
      <td className="px-4 py-3 text-xs text-gray-600">{c.transfer_type}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-20 h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${riskPct}%`,
                backgroundColor:
                  riskPct < 45
                    ? "#22c55e"
                    : riskPct < 65
                    ? "#eab308"
                    : riskPct < 80
                    ? "#f97316"
                    : "#ef4444",
              }}
            />
          </div>
          <span className="text-xs text-gray-600 w-8">{c.risk_score.toFixed(0)}</span>
          <RiskBadge level={c.risk_level} />
        </div>
      </td>
      <td className="px-4 py-3 text-xs text-gray-600">
        {c.friction_applied ?? "—"}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={c.status} />
      </td>
    </tr>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    open: "bg-blue-100 text-blue-700",
    investigating: "bg-purple-100 text-purple-700",
    closed_fraud: "bg-red-100 text-red-700",
    closed_legit: "bg-green-100 text-green-700",
  };
  const cls = styles[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}
