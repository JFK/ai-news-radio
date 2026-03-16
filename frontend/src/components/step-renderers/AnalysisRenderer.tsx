import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { AnalysisData, NewsItem } from "../../types";
import { SeverityBadge } from "../ui/Badge";

interface Props {
  newsItems: NewsItem[];
}

function AnalysisDetail({ data }: { data: AnalysisData }) {
  const { t } = useTranslation();
  return (
    <div className="text-sm space-y-3">
      {data.background && (
        <div>
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
                    {p.standpoint}
                  </td>
                  <td className="py-1 text-gray-600">{p.argument}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.data_validation && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">
            {t("stepData.analysis.dataVerification")}
          </p>
          <p className="text-gray-700">{data.data_validation}</p>
        </div>
      )}

      {data.source_comparison && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">
            {t("stepData.analysis.sourceComparison")}
          </p>
          <p className="text-gray-700">{data.source_comparison}</p>
        </div>
      )}

      {data.impact && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">
            {t("stepData.analysis.impact")}
          </p>
          <p className="text-gray-700">{data.impact}</p>
        </div>
      )}

      {data.recommended_format && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">
            {t("stepData.analysis.recommendedFormat")}
          </p>
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              data.recommended_format === "explainer"
                ? "bg-indigo-100 text-indigo-700"
                : "bg-gray-100 text-gray-700"
            }`}>
              {data.recommended_format === "explainer"
                ? t("stepData.analysis.formatExplainer")
                : t("stepData.analysis.formatSolo")}
            </span>
            {data.format_reason && (
              <span className="text-xs text-gray-500">{data.format_reason}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalysisRenderer({ newsItems }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Build groups from newsItems' group_id fields
  const groupMap = new Map<number, NewsItem[]>();
  const ungroupedItems: NewsItem[] = [];

  for (const item of newsItems) {
    if (item.group_id != null) {
      const existing = groupMap.get(item.group_id) || [];
      existing.push(item);
      groupMap.set(item.group_id, existing);
    } else {
      ungroupedItems.push(item);
    }
  }

  // Separate primary and members for each group
  const groups: { primary: NewsItem; members: NewsItem[]; groupId: number }[] = [];
  for (const [groupId, items] of groupMap) {
    const primary = items.find((i) => i.is_group_primary) || items[0];
    const members = items.filter((i) => i.id !== primary.id);
    groups.push({ primary, members, groupId });
  }

  // Items with real analysis data (not merged_into markers)
  const analyzedItems = newsItems.filter(
    (n) => n.analysis_data && !("merged_into" in (n.analysis_data ?? {})),
  );
  const severityCounts = analyzedItems.reduce(
    (acc, n) => {
      const s = (n.analysis_data as AnalysisData)?.severity ?? "low";
      acc[s] = (acc[s] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  const renderItemRow = (item: NewsItem, isGroupMember = false) => {
    const data = item.analysis_data as AnalysisData | null;
    const isMerged = data && "merged_into" in (item.analysis_data ?? {});

    return (
      <div
        key={item.id}
        className={`border rounded-lg ${isGroupMember ? "ml-6 border-dashed" : ""}`}
      >
        <button
          onClick={() =>
            setExpandedId(expandedId === item.id ? null : item.id)
          }
          className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50 cursor-pointer"
        >
          <span className="text-sm font-medium text-gray-800 truncate mr-2">
            {isGroupMember && (
              <span className="text-gray-400 mr-1">└</span>
            )}
            {item.title}
            {isGroupMember && (
              <span className="ml-2 text-xs text-gray-400">
                ({item.source_name})
              </span>
            )}
          </span>
          <div className="flex items-center gap-2 shrink-0">
            {isMerged && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">
                {t("stepData.analysis.merged")}
              </span>
            )}
            {!isMerged && data?.recommended_format && (
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                data.recommended_format === "explainer"
                  ? "bg-indigo-50 text-indigo-600"
                  : "bg-gray-50 text-gray-600"
              }`}>
                {data.recommended_format === "explainer"
                  ? t("stepData.analysis.formatExplainer")
                  : t("stepData.analysis.formatSolo")}
              </span>
            )}
            {!isMerged && data?.severity && (
              <SeverityBadge severity={data.severity} />
            )}
            {!isMerged &&
              data?.topics?.map((topic) => (
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

        {expandedId === item.id && data && !isMerged && (
          <div className="px-3 pb-3 border-t mt-0">
            <div className="mt-2">
              <AnalysisDetail data={data} />
            </div>
          </div>
        )}
      </div>
    );
  };

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
          <div
            key={severity}
            className="bg-gray-50 rounded-lg p-3 text-center"
          >
            <p className="text-2xl font-bold text-gray-700">{count}</p>
            <p className="text-xs text-gray-600">
              {t(`stepData.analysis.severity_${severity}`, severity)}
            </p>
          </div>
        ))}
      </div>

      {groups.length > 0 && (
        <div className="text-xs text-gray-500">
          {t("stepData.analysis.groupCount", { count: groups.length })}
        </div>
      )}

      <div className="space-y-2">
        {/* Render grouped items */}
        {groups.map(({ primary, members, groupId }) => (
          <div key={`group-${groupId}`} className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full text-xs bg-purple-50 text-purple-700">
                {t("stepData.analysis.group")} {groupId}
              </span>
              <span className="text-xs text-gray-500">
                {members.length + 1} {t("stepData.analysis.sources")}
              </span>
            </div>
            {renderItemRow(primary)}
            {members.map((member) => renderItemRow(member, true))}
          </div>
        ))}

        {/* Render ungrouped items */}
        {ungroupedItems.map((item) => renderItemRow(item))}
      </div>
    </div>
  );
}
