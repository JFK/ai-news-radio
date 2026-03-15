import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Episode } from "../types";

export function useEpisode(id: number) {
  const { t } = useTranslation();
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hasRunningStep = episode?.pipeline_steps.some((s) => s.status === "running") ?? false;

  const fetchData = useCallback(async (): Promise<Episode | null> => {
    try {
      setError(null);
      const res = await api.getEpisode(id);
      setEpisode(res.data);
      return res.data;
    } catch (e) {
      setError(e instanceof Error ? e.message : t("errors.fetchEpisode"));
      return null;
    } finally {
      setLoading(false);
    }
  }, [id, t]);

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [fetchData]);

  // Only poll when a step is running
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (hasRunningStep) {
      intervalRef.current = setInterval(fetchData, 2000);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData, hasRunningStep]);

  return { episode, loading, error, refetch: fetchData };
}
