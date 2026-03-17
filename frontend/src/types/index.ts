export type StepName =
  | "collection"
  | "factcheck"
  | "analysis"
  | "script"
  | "voice"
  | "video";

export type StepStatus =
  | "pending"
  | "running"
  | "needs_approval"
  | "approved"
  | "rejected";

export type EpisodeStatus = "draft" | "in_progress" | "completed";

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
  drive_file_id: string | null;
  drive_file_url: string | null;
  shorts_enabled: boolean;
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
  script_mode: string | null;
  script_data: Record<string, unknown> | null;
  group_id: number | null;
  is_group_primary: boolean | null;
  excluded: boolean;
  excluded_at_step: string | null;
  created_at: string;
}

export interface AnalysisData {
  background?: string;
  why_now?: string;
  perspectives?: Array<{ standpoint?: string; argument?: string; basis?: string }>;
  data_validation?: string;
  impact?: string;
  uncertainties?: string;
  source_comparison?: string;
  severity?: string;
  topics?: string[];
  recommended_format?: "explainer" | "solo";
  format_reason?: string;
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

export interface Pronunciation {
  id: number;
  surface: string;
  reading: string;
  priority: number;
  created_at: string;
}

export interface PromptSummary {
  key: string;
  name: string;
  active_version: number | null;
  has_custom: boolean;
  content_preview: string;
}

export interface PromptTemplateVersion {
  id: number;
  key: string;
  name: string;
  content: string;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PromptHistory {
  key: string;
  name: string;
  default_content: string;
  active_version: number | null;
  versions: PromptTemplateVersion[];
}

export interface DriveExportResponse {
  episode_id: number;
  drive_file_id: string;
  drive_file_url: string;
  source_text_length: number;
  input_tokens: number;
  output_tokens: number;
}

export interface SpeakerProfile {
  id: number;
  name: string;
  role: string;
  voice_name: string;
  voice_instructions: string;
  avatar_path: string | null;
  avatar_position: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ShortsVideoMetadata {
  title?: string;
  description?: string;
  hashtags?: string[];
}

export interface ShortsVideo {
  news_item_id: number;
  video_path: string;
  duration_seconds: number;
  mode: string;
  provider: string;
  metadata?: ShortsVideoMetadata;
}

export interface AppSettings {
  settings: Record<string, string>;
  masked_keys: string[];
}
