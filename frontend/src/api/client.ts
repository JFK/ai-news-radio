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
  deleteEpisode: (episodeId: number) =>
    client.delete(`/episodes/${episodeId}`),
  runStep: (episodeId: number, stepName: string, body?: { queries?: string[] }) =>
    client.post<PipelineStep>(`/episodes/${episodeId}/steps/${stepName}/run`, body),
  approveStep: (stepId: number) =>
    client.post<PipelineStep>(`/steps/${stepId}/approve`),
  rejectStep: (stepId: number, reason: string) =>
    client.post<PipelineStep>(`/steps/${stepId}/reject`, { reason }),
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
};

export default client;
