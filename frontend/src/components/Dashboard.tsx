import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useEpisodes } from "../hooks/useEpisodes";
import type { EpisodeStatus } from "../types";

const STATUS_STYLES: Record<EpisodeStatus, { bg: string; text: string }> = {
  draft: { bg: "bg-gray-100", text: "text-gray-700" },
  in_progress: { bg: "bg-blue-100", text: "text-blue-700" },
  completed: { bg: "bg-green-100", text: "text-green-700" },
  published: { bg: "bg-purple-100", text: "text-purple-700" },
};

export default function Dashboard() {
  const { t } = useTranslation();
  const { episodes, loading, error, refetch } = useEpisodes();
  const navigate = useNavigate();
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    try {
      setCreating(true);
      const res = await api.createEpisode(newTitle.trim());
      setNewTitle("");
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
        <div className="mb-6 flex gap-2">
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder={t("dashboard.titlePlaceholder")}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
            autoFocus
          />
          <button
            onClick={handleCreate}
            disabled={creating || !newTitle.trim()}
            className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
          >
            {creating ? t("dashboard.creating") : t("dashboard.create")}
          </button>
          <button
            onClick={() => {
              setShowForm(false);
              setNewTitle("");
            }}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 cursor-pointer"
          >
            {t("dashboard.cancel")}
          </button>
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
