import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Episode, EpisodeStatus } from "../types";

const STATUS_STYLES: Record<EpisodeStatus, { bg: string; text: string }> = {
  draft: { bg: "bg-gray-100", text: "text-gray-700" },
  in_progress: { bg: "bg-blue-100", text: "text-blue-700" },
  completed: { bg: "bg-green-100", text: "text-green-700" },
  published: { bg: "bg-purple-100", text: "text-purple-700" },
};

interface Props {
  episodes: Episode[];
}

export default function EpisodeTable({ episodes }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const currentStep = (steps: { step_name: string; status: string }[]) => {
    const active = steps.find((s) => s.status === "running" || s.status === "needs_approval");
    if (!active) return "-";
    return t(`steps.${active.step_name}`);
  };

  if (episodes.length === 0) return null;

  return (
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
  );
}
