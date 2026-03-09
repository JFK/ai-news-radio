import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { ArticleInput } from "../types";

type CreateMode = "search" | "articles";

interface Props {
  onCreated: () => void;
}

export default function EpisodeCreationForm({ onCreated }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createMode, setCreateMode] = useState<CreateMode>("search");
  const [queries, setQueries] = useState("");
  const [articlesText, setArticlesText] = useState("");
  const [showForm, setShowForm] = useState(false);

  const handleCreateSearch = async () => {
    if (!newTitle.trim()) return;
    try {
      setCreating(true);
      const res = await api.createEpisode(newTitle.trim());
      const episodeId = res.data.id;
      if (queries.trim()) {
        const queryList = queries.split(",").map((q) => q.trim()).filter(Boolean);
        await api.runStep(episodeId, "collection", { queries: queryList });
      }
      resetForm();
      navigate(`/episodes/${episodeId}`);
    } catch {
      onCreated();
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
      resetForm();
      navigate(`/episodes/${res.data.id}`);
    } catch {
      onCreated();
    } finally {
      setCreating(false);
    }
  };

  const resetForm = () => {
    setShowForm(false);
    setNewTitle("");
    setQueries("");
    setArticlesText("");
  };

  return (
    <>
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
              onClick={resetForm}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 cursor-pointer"
            >
              {t("dashboard.cancel")}
            </button>
          </div>
        </div>
      )}
    </>
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
