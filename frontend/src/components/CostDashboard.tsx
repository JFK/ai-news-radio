import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { CostStatsResponse } from "../types";

type DatePreset = "today" | "7d" | "30d" | "all";

function getDateRange(preset: DatePreset): { from?: string; to?: string } {
  if (preset === "all") return {};
  const to = new Date().toISOString().split("T")[0];
  const from = new Date();
  if (preset === "today") {
    // same day
  } else if (preset === "7d") {
    from.setDate(from.getDate() - 7);
  } else if (preset === "30d") {
    from.setDate(from.getDate() - 30);
  }
  return { from: from.toISOString().split("T")[0], to };
}

export default function CostDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<CostStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preset, setPreset] = useState<DatePreset>("all");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const { from, to } = getDateRange(preset);
      const res = await api.getCostStats(from, to);
      setStats(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("costs.fetchFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, preset]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatCost = (usd: number) => `$${usd.toFixed(4)}`;
  const formatTokens = (n: number) => n.toLocaleString();

  const presets: { key: DatePreset; label: string }[] = [
    { key: "today", label: t("costs.presetToday") },
    { key: "7d", label: t("costs.preset7d") },
    { key: "30d", label: t("costs.preset30d") },
    { key: "all", label: t("costs.presetAll") },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">{t("costs.title")}</h2>

      {/* Date filter */}
      <div className="flex gap-2 mb-6">
        {presets.map((p) => (
          <button
            key={p.key}
            onClick={() => setPreset(p.key)}
            className={`px-3 py-1.5 text-sm rounded-md font-medium cursor-pointer ${
              preset === p.key
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-gray-500">{t("costs.loading")}</p>}
      {error && <p className="text-red-600">{error}</p>}
      {!loading && !error && stats && (
        <>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">{t("costs.totalCost")}</p>
              <p className="text-2xl font-bold text-gray-900">{formatCost(stats.total_cost_usd)}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">{t("costs.totalRequests")}</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_requests.toLocaleString()}</p>
            </div>
          </div>

          {stats.by_provider.length > 0 && (
            <div className="mb-6">
              <h3 className="text-base font-semibold text-gray-700 mb-3">{t("costs.byProvider")}</h3>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">{t("costs.provider")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.inputTokens")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.outputTokens")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.cost")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.requests")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {stats.by_provider.map((row) => (
                      <tr key={row.provider}>
                        <td className="px-4 py-3 font-medium text-gray-900">{row.provider}</td>
                        <td className="px-4 py-3 text-right text-gray-600">{formatTokens(row.total_input_tokens)}</td>
                        <td className="px-4 py-3 text-right text-gray-600">{formatTokens(row.total_output_tokens)}</td>
                        <td className="px-4 py-3 text-right text-gray-900 font-medium">{formatCost(row.total_cost_usd)}</td>
                        <td className="px-4 py-3 text-right text-gray-600">{row.request_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {stats.by_step.length > 0 && (
            <div>
              <h3 className="text-base font-semibold text-gray-700 mb-3">{t("costs.byStep")}</h3>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">{t("costs.step")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.inputTokens")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.outputTokens")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.cost")}</th>
                      <th className="text-right px-4 py-3 font-medium text-gray-600">{t("costs.requests")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {stats.by_step.map((row) => (
                      <tr key={row.step_name}>
                        <td className="px-4 py-3 font-medium text-gray-900">{t(`steps.${row.step_name}`)}</td>
                        <td className="px-4 py-3 text-right text-gray-600">{formatTokens(row.total_input_tokens)}</td>
                        <td className="px-4 py-3 text-right text-gray-600">{formatTokens(row.total_output_tokens)}</td>
                        <td className="px-4 py-3 text-right text-gray-900 font-medium">{formatCost(row.total_cost_usd)}</td>
                        <td className="px-4 py-3 text-right text-gray-600">{row.request_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {stats.by_provider.length === 0 && stats.by_step.length === 0 && (
            <p className="text-gray-500">{t("costs.noData")}</p>
          )}
        </>
      )}
    </div>
  );
}
