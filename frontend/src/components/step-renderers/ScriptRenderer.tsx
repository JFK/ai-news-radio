import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { NewsItem } from "../../types";

interface Props {
  outputData: Record<string, unknown>;
  newsItems: NewsItem[];
}

export default function ScriptRenderer({ outputData, newsItems }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fullScript = outputData.full_script as string | undefined;
  const itemsWithScript = newsItems.filter((n) => n.script_text);

  return (
    <div className="space-y-4">
      {fullScript && (
        <div>
          <h4 className="text-sm font-medium text-gray-600 mb-2">
            {t("stepData.script.fullScript")}
          </h4>
          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 whitespace-pre-wrap border max-h-96 overflow-y-auto">
            {fullScript}
          </div>
        </div>
      )}

      {itemsWithScript.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-600 mb-2">
            {t("stepData.script.perArticle")}
          </h4>
          <div className="space-y-2">
            {itemsWithScript.map((item) => (
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
                  <span className="text-gray-400 text-xs shrink-0">
                    {expandedId === item.id ? "▲" : "▼"}
                  </span>
                </button>
                {expandedId === item.id && item.script_text && (
                  <div className="px-3 pb-3 border-t">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap mt-2">
                      {item.script_text}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
