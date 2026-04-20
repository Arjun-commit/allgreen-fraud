/**
 * Shows what friction was applied to a session and how the user responded.
 */

import { AlertTriangle, Clock, Phone, CheckCircle } from "lucide-react";

interface FrictionLogProps {
  frictionType: string | null;
  userResponse: string | null;
}

const FRICTION_META: Record<string, { label: string; icon: typeof AlertTriangle; cls: string }> = {
  awareness_prompt: { label: "Awareness Prompt", icon: AlertTriangle, cls: "text-yellow-600" },
  cooling_timer: { label: "Cooling Timer", icon: Clock, cls: "text-orange-600" },
  callback_required: { label: "Callback Required", icon: Phone, cls: "text-red-600" },
};

const RESPONSE_META: Record<string, { label: string; cls: string }> = {
  proceeded: { label: "User proceeded", cls: "text-gray-600" },
  abandoned: { label: "User abandoned", cls: "text-green-600" },
  confirmed_scam: { label: "User confirmed scam", cls: "text-red-600" },
};

export default function FrictionLog({ frictionType, userResponse }: FrictionLogProps) {
  if (!frictionType || frictionType === "none") {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <CheckCircle className="w-4 h-4" />
        No friction applied
      </div>
    );
  }

  const meta = FRICTION_META[frictionType];
  const responseMeta = userResponse ? RESPONSE_META[userResponse] : null;

  if (!meta) {
    return <div className="text-sm text-gray-500">Friction: {frictionType}</div>;
  }

  const Icon = meta.icon;

  return (
    <div className="space-y-1">
      <div className={`flex items-center gap-2 text-sm font-medium ${meta.cls}`}>
        <Icon className="w-4 h-4" />
        {meta.label}
      </div>
      {responseMeta && (
        <div className={`text-xs ${responseMeta.cls} ml-6`}>
          {responseMeta.label}
        </div>
      )}
    </div>
  );
}
