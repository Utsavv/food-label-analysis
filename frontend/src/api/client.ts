// API client + shared types. All calls go through /api (proxied to the backend).

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

// ---------- Types ----------

export interface Source {
  id: number;
  source_type: string;
  source_url: string;
  is_active: boolean;
  scrape_frequency: string;
  last_checked_at: string | null;
}

export interface Product {
  id: number;
  brand: string;
  name: string;
  category: string;
  country: string;
  status: string;
  notes: string | null;
  created_at: string;
  sources: Source[];
  latest_version_id?: number | null;
  latest_version_at?: string | null;
  latest_significance?: number | null;
}

export interface NutrientValue {
  name: string;
  amount: number | null;
  unit: string | null;
  basis: string;
  daily_value_percent?: number | null;
  evidence?: string | null;
}

export interface IngredientEntry {
  name_raw: string;
  name_normalized: string;
  position: number;
  is_additive: boolean;
  is_sweetener: boolean;
  is_preservative: boolean;
  category: string | null;
}

export interface StructuredLabel {
  serving_size: { value: string | null };
  servings_per_container: { value: number | null };
  nutrition: NutrientValue[];
  ingredients: IngredientEntry[];
  allergens: { name: string; presence_type: string }[];
  certifications: string[];
  claims: { claim_text: string; normalized_claim: string; claim_type: string | null }[];
  warnings: string[];
  fssai_license: { value: string | null };
  veg_status: { value: string | null };
  manufacturer_info: { value: string | null };
  country_of_origin: { value: string | null };
  overall_confidence: number;
}

export interface LabelVersion {
  id: number;
  product_id: number;
  version_number: number;
  version_hash: string;
  effective_detected_at: string;
  raw_text: string;
  structured_json: StructuredLabel;
  confidence_score: number;
  created_at: string;
}

export interface LabelVersionSummary {
  id: number;
  version_number: number;
  version_hash: string;
  effective_detected_at: string;
  confidence_score: number;
}

export interface DiffItem {
  type: string;
  field: string;
  old_value: unknown;
  new_value: unknown;
  unit?: string;
  percent_change?: number | null;
  detail: string;
  significance: number;
  significance_level: string;
  presence_type?: string;
  is_sweetener?: boolean;
  is_preservative?: boolean;
  is_additive?: boolean;
}

export interface AIAnalysis {
  id: number;
  analysis_type: string;
  prompt_version: string;
  model_name: string;
  analysis_json: Record<string, unknown>;
  plain_english_summary: string;
  confidence_score: number;
  created_at: string;
}

export interface Comparison {
  id: number;
  product_id: number;
  old_label_version_id: number;
  new_label_version_id: number;
  diff_json: { items: DiffItem[]; overall_score: number; overall_level: string };
  significance_score: number;
  created_at: string;
  analyses: AIAnalysis[];
}

export interface ScrapeRun {
  id: number;
  product_id: number;
  status: string;
  trigger: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface DashboardStats {
  tracked_products: number;
  changed_this_week: number;
  high_significance_changes: number;
  failed_runs_this_week: number;
}

export interface CheckNowResult {
  run_id: number;
  status: string;
  new_version_created: boolean;
  label_version_id: number | null;
  comparison_id: number | null;
  significance_score: number | null;
  message: string;
}

export interface IngredientExplanation {
  ingredient_name: string;
  plain_english_meaning: string;
  common_use: string;
  commonness: string;
  health_context: string;
  confidence: number;
  model_name: string;
  prompt_version: string;
}

// ---------- Endpoints ----------

export const api = {
  dashboardStats: () => request<DashboardStats>('/dashboard/stats'),
  listProducts: (params?: { category?: string; status?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString();
    return request<Product[]>(`/products${q ? `?${q}` : ''}`);
  },
  getProduct: (id: number) => request<Product>(`/products/${id}`),
  createProduct: (body: Record<string, unknown>) =>
    request<Product>('/products', { method: 'POST', body: JSON.stringify(body) }),
  checkNow: (id: number) =>
    request<CheckNowResult>(`/products/${id}/check-now`, { method: 'POST' }),
  listVersions: (productId: number) =>
    request<LabelVersionSummary[]>(`/products/${productId}/label-versions`),
  getVersion: (versionId: number) => request<LabelVersion>(`/label-versions/${versionId}`),
  listComparisons: (productId: number) =>
    request<Comparison[]>(`/products/${productId}/comparisons`),
  getComparison: (id: number) => request<Comparison>(`/comparisons/${id}`),
  listRuns: (params?: { status?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString();
    return request<ScrapeRun[]>(`/runs${q ? `?${q}` : ''}`);
  },
  explainIngredient: (name: string, category: string) =>
    request<IngredientExplanation>(
      `/ingredients/explain?name=${encodeURIComponent(name)}&category=${encodeURIComponent(category)}`,
    ),
};
