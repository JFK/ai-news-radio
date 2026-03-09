import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { NewsItem } from "../../types";
import { ScoreBadge, StatusBadge } from "../ui/Badge";

interface Props {
  newsItems: NewsItem[];
}

export default function FactcheckRenderer({ newsItems }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const checkedItems = newsItems.filter((n) => n.fact_check_status);
  const avgScore =
    checkedItems.length > 0
      ? (
          checkedItems.reduce((sum, n) => sum + (n.fact_check_score ?? 0), 0) /
          checkedItems.length
        ).toFixed(1)
      : "-";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-blue-700">
            {checkedItems.length}
          </p>
          <p className="text-xs text-blue-600">
            {t("stepData.factcheck.checked")}
          </p>
        </div>
        <div className="bg-purple-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-purple-700">{avgScore}</p>
          <p className="text-xs text-purple-600">
            {t("stepData.factcheck.avgScore")}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {newsItems.map((item) => (
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
                <StatusBadge status={item.fact_check_status} />
                <ScoreBadge score={item.fact_check_score} />
                <span className="text-gray-400 text-xs">
                  {expandedId === item.id ? "▲" : "▼"}
                </span>
              </div>
            </button>

            {expandedId === item.id && (
              <div className="px-3 pb-3 border-t text-sm space-y-2">
                {item.fact_check_details && (
                  <p className="text-gray-700 mt-2">
                    {item.fact_check_details}
                  </p>
                )}
                {item.reference_urls && item.reference_urls.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-1">
                      {t("stepData.factcheck.references")}
                    </p>
                    <ul className="space-y-1">
                      {item.reference_urls.map((url, i) => (
                        <li key={i}>
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline break-all"
                          >
                            {url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
