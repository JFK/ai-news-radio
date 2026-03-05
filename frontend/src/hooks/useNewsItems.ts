import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { NewsItem } from "../types";

export function useNewsItems(episodeId: number) {
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const res = await api.getNewsItems(episodeId);
      setNewsItems(res.data);
    } catch {
      // silently fail — news items are supplementary
    } finally {
      setLoading(false);
    }
  }, [episodeId]);

  useEffect(() => {
    setLoading(true);
    fetch();
  }, [fetch]);

  return { newsItems, loading, refetch: fetch };
}
