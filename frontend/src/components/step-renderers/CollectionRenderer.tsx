import { useTranslation } from "react-i18next";
import type { NewsItem } from "../../types";

interface Props {
  outputData: Record<string, unknown>;
  newsItems: NewsItem[];
}

export default function CollectionRenderer({ outputData, newsItems }: Props) {
  const { t } = useTranslation();

  const stats = outputData.stats as
    | { fetched?: number; saved?: number }
    | undefined;

  return (
    <div className="space-y-4">
      {stats && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-blue-50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-blue-700">
              {stats.fetched ?? "-"}
            </p>
            <p className="text-xs text-blue-600">
              {t("stepData.collection.fetched")}
            </p>
          </div>
          <div className="bg-green-50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-green-700">
              {stats.saved ?? "-"}
            </p>
            <p className="text-xs text-green-600">
              {t("stepData.collection.saved")}
            </p>
          </div>
        </div>
      )}

      {newsItems.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2 font-medium">
                  {t("stepData.collection.title")}
                </th>
                <th className="pb-2 font-medium">
                  {t("stepData.collection.source")}
                </th>
              </tr>
            </thead>
            <tbody>
              {newsItems.map((item) => (
                <tr key={item.id} className="border-b last:border-0">
                  <td className="py-2 pr-3">
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {item.title}
                    </a>
                  </td>
                  <td className="py-2 text-gray-500">{item.source_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
