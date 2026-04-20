/**
 * Case Detail — per-session drill-down page.
 *
 * Blueprint spec:
 *  - Risk score breakdown (behavioral vs context gauges)
 *  - Session timeline
 *  - Top SHAP factors bar chart
 *  - Transaction details
 *  - Friction log
 *  - Analyst action buttons
 */

import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, User, Monitor, Globe, Clock, DollarSign } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { getCase, resolveCase, type CaseDetailData } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import RiskGauge from "../components/RiskGauge";
import SessionTimeline from "../components/SessionTimeline";
import FrictionLog from "../components/FrictionLog";

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<CaseDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    getCase(caseId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [caseId]);

  const handleResolve = async (outcome: string) => {
    if (!caseId) return;
    setResolving(true);
    try {
      await resolveCase(caseId, outcome, notes || undefined);
      // Refresh
      const updated = await getCase(caseId);
      setData(updated);
    } catch {
      // TODO: show error toast
    } finally {
      setResolving(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-gray-400">Loading case...</div>;
  }
  if (!data) {
    return <div className="p-6 text-red-500">Case not found</div>;
  }

  // SHAP chart data
  const shapData = (data.shap_factors || []).map((f) => ({
    name: f.feature.replace(/_/g, " "),
    value: f.magnitude,
    direction: f.direction,
  }));

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Back nav + header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate("/")}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <ArrowLeft className="w-5 h-5 text-gray-500" />
        </button>
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            Case {caseId?.slice(0, 8)}...
            <RiskBadge level={data.risk_level} />
          </h1>
          <p className="text-xs text-gray-400">
            {new Date(data.created_at).toLocaleString()} — {data.session_id}
          </p>
        </div>
      </div>

      {/* Score breakdown gauges */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border p-4 flex flex-col items-center">
          <RiskGauge label="Overall Risk" value={data.risk_score / 100} size={140} />
          <span className="mt-2 text-sm font-medium">{data.risk_score.toFixed(1)}/100</span>
        </div>
        <div className="bg-white rounded-lg border p-4 flex flex-col items-center">
          <RiskGauge
            label="Behavioral"
            value={data.behavioral_score ?? 0}
            size={140}
          />
          <span className="mt-2 text-sm text-gray-500">LSTM anomaly score</span>
        </div>
        <div className="bg-white rounded-lg border p-4 flex flex-col items-center">
          <RiskGauge
            label="Context"
            value={data.context_score ?? 0}
            size={140}
          />
          <span className="mt-2 text-sm text-gray-500">XGBoost fraud prob</span>
        </div>
      </div>

      {/* Session timeline */}
      <div className="bg-white rounded-lg border p-4">
        <h2 className="text-sm font-medium text-gray-600 mb-3">Session Activity Timeline</h2>
        <SessionTimeline durationMs={data.session_duration_ms ?? 60000} />
        <p className="text-xs text-gray-400 mt-2">
          Red zones indicate periods of inactivity (possible coached pauses)
        </p>
      </div>

      {/* SHAP factors */}
      {shapData.length > 0 && (
        <div className="bg-white rounded-lg border p-4">
          <h2 className="text-sm font-medium text-gray-600 mb-3">
            Top Risk Factors (SHAP)
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={shapData} layout="vertical" margin={{ left: 120 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11 }}
                width={115}
              />
              <Tooltip
                formatter={(val: number, _name: string, props: { payload: { direction: string } }) => [
                  val.toFixed(4),
                  props.payload.direction === "increases_risk"
                    ? "Increases risk"
                    : "Decreases risk",
                ]}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {shapData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.direction === "increases_risk" ? "#ef4444" : "#22c55e"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Transaction + user details */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border p-4 space-y-3">
          <h2 className="text-sm font-medium text-gray-600">Transaction Details</h2>
          <Detail icon={<DollarSign className="w-4 h-4" />} label="Amount">
            ${data.amount.toLocaleString()} {data.currency}
          </Detail>
          <Detail icon={<Globe className="w-4 h-4" />} label="Type">
            {data.transfer_type}
          </Detail>
          <Detail label="New Payee">
            {data.is_new_payee ? (
              <span className="text-orange-600 font-medium">Yes</span>
            ) : (
              "No"
            )}
          </Detail>
          <Detail label="Payee Account">{data.payee_account_masked ?? "—"}</Detail>
        </div>

        <div className="bg-white rounded-lg border p-4 space-y-3">
          <h2 className="text-sm font-medium text-gray-600">Session Info</h2>
          <Detail icon={<User className="w-4 h-4" />} label="User">
            {data.user_id_masked}
          </Detail>
          <Detail icon={<Monitor className="w-4 h-4" />} label="Device">
            {data.device_hash ?? "—"}
          </Detail>
          <Detail icon={<Globe className="w-4 h-4" />} label="IP">
            {data.ip_address ?? "—"}
          </Detail>
          <Detail icon={<Clock className="w-4 h-4" />} label="Duration">
            {data.session_duration_ms
              ? `${(data.session_duration_ms / 1000).toFixed(0)}s`
              : "—"}
          </Detail>
        </div>
      </div>

      {/* Friction log */}
      <div className="bg-white rounded-lg border p-4">
        <h2 className="text-sm font-medium text-gray-600 mb-2">Friction Applied</h2>
        <FrictionLog
          frictionType={data.friction_applied}
          userResponse={data.friction_user_response}
        />
      </div>

      {/* Analyst actions */}
      <div className="bg-white rounded-lg border p-4 space-y-3">
        <h2 className="text-sm font-medium text-gray-600">Analyst Actions</h2>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add investigation notes..."
          className="w-full border rounded px-3 py-2 text-sm h-20 resize-none"
        />
        <div className="flex gap-2">
          <button
            onClick={() => handleResolve("confirmed_fraud")}
            disabled={resolving}
            className="px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700 disabled:opacity-50"
          >
            Confirm Fraud
          </button>
          <button
            onClick={() => handleResolve("legitimate")}
            disabled={resolving}
            className="px-4 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
          >
            Mark Legitimate
          </button>
          <button
            onClick={() => handleResolve("escalated")}
            disabled={resolving}
            className="px-4 py-2 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50"
          >
            Escalate
          </button>
        </div>
      </div>
    </div>
  );
}

// Small helper for key-value detail rows
function Detail({
  icon,
  label,
  children,
}: {
  icon?: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {icon && <span className="text-gray-400">{icon}</span>}
      <span className="text-gray-500 w-28">{label}</span>
      <span className="text-gray-800">{children}</span>
    </div>
  );
}
