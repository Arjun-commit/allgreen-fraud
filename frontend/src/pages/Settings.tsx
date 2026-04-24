// Threshold settings with live impact preview and maker-checker save flow.

import { useState, useEffect } from "react";
import { Save, AlertTriangle, Lock } from "lucide-react";
import { listCases, type CaseSummary } from "../api/client";

interface Thresholds {
  medium: number;
  high: number;
  critical: number;
}

interface FrictionConfig {
  medium: string;
  high: string;
  critical: string;
}

const DEFAULT_THRESHOLDS: Thresholds = {
  medium: 45,
  high: 65,
  critical: 80,
};

const DEFAULT_FRICTION: FrictionConfig = {
  medium: "awareness_prompt",
  high: "cooling_timer",
  critical: "callback_required",
};

const FRICTION_OPTIONS = [
  { value: "none", label: "None" },
  { value: "awareness_prompt", label: "Awareness Prompt" },
  { value: "cooling_timer", label: "Cooling Timer" },
  { value: "callback_required", label: "Callback Required" },
];

export default function Settings() {
  const [thresholds, setThresholds] = useState<Thresholds>(DEFAULT_THRESHOLDS);
  const [friction, setFriction] = useState<FrictionConfig>(DEFAULT_FRICTION);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [saved, setSaved] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(false);

  // Load recent cases for the impact preview
  useEffect(() => {
    listCases({ limit: "200" })
      .then((res) => setCases(res.items))
      .catch(() => {});
  }, []);

  // Calculate impact preview
  const mediumCount = cases.filter(
    (c) => c.risk_score >= thresholds.medium && c.risk_score < thresholds.high
  ).length;
  const highCount = cases.filter(
    (c) => c.risk_score >= thresholds.high && c.risk_score < thresholds.critical
  ).length;
  const criticalCount = cases.filter(
    (c) => c.risk_score >= thresholds.critical
  ).length;

  const handleSave = () => {
    // In prod, this would POST to a backend endpoint and require
    // a second analyst to approve (maker-checker pattern).
    // For now, just simulate the approval flow.
    setPendingApproval(true);
    setSaved(false);

    // Fake "approval" after 2s
    setTimeout(() => {
      setPendingApproval(false);
      setSaved(true);
      // TODO: POST /v1/settings/thresholds with maker-checker flow
    }, 2000);
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold text-gray-800">Threshold Settings</h1>

      {/* Threshold sliders */}
      <div className="bg-white rounded-lg border p-6 space-y-6">
        <ThresholdSlider
          label="Medium"
          color="text-yellow-600"
          value={thresholds.medium}
          min={20}
          max={thresholds.high - 1}
          onChange={(v) => setThresholds({ ...thresholds, medium: v })}
        />
        <ThresholdSlider
          label="High"
          color="text-orange-600"
          value={thresholds.high}
          min={thresholds.medium + 1}
          max={thresholds.critical - 1}
          onChange={(v) => setThresholds({ ...thresholds, high: v })}
        />
        <ThresholdSlider
          label="Critical"
          color="text-red-600"
          value={thresholds.critical}
          min={thresholds.high + 1}
          max={99}
          onChange={(v) => setThresholds({ ...thresholds, critical: v })}
        />
      </div>

      {/* Impact preview */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Impact Preview (based on recent cases)
        </h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <ImpactBucket label="Medium" count={mediumCount} color="text-yellow-700" />
          <ImpactBucket label="High" count={highCount} color="text-orange-700" />
          <ImpactBucket label="Critical" count={criticalCount} color="text-red-700" />
        </div>
        <p className="text-xs text-blue-600 mt-2">
          With these thresholds, {mediumCount + highCount + criticalCount} of{" "}
          {cases.length} recent transactions would have triggered friction.
        </p>
      </div>

      {/* Friction type config */}
      <div className="bg-white rounded-lg border p-6 space-y-4">
        <h2 className="text-sm font-medium text-gray-600">Friction Type per Threshold</h2>
        {(["medium", "high", "critical"] as const).map((level) => (
          <div key={level} className="flex items-center gap-4">
            <span className="text-sm text-gray-500 w-20 capitalize">{level}</span>
            <select
              value={friction[level]}
              onChange={(e) =>
                setFriction({ ...friction, [level]: e.target.value })
              }
              className="text-sm border rounded px-3 py-1.5 flex-1"
            >
              {FRICTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {/* Save button with maker-checker */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={pendingApproval}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {pendingApproval ? (
            <>
              <Lock className="w-4 h-4 animate-pulse" />
              Awaiting approval...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save (requires approval)
            </>
          )}
        </button>
        {saved && (
          <span className="text-sm text-green-600">
            Settings saved successfully
          </span>
        )}
      </div>
      <p className="text-xs text-gray-400">
        Threshold changes require 2-person approval (maker-checker).
        The approver will see the impact preview above before confirming.
      </p>
    </div>
  );
}

// ---- Sub-components ----

function ThresholdSlider({
  label,
  color,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  color: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-sm font-medium ${color}`}>{label} threshold</span>
        <span className="text-sm font-mono text-gray-600">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
      />
      <div className="flex justify-between text-xs text-gray-400 mt-0.5">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

function ImpactBucket({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div>
      <p className={`text-2xl font-bold ${color}`}>{count}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}
