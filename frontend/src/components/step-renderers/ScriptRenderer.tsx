import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { NewsItem } from "../../types";

interface DialogueTurn {
  speaker: string;
  text: string;
}

interface ScriptData {
  mode: string;
  speakers: Record<string, string>;
  dialogue: DialogueTurn[];
}

interface Props {
  outputData: Record<string, unknown>;
  newsItems: NewsItem[];
  episodeId: number;
  editable?: boolean;
  onUpdated?: () => void;
}

const SPEAKER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  speaker_a: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  speaker_b: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
};

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

  const handleModeChange = async (itemId: number, mode: string) => {
    const labels: Record<string, string> = {
      auto: t("stepData.script.modeAuto"),
      explainer: t("stepData.script.modeExplainer"),
      solo: t("stepData.script.modeSolo"),
    };
    if (!confirm(t("stepData.script.modeChangeConfirm", { mode: labels[mode] ?? mode }))) return;
    await api.setScriptMode(episodeId, itemId, mode);
    onUpdated?.();
  };

  const renderDialogue = (scriptData: ScriptData) => {
    const speakers = scriptData.speakers || {};
    return (
      <div className="space-y-2 mt-2">
        {scriptData.dialogue.map((turn, i) => {
          const colors = SPEAKER_COLORS[turn.speaker] ?? SPEAKER_COLORS.speaker_a;
          const name = speakers[turn.speaker] ?? turn.speaker;
          return (
            <div key={i} className={`rounded-lg p-3 border ${colors.bg} ${colors.border}`}>
              <span className={`text-xs font-semibold ${colors.text}`}>{name}</span>
              <p className="text-sm text-gray-800 mt-1">{turn.text}</p>
            </div>
          );
        })}
      </div>
    );
  };

  const getModeBadge = (item: NewsItem) => {
    const mode = item.script_mode || (item.script_data as ScriptData | null)?.mode;
    if (!mode) return null;
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs ${
        mode === "explainer"
          ? "bg-indigo-100 text-indigo-700"
          : "bg-gray-100 text-gray-600"
      }`}>
        {mode === "explainer" ? t("stepData.script.modeExplainer") : t("stepData.script.modeSolo")}
      </span>
    );
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
            {itemsWithScript.map((item) => {
              const scriptData = item.script_data as ScriptData | null;
              const isExplainer = scriptData?.mode === "explainer";

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
                      {getModeBadge(item)}
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
                  {expandedId === item.id && (
                    <div className="px-3 pb-3 border-t">
                      {/* Mode selector */}
                      {editable && (
                        <div className="flex items-center gap-2 mt-2 mb-2">
                          <span className="text-xs text-gray-500">{t("stepData.script.mode")}:</span>
                          <select
                            value={item.script_mode || "auto"}
                            onChange={(e) => handleModeChange(item.id, e.target.value)}
                            className="px-2 py-1 border border-gray-300 rounded text-xs bg-white"
                          >
                            <option value="auto">{t("stepData.script.modeAuto")}</option>
                            <option value="explainer">{t("stepData.script.modeExplainer")}</option>
                            <option value="solo">{t("stepData.script.modeSolo")}</option>
                          </select>
                        </div>
                      )}

                      {/* Dialogue or plain text */}
                      {isExplainer && scriptData ? (
                        renderDialogue(scriptData)
                      ) : editingItemId === item.id ? (
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
              );
            })}
          </div>
        </div>
      )}

      {/* Shorts scripts */}
      {(outputData.shorts as unknown[])?.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-600 mb-2">
            {t("stepData.script.shorts")}
          </h4>
          <div className="space-y-2">
            {(outputData.shorts as Array<{news_item_id: number; title?: string; mode: string; text?: string; dialogue?: DialogueTurn[]; speakers?: Record<string, string>; caption?: string}>).map((short, i) => {
              const item = newsItems.find((n) => n.id === short.news_item_id);
              const title = short.title || item?.title || `Short ${i + 1}`;
              return (
                <div key={i} className="border border-orange-200 rounded-lg p-3 bg-orange-50">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-orange-700">Short</span>
                    <span className="text-sm font-medium text-gray-700 truncate">{title}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${
                      short.mode === "explainer" ? "bg-indigo-100 text-indigo-700" : "bg-gray-100 text-gray-600"
                    }`}>
                      {short.mode === "explainer" ? t("stepData.script.modeExplainer") : t("stepData.script.modeSolo")}
                    </span>
                  </div>
                  {short.mode === "explainer" && short.dialogue ? (
                    renderDialogue({ mode: "explainer", speakers: short.speakers || {}, dialogue: short.dialogue })
                  ) : (
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{short.text}</p>
                  )}
                  {short.caption && (
                    <p className="text-xs text-gray-500 mt-2 italic">{short.caption}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
