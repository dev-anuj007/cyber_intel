export type PriorityTier =
  | "tier_1_critical"
  | "tier_2_high"
  | "tier_3_medium"
  | "tier_4_low";

export type SignalSeverity = "critical" | "high" | "medium" | "low";

export interface SecuritySignal {
  name: string;
  severity: SignalSeverity;
  category: string;
  evidence: string;
}

export interface Asset {
  ip: string | null;
  port: number | null;
  hostname: string | null;
}

export interface ScoreHistoryItem {
  id: number;
  account_key: string;
  version: number;
  score: number;
  priority_tier: PriorityTier;
  key_risks: string[];
  suggested_outreach: string;
  score_rationale?: string;
  model_version: string;
  model_name: string;
  tokens_used: {
    input?: number;
    output?: number;
  };
  latency_ms: number;
  cost_usd: number;
  timestamp: string;
}

export interface ScoreHistoryResponse {
  account_key: string;
  total_versions: number;
  history: ScoreHistoryItem[];
}

export interface Account {
  account_key: string;
  version?: string;
  domain?: string;
  domains: string[];
  priority_tier?: PriorityTier;
  critical_signals_count?: number;
  high_signals_count?: number;
  medium_signals_count?: number;
  low_signals_count?: number;
  total_signals_count?: number;
  total_assets?: number;
  total_subdomains?: number;
  assets: Asset[];
  ips: string[];
  hostnames: string[];
  ports: number[];
  products: string[];
  cloud_providers: string[];
  signals: SecuritySignal[];
  ai_score?: number | null;
  latest_score?: ScoreHistoryItem | null;
}

export interface AccountScore {
  account_key: string;
  account: Account;
  score: number;
  score_rationale?: string;
  priority_tier: PriorityTier;
  key_risks: string[];
  suggested_outreach: string;
  model_version: string;
  timestamp: string;
  tokens_used: {
    input: number;
    output: number;
  };
  latency_ms: number;
  cost_usd: number;
  version?: number;
}

export interface SummaryStats {
  total_accounts: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
}

export interface LLMStats {
  total_calls: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  trace_file: string;
}

export interface UserProfile {
  id: number;
  email: string;
  has_api_key: boolean;
  api_key_preview?: string | null;
  created_at?: string | null;
}

export interface AuthResponse {
  token: string;
  user: UserProfile;
}

export type AuthModalMode = "signin" | "signup";

export interface PromptTemplateInfo {
  filename: string;
  name: string;
  version: string;
  type: string;
  template: string;
}

export interface EvalPrediction {
  expected_tier: string;
  predicted_tier: string;
  expected_score: number;
  predicted_score: number;
  tier_match: boolean;
  score_error: number;
  score_tier_consistent: boolean;
  key_risks: string[];
  suggested_outreach: string;
}

export interface EvalBenchmarkSample {
  account_key: string;
  expected_tier: string;
  expected_score: number;
  reasoning?: string;
  domains?: string[];
  critical_signals?: string[];
}

export interface TierMetric {
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
  tp: number;
  fp: number;
  fn: number;
}

export interface EvalResultData {
  prompt_version: string;
  total: number;
  tier_accuracy: number;
  macro_f1: number;
  weighted_f1: number;
  critical_threat_recall: number;
  score_tier_consistency: number;
  score_mae: number;
  score_rmse: number;
  within_5_points: number;
  within_5_points_pct: number;
  tier_metrics: Record<string, TierMetric>;
  predictions: EvalPrediction[];
}

export interface EvalRunResponse {
  success: boolean;
  results: EvalResultData;
  saved_file: string;
  timestamp: string;
}

export interface EvalComparisonMetric {
  name: string;
  val_a: number;
  val_b: number;
  delta: number;
  delta_str: string;
  improved: boolean;
  status: "improved" | "regressed" | "unchanged";
  is_pct: boolean;
  lower_is_better: boolean;
}

export interface EvalComparisonData {
  prompt_a: string;
  prompt_b: string;
  metrics: EvalComparisonMetric[];
  tier_comparisons: Record<string, {
    precision_a: number;
    precision_b: number;
    recall_a: number;
    recall_b: number;
    f1_a: number;
    f1_b: number;
    support: number;
  }>;
  prediction_diffs: Array<{
    index: number;
    expected_tier: string;
    expected_score: number;
    pred_tier_a: string;
    pred_score_a: number;
    pred_tier_b: string;
    pred_score_b: number;
  }>;
}

export interface EvalCompareResponse {
  success: boolean;
  comparison: EvalComparisonData;
  results_a: EvalResultData;
  results_b: EvalResultData;
  timestamp: string;
}

export interface EvalHistoryItem {
  filename: string;
  timestamp: string;
  prompt_version: string;
  total: number;
  tier_accuracy: number;
  macro_f1: number;
  weighted_f1: number;
  score_mae: number;
  within_5_points_pct: number;
}

export type JobStatusType = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface BackgroundJobSummary {
  job_id: string;
  job_type: string;
  title: string;
  status: JobStatusType;
  progress_current: number;
  progress_total: number;
  progress_percent: number;
  retry_count: number;
  max_retries: number;
  metadata: {
    assets_discovered_count?: number;
    signals_detected_count?: number;
    domains_count?: number;
    scan_depth?: string;
    [key: string]: any;
  };
  error_message?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
}

export interface BackgroundJobDetail extends BackgroundJobSummary {
  payload: Record<string, any>;
  results?: any[] | null;
}

export interface BackgroundJobListResponse {
  total: number;
  skip: number;
  limit: number;
  items: BackgroundJobSummary[];
}

export interface JobSubmitResponse {
  success: boolean;
  job_id: string;
  job_type: string;
  status: JobStatusType;
  message: string;
  trace_id?: string | null;
}

export interface ScannerEngineInfo {
  id: string;
  name: string;
  description: string;
  badge: string;
  icon: string;
}

export interface CrawlerSubmitOptions {
  domains: string[];
  pipeline_name?: string;
  scan_depth?: "quick" | "standard" | "deep";
  scanner_type?: string;
  enable_subdomains?: boolean;
  custom_ports?: number[];
  save_to_database?: boolean;
}


