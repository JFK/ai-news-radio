import { useTranslation } from "react-i18next";
import { useEpisodes } from "../hooks/useEpisodes";
import EpisodeCreationForm from "./EpisodeCreationForm";
import EpisodeTable from "./EpisodeTable";

export default function Dashboard() {
  const { t } = useTranslation();
  const { episodes, loading, error, refetch } = useEpisodes();

  return (
    <div>
      <EpisodeCreationForm onCreated={refetch} />

      {loading && <p className="text-gray-500">{t("dashboard.loading")}</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && episodes.length === 0 && (
        <p className="text-gray-500">{t("dashboard.noEpisodes")}</p>
      )}

      <EpisodeTable episodes={episodes} />
    </div>
  );
}
