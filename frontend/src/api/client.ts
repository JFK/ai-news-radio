import axios from "axios";
import type {
  Episode,
  EpisodeListResponse,
  NewsItem,
  PipelineStep,
  CostStatsResponse,
  EpisodeCostResponse,
} from "../types";

const client = axios.create({
  baseURL: "/api",
});

export const api = {
  getEpisodes: () => client.get<EpisodeListResponse>("/episodes"),
  getEpisode: (id: number) => client.get<Episode>(`/episodes/${id}`),
  createEpisode: (title: string) =>
    client.post<Episode>("/episodes", { title }),
  getSteps: (episodeId: number) =>
    client.get<PipelineStep[]>(`/episodes/${episodeId}/steps`),
  getNewsItems: (episodeId: number) =>
    client.get<NewsItem[]>(`/episodes/${episodeId}/news-items`),
  runStep: (episodeId: number, stepName: string) =>
    client.post<PipelineStep>(`/episodes/${episodeId}/steps/${stepName}/run`),
  approveStep: (stepId: number) =>
    client.post<PipelineStep>(`/steps/${stepId}/approve`),
  rejectStep: (stepId: number, reason: string) =>
    client.post<PipelineStep>(`/steps/${stepId}/reject`, { reason }),
  getCostStats: () => client.get<CostStatsResponse>("/stats/costs"),
  getEpisodeCosts: (id: number) =>
    client.get<EpisodeCostResponse>(`/stats/costs/episodes/${id}`),
};

export default client;
