import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Episode } from "../types";

export function useEpisodes() {
  const { t } = useTranslation();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getEpisodes();
      setEpisodes(res.data.episodes);
      setTotal(res.data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("errors.fetchEpisodes"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { episodes, total, loading, error, refetch: fetch };
}
