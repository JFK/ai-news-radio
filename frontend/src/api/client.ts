import axios from "axios";
import type {
  Episode,
  EpisodeListResponse,
  NewsItem,
  PipelineStep,
  CostStatsResponse,
  EpisodeCostResponse,
  ArticleInput,
  ModelPricing,
  Pronunciation,
  PromptSummary,
  PromptHistory,
  PromptTemplateVersion,
  DriveExportResponse,
  AppSettings,
  SpeakerProfile,
} from "../types";

const client = axios.create({
  baseURL: "/api",
});

export const api = {
  getEpisodes: () => client.get<EpisodeListResponse>("/episodes"),
  getEpisode: (id: number) => client.get<Episode>(`/episodes/${id}`),
  createEpisode: (title: string) =>
    client.post<Episode>("/episodes", { title }),
  createEpisodeFromArticles: (title: string, articles: ArticleInput[]) =>
    client.post<Episode>("/episodes/from-articles", { title, articles }),
  getSteps: (episodeId: number) =>
    client.get<PipelineStep[]>(`/episodes/${episodeId}/steps`),
  getNewsItems: (episodeId: number) =>
    client.get<NewsItem[]>(`/episodes/${episodeId}/news-items`),
  updateEpisode: (episodeId: number, data: { title?: string; shorts_enabled?: boolean }) =>
    client.patch<Episode>(`/episodes/${episodeId}`, data),
  deleteEpisode: (episodeId: number) =>
    client.delete(`/episodes/${episodeId}`),
  runStep: (episodeId: number, stepName: string, body?: { queries?: string[]; tts_model?: string; tts_voice?: string; video_targets?: string[] }) =>
    client.post<PipelineStep>(`/episodes/${episodeId}/steps/${stepName}/run`, body),
  getStepLogs: (episodeId: number, stepName: string) =>
    client.get<{ logs: { message: string; timestamp: string }[] }>(`/episodes/${episodeId}/steps/${stepName}/logs`),
  approveStep: (stepId: number, excludedItemIds?: number[]) =>
    client.post<PipelineStep>(`/steps/${stepId}/approve`, excludedItemIds?.length ? { excluded_item_ids: excludedItemIds } : undefined),
  rejectStep: (stepId: number, reason: string) =>
    client.post<PipelineStep>(`/steps/${stepId}/reject`, { reason }),
  editItemScript: (episodeId: number, newsItemId: number, scriptText: string) =>
    client.patch(`/episodes/${episodeId}/news-items/${newsItemId}/script`, { script_text: scriptText }),
  setScriptMode: (episodeId: number, newsItemId: number, scriptMode: string) =>
    client.patch(`/episodes/${episodeId}/news-items/${newsItemId}/script-mode`, { script_mode: scriptMode }),
  editEpisodeScript: (episodeId: number, episodeScript: string) =>
    client.patch(`/episodes/${episodeId}/steps/script/output`, { episode_script: episodeScript }),
  getCostStats: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    const qs = params.toString();
    return client.get<CostStatsResponse>(`/stats/costs${qs ? `?${qs}` : ""}`);
  },
  getEpisodeCosts: (id: number) =>
    client.get<EpisodeCostResponse>(`/stats/costs/episodes/${id}`),
  // Pricing CRUD
  getPricing: () => client.get<ModelPricing[]>("/pricing"),
  createPricing: (data: { model_prefix: string; provider: string; input_price_per_1m: number; output_price_per_1m: number }) =>
    client.post<ModelPricing>("/pricing", data),
  updatePricing: (id: number, data: { model_prefix: string; provider: string; input_price_per_1m: number; output_price_per_1m: number }) =>
    client.put<ModelPricing>(`/pricing/${id}`, data),
  deletePricing: (id: number) => client.delete(`/pricing/${id}`),
  // Prompt templates
  getPrompts: () => client.get<PromptSummary[]>("/prompts"),
  getPrompt: (key: string) => client.get<PromptHistory>(`/prompts/${key}`),
  updatePrompt: (key: string, content: string) =>
    client.put<PromptTemplateVersion>(`/prompts/${key}`, { content }),
  rollbackPrompt: (key: string, version: number) =>
    client.post<PromptTemplateVersion>(`/prompts/${key}/rollback/${version}`),
  resetPrompt: (key: string) => client.delete(`/prompts/${key}`),
  // Pronunciation dictionary
  getDictionary: () => client.get<Pronunciation[]>("/dictionary"),
  createDictionary: (data: { surface: string; reading: string; priority: number }) =>
    client.post<Pronunciation>("/dictionary", data),
  deleteDictionary: (id: number) => client.delete(`/dictionary/${id}`),
  // Settings
  getSettings: () => client.get<AppSettings>("/settings"),
  updateSettings: (settings: Record<string, string>) =>
    client.put<{ updated: string[] }>("/settings", { settings }),
  // Speakers
  getSpeakers: () => client.get<SpeakerProfile[]>("/speakers"),
  createSpeaker: (data: { name: string; role: string; voice_name?: string; voice_instructions?: string; avatar_position?: string; description?: string }) =>
    client.post<SpeakerProfile>("/speakers", data),
  updateSpeaker: (id: number, data: { name: string; role: string; voice_name?: string; voice_instructions?: string; avatar_position?: string; description?: string }) =>
    client.put<SpeakerProfile>(`/speakers/${id}`, data),
  deleteSpeaker: (id: number) => client.delete(`/speakers/${id}`),
  uploadAvatar: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return client.post<SpeakerProfile>(`/speakers/${id}/avatar`, form);
  },
  deleteAvatar: (id: number) => client.delete<SpeakerProfile>(`/speakers/${id}/avatar`),
  generateAvatar: (id: number, customPrompt?: string) =>
    client.post<{ speaker: SpeakerProfile; cost_usd: number; visual_provider: string }>(`/speakers/${id}/avatar/generate`, customPrompt ? { custom_prompt: customPrompt } : {}),
  getAvatarLibrary: (id: number) =>
    client.get<{ images: string[] }>(`/speakers/${id}/avatar/library`),
  selectAvatar: (id: number, imagePath: string) =>
    client.put<SpeakerProfile>(`/speakers/${id}/avatar/select`, { image_path: imagePath }),
  // Toggle complete
  toggleComplete: (episodeId: number) =>
    client.post<Episode>(`/episodes/${episodeId}/toggle-complete`),
  // Drive export
  exportToDrive: (episodeId: number) =>
    client.post<DriveExportResponse>(`/episodes/${episodeId}/export/drive`),
  // Google Drive OAuth
  getGoogleDriveAuthUrl: () =>
    client.get<{ auth_url: string }>("/auth/google/drive/url"),
  getGoogleDriveAuthStatus: () =>
    client.get<{ authenticated: boolean; client_id_configured: boolean }>("/auth/google/drive/status"),
};

export default client;
