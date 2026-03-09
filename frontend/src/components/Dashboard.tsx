import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useEpisodes } from "../hooks/useEpisodes";
import type { ArticleInput, EpisodeStatus } from "../types";

const STATUS_STYLES: Record<EpisodeStatus, { bg: string; text: string }> = {
  draft: { bg: "bg-gray-100", text: "text-gray-700" },
  in_progress: { bg: "bg-blue-100", text: "text-blue-700" },
  completed: { bg: "bg-green-100", text: "text-green-700" },
  published: { bg: "bg-purple-100", text: "text-purple-700" },
};

type CreateMode = "search" | "articles";

export default function Dashboard() {
  const { t } = useTranslation();
  const { episodes, loading, error, refetch } = useEpisodes();
  const navigate = useNavigate();
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [createMode, setCreateMode] = useState<CreateMode>("search");
  const [queries, setQueries] = useState("");
  const [articlesText, setArticlesText] = useState("");

  const handleCreateSearch = async () => {
    if (!newTitle.trim()) return;
    try {
      setCreating(true);
      const res = await api.createEpisode(newTitle.trim());
      const episodeId = res.data.id;
      // Run collection step with custom queries if provided
      if (queries.trim()) {
        const queryList = queries.split(",").map((q) => q.trim()).filter(Boolean);
        await api.runStep(episodeId, "collection", { queries: queryList });
      }
      setNewTitle("");
      setQueries("");
      setShowForm(false);
      navigate(`/episodes/${episodeId}`);
    } catch {
      refetch();
    } finally {
      setCreating(false);
    }
  };

  const handleCreateArticles = async () => {
    if (!newTitle.trim() || !articlesText.trim()) return;
    try {
      setCreating(true);
      const articles = parseArticles(articlesText);
      if (articles.length === 0) return;
      const res = await api.createEpisodeFromArticles(newTitle.trim(), articles);
      setNewTitle("");
      setArticlesText("");
      setShowForm(false);
      navigate(`/episodes/${res.data.id}`);
    } catch {
      refetch();
    } finally {
      setCreating(false);
    }
  };

  const currentStep = (steps: { step_name: string; status: string }[]) => {
    const active = steps.find((s) => s.status === "running" || s.status === "needs_approval");
    if (!active) return "-";
    return t(`steps.${active.step_name}`);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">{t("dashboard.title")}</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 cursor-pointer"
        >
          {t("dashboard.newEpisode")}
        </button>
      </div>

      {showForm && (
        <div className="mb-6 bg-white rounded-lg shadow p-4">
          {/* Mode selector */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setCreateMode("search")}
              className={`px-3 py-1.5 text-sm rounded-md font-medium ${
                createMode === "search"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              } cursor-pointer`}
            >
              {t("dashboard.modeSearch")}
            </button>
            <button
              onClick={() => setCreateMode("articles")}
              className={`px-3 py-1.5 text-sm rounded-md font-medium ${
                createMode === "articles"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              } cursor-pointer`}
            >
              {t("dashboard.modeArticles")}
            </button>
          </div>

          {/* Title input */}
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder={t("dashboard.titlePlaceholder")}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-3"
            autoFocus
          />

          {/* Search mode */}
          {createMode === "search" && (
            <div className="mb-3">
              <input
                type="text"
                value={queries}
                onChange={(e) => setQueries(e.target.value)}
                placeholder={t("dashboard.queriesPlaceholder")}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">{t("dashboard.queriesHint")}</p>
            </div>
          )}

          {/* Articles mode */}
          {createMode === "articles" && (
            <div className="mb-3">
              <textarea
                value={articlesText}
                onChange={(e) => setArticlesText(e.target.value)}
                placeholder={t("dashboard.articlesPlaceholder")}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm h-40 font-mono"
              />
              <p className="text-xs text-gray-400 mt-1">{t("dashboard.articlesHint")}</p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={createMode === "search" ? handleCreateSearch : handleCreateArticles}
              disabled={creating || !newTitle.trim() || (createMode === "articles" && !articlesText.trim())}
              className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
            >
              {creating ? t("dashboard.creating") : t("dashboard.create")}
            </button>
            <button
              onClick={() => { setShowForm(false); setNewTitle(""); setQueries(""); setArticlesText(""); }}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 cursor-pointer"
            >
              {t("dashboard.cancel")}
            </button>
          </div>
        </div>
      )}

      {loading && <p className="text-gray-500">{t("dashboard.loading")}</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && episodes.length === 0 && (
        <p className="text-gray-500">{t("dashboard.noEpisodes")}</p>
      )}

      {episodes.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("dashboard.table.id")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("dashboard.table.title")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("dashboard.table.status")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("dashboard.table.currentStep")}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t("dashboard.table.createdAt")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {episodes.map((ep) => {
                const style = STATUS_STYLES[ep.status];
                return (
                  <tr
                    key={ep.id}
                    onClick={() => navigate(`/episodes/${ep.id}`)}
                    className="hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-4 py-3 text-gray-500">#{ep.id}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">{ep.title}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
                        {t(`episodeStatus.${ep.status}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{currentStep(ep.pipeline_steps)}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(ep.created_at).toLocaleDateString("ja-JP")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function parseArticles(text: string): ArticleInput[] {
  // Try JSON first
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed;
    return [parsed];
  } catch {
    // Fall through to line-based parsing
  }

  // Line-based: "title | url | source_name" per line
  const articles: ArticleInput[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const parts = trimmed.split("|").map((p) => p.trim());
    if (parts.length >= 3) {
      articles.push({
        title: parts[0],
        source_url: parts[1],
        source_name: parts[2],
        summary: parts[3] || undefined,
      });
    }
  }
  return articles;
}
