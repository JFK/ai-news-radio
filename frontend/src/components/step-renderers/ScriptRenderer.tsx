import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { NewsItem } from "../../types";

interface Props {
  outputData: Record<string, unknown>;
  newsItems: NewsItem[];
  episodeId: number;
  editable?: boolean;
  onUpdated?: () => void;
}

export default function ScriptRenderer({ outputData, newsItems, episodeId, editable, onUpdated }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingFull, setEditingFull] = useState(false);
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);

  const fullScript = (outputData.episode_script as string | undefined) ?? (outputData.full_script as string | undefined);
  const itemsWithScript = newsItems.filter((n) => n.script_text);

  const handleEditFull = () => {
    setEditText(fullScript || "");
    setEditingFull(true);
  };

  const handleSaveFull = async () => {
    try {
      setSaving(true);
      await api.editEpisodeScript(episodeId, editText);
      setEditingFull(false);
      onUpdated?.();
    } finally {
      setSaving(false);
    }
  };

  const handleEditItem = (item: NewsItem) => {
    setEditText(item.script_text || "");
    setEditingItemId(item.id);
  };

  const handleSaveItem = async () => {
    if (!editingItemId) return;
    try {
      setSaving(true);
      await api.editItemScript(episodeId, editingItemId, editText);
      setEditingItemId(null);
      onUpdated?.();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {fullScript && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-gray-600">
              {t("stepData.script.fullScript")}
            </h4>
            {editable && !editingFull && (
              <button
                onClick={handleEditFull}
                className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer"
              >
                {t("stepData.script.edit")}
              </button>
            )}
          </div>
          {editingFull ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full h-96 px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSaveFull}
                  disabled={saving}
                  className="px-3 py-1.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
                >
                  {saving ? t("stepData.script.saving") : t("stepData.script.save")}
                </button>
                <button
                  onClick={() => setEditingFull(false)}
                  className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 cursor-pointer"
                >
                  {t("stepData.script.cancel")}
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 whitespace-pre-wrap border max-h-96 overflow-y-auto">
              {fullScript}
            </div>
          )}
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
                  <div className="flex items-center gap-2 shrink-0">
                    {item.is_group_primary && item.group_id != null &&
                      newsItems.filter((n) => n.group_id === item.group_id).length > 1 && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-purple-50 text-purple-700">
                          {newsItems.filter((n) => n.group_id === item.group_id).length} {t("stepData.script.sources")}
                        </span>
                      )}
                    <span className="text-gray-400 text-xs">
                      {expandedId === item.id ? "▲" : "▼"}
                    </span>
                  </div>
                </button>
                {expandedId === item.id && item.script_text && (
                  <div className="px-3 pb-3 border-t">
                    {editingItemId === item.id ? (
                      <div className="space-y-2 mt-2">
                        <textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          className="w-full h-48 px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={handleSaveItem}
                            disabled={saving}
                            className="px-3 py-1.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
                          >
                            {saving ? t("stepData.script.saving") : t("stepData.script.save")}
                          </button>
                          <button
                            onClick={() => setEditingItemId(null)}
                            className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 cursor-pointer"
                          >
                            {t("stepData.script.cancel")}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-2">
                        <p className="text-sm text-gray-700 whitespace-pre-wrap">
                          {item.script_text}
                        </p>
                        {editable && (
                          <button
                            onClick={() => handleEditItem(item)}
                            className="text-xs text-blue-600 hover:text-blue-800 mt-2 cursor-pointer"
                          >
                            {t("stepData.script.edit")}
                          </button>
                        )}
                      </div>
                    )}
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
