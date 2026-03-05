import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { NewsItem } from "../../types";

interface Props {
  newsItems: NewsItem[];
}

interface AnalysisData {
  background?: string;
  perspectives?: Array<{ viewpoint?: string; description?: string }>;
  data_verification?: string;
  impact_assessment?: string;
  severity?: string;
  topics?: string[];
}

function SeverityBadge({ severity }: { severity: string }) {
  const color =
    severity === "high"
      ? "bg-red-100 text-red-800"
      : severity === "medium"
        ? "bg-yellow-100 text-yellow-800"
        : "bg-green-100 text-green-800";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {severity}
    </span>
  );
}

export default function AnalysisRenderer({ newsItems }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const analyzedItems = newsItems.filter((n) => n.analysis_data);
  const severityCounts = analyzedItems.reduce(
    (acc, n) => {
      const s = (n.analysis_data as AnalysisData)?.severity ?? "low";
      acc[s] = (acc[s] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-blue-700">
            {analyzedItems.length}
          </p>
          <p className="text-xs text-blue-600">
            {t("stepData.analysis.analyzed")}
          </p>
        </div>
        {Object.entries(severityCounts).map(([severity, count]) => (
          <div key={severity} className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-gray-700">{count}</p>
            <p className="text-xs text-gray-600">
              {t(`stepData.analysis.severity_${severity}`, severity)}
            </p>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        {newsItems.map((item) => {
          const data = item.analysis_data as AnalysisData | null;
          return (
            <div key={item.id} className="border rounded-lg">
              <button
                onClick={() =>
                  setExpandedId(expandedId === item.id ? null : item.id)
                }
                className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50 cursor-pointer"
              >
                <span className="text-sm font-medium text-gray-800 truncate mr-2">
                  {item.title}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  {data?.severity && (
                    <SeverityBadge severity={data.severity} />
                  )}
                  {data?.topics?.map((topic) => (
                    <span
                      key={topic}
                      className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700"
                    >
                      {topic}
                    </span>
                  ))}
                  <span className="text-gray-400 text-xs">
                    {expandedId === item.id ? "▲" : "▼"}
                  </span>
                </div>
              </button>

              {expandedId === item.id && data && (
                <div className="px-3 pb-3 border-t text-sm space-y-3 mt-0">
                  {data.background && (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        {t("stepData.analysis.background")}
                      </p>
                      <p className="text-gray-700">{data.background}</p>
                    </div>
                  )}

                  {data.perspectives && data.perspectives.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        {t("stepData.analysis.perspectives")}
                      </p>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-gray-500">
                            <th className="text-left pb-1 font-medium">
                              {t("stepData.analysis.viewpoint")}
                            </th>
                            <th className="text-left pb-1 font-medium">
                              {t("stepData.analysis.description")}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.perspectives.map((p, i) => (
                            <tr key={i} className="border-b last:border-0">
                              <td className="py-1 pr-2 font-medium text-gray-700">
                                {p.viewpoint}
                              </td>
                              <td className="py-1 text-gray-600">
                                {p.description}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {data.data_verification && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        {t("stepData.analysis.dataVerification")}
                      </p>
                      <p className="text-gray-700">{data.data_verification}</p>
                    </div>
                  )}

                  {data.impact_assessment && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        {t("stepData.analysis.impact")}
                      </p>
                      <p className="text-gray-700">{data.impact_assessment}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
