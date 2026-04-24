// API client. Dev uses Vite proxy; prod serves from same origin.

const BASE = "/v1";

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, v);
      }
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

// ---- Cases ----

export interface CaseSummary {
  case_id: string;
  transaction_id: string;
  session_id: string;
  user_id_masked: string;
  amount: number;
  currency: string;
  transfer_type: string;
  risk_score: number;
  risk_level: string;
  friction_applied: string | null;
  status: string;
  created_at: string;
}

export interface CaseDetailData extends CaseSummary {
  behavioral_score: number | null;
  context_score: number | null;
  shap_factors: { feature: string; direction: string; magnitude: number }[];
  session_duration_ms: number | null;
  is_new_payee: boolean;
  payee_account_masked: string | null;
  device_hash: string | null;
  ip_address: string | null;
  friction_user_response: string | null;
  analyst_notes: string | null;
  assigned_to: string | null;
  resolved_at: string | null;
}

export interface CaseListResponse {
  items: CaseSummary[];
  page: number;
  limit: number;
  total: number;
}

export function listCases(params?: {
  status?: string;
  min_score?: string;
  page?: string;
  limit?: string;
}): Promise<CaseListResponse> {
  return get("/cases", params);
}

export function getCase(caseId: string): Promise<CaseDetailData> {
  return get(`/cases/${caseId}`);
}

export function resolveCase(
  caseId: string,
  outcome: string,
  notes?: string
): Promise<{ case_id: string; status: string; outcome: string }> {
  return post(`/cases/${caseId}/resolve`, { outcome, notes });
}

// ---- Analytics ----

export interface ModelPerformance {
  period: string;
  lstm: { auc: number | null; precision: number | null; recall: number | null };
  xgboost: { auc: number | null; precision: number | null; recall: number | null };
  ensemble: { auc: number | null };
  friction_effectiveness: {
    soft_friction_abandon_rate: number | null;
    hard_block_scam_confirmation_rate: number | null;
  };
}

export interface ScoreDistribution {
  buckets: string[];
  current_week: number[];
  last_week: number[];
}

export function getModelPerformance(): Promise<ModelPerformance> {
  return get("/analytics/model-performance");
}

export function getScoreDistribution(): Promise<ScoreDistribution> {
  return get("/analytics/score-distribution");
}

// ---- Health ----

export function getHealth(): Promise<{ status: string; version: string }> {
  return get("/health".replace("/v1", ""));
}
