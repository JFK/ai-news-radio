export type StepName =
  | "collection"
  | "factcheck"
  | "analysis"
  | "script"
  | "voice"
  | "video"
  | "publish";

export type StepStatus =
  | "pending"
  | "running"
  | "needs_approval"
  | "approved"
  | "rejected";

export type EpisodeStatus = "draft" | "in_progress" | "completed" | "published";

export interface PipelineStep {
  id: number;
  episode_id: number;
  step_name: StepName;
  status: StepStatus;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface Episode {
  id: number;
  title: string;
  status: EpisodeStatus;
  created_at: string;
  published_at: string | null;
  audio_path: string | null;
  video_path: string | null;
  pipeline_steps: PipelineStep[];
}

export interface NewsItem {
  id: number;
  episode_id: number;
  title: string;
  summary: string | null;
  source_url: string;
  source_name: string;
  fact_check_status: string | null;
  fact_check_score: number | null;
  fact_check_details: string | null;
  reference_urls: string[] | null;
  analysis_data: Record<string, unknown> | null;
  script_text: string | null;
  created_at: string;
}

export interface AnalysisData {
  background?: string;
  why_now?: string;
  perspectives?: Array<{ viewpoint?: string; description?: string }>;
  data_verification?: string;
  impact_assessment?: string;
  severity?: string;
  topics?: string[];
}

export interface EpisodeListResponse {
  episodes: Episode[];
  total: number;
}

export interface CostByProvider {
  provider: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  request_count: number;
}

export interface CostByStep {
  step_name: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  request_count: number;
}

export interface CostStatsResponse {
  by_provider: CostByProvider[];
  by_step: CostByStep[];
  total_cost_usd: number;
  total_requests: number;
}

export interface EpisodeCostResponse {
  episode_id: number;
  by_step: CostByStep[];
  total_cost_usd: number;
  total_requests: number;
}

export interface ArticleInput {
  title: string;
  summary?: string;
  source_url: string;
  source_name: string;
}

export interface ModelPricing {
  id: number;
  model_prefix: string;
  provider: string;
  input_price_per_1m: number;
  output_price_per_1m: number;
  created_at: string;
  updated_at: string;
}
