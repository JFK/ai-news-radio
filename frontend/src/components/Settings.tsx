import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { ModelPricing, Pronunciation, PromptSummary, PromptHistory } from "../types";

type SettingsTab = "config" | "pricing" | "prompts" | "dictionary";

export default function Settings() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<SettingsTab>("config");

  const tabs: { key: SettingsTab; label: string }[] = [
    { key: "config", label: t("settings.config.title") },
    { key: "pricing", label: t("settings.pricing.title") },
    { key: "prompts", label: t("settings.prompts.title") },
    { key: "dictionary", label: t("settings.dictionary.title") },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">{t("settings.title")}</h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 cursor-pointer ${
              activeTab === tab.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "config" && <ConfigSection />}
      {activeTab === "pricing" && <PricingSection />}
      {activeTab === "prompts" && <PromptsSection />}
      {activeTab === "dictionary" && <DictionarySection />}
    </div>
  );
}

interface FieldDef {
  key: string;
  label: string;
  type: "text" | "password" | "number" | "select" | "checkbox" | "textarea" | "model";
  options?: string[];
  wide?: boolean;
}

interface CategoryDef {
  title: string;
  fields: FieldDef[];
  guide?: string[];
}

function ConfigSection() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [maskedKeys, setMaskedKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const originalRef = useRef<Record<string, string>>({});
  const [editingSecrets, setEditingSecrets] = useState<Set<string>>(new Set());
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [driveAuthStatus, setDriveAuthStatus] = useState<{ authenticated: boolean; client_id_configured: boolean } | null>(null);

  // Fetch model names from pricing table
  useEffect(() => {
    api.getPricing().then((res) => {
      const models = [...new Set(res.data.map((p: ModelPricing) => p.model_prefix))].sort();
      setModelOptions(models);
    }).catch(() => {});
  }, []);

  // Fetch Google Drive auth status
  const refreshDriveAuthStatus = useCallback(() => {
    api.getGoogleDriveAuthStatus().then((res) => setDriveAuthStatus(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    refreshDriveAuthStatus();
  }, [refreshDriveAuthStatus]);

  // Detect OAuth callback redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("drive_auth") === "success") {
      setFeedback({ type: "success", message: t("settings.config.driveAuthSuccess") });
      refreshDriveAuthStatus();
      // Clean up URL
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [refreshDriveAuthStatus, t]);

  const categories: CategoryDef[] = [
    {
      title: t("settings.config.aiProvider"),
      fields: [
        { key: "default_ai_provider", label: "Default AI Provider", type: "select", options: ["openai", "anthropic", "google"] },
        { key: "default_ai_model", label: "Default AI Model", type: "model" },
      ],
    },
    {
      title: t("settings.config.pipelineAi"),
      fields: [
        { key: "pipeline_factcheck_provider", label: "Factcheck Provider", type: "select", options: ["openai", "anthropic", "google"] },
        { key: "pipeline_factcheck_model", label: "Factcheck Model", type: "model" },
        { key: "pipeline_analysis_provider", label: "Analysis Provider", type: "select", options: ["openai", "anthropic", "google"] },
        { key: "pipeline_analysis_model", label: "Analysis Model", type: "model" },
        { key: "pipeline_script_provider", label: "Script Provider", type: "select", options: ["openai", "anthropic", "google"] },
        { key: "pipeline_script_model", label: "Script Model", type: "model" },
        { key: "pipeline_export_provider", label: "Export Provider", type: "select", options: ["openai", "anthropic", "google"] },
        { key: "pipeline_export_model", label: "Export Model", type: "model" },
      ],
    },
    {
      title: t("settings.config.apiKeys"),
      fields: [
        { key: "anthropic_api_key", label: "Anthropic API Key", type: "password" },
        { key: "openai_api_key", label: "OpenAI API Key", type: "password" },
        { key: "google_api_key", label: "Google API Key", type: "password" },
        { key: "brave_search_api_key", label: "Brave Search API Key", type: "password" },
        { key: "elevenlabs_api_key", label: "ElevenLabs API Key", type: "password" },
      ],
    },
    {
      title: t("settings.config.collection"),
      fields: [
        { key: "collection_method", label: "Collection Method", type: "text" },
        { key: "collection_queries", label: "Collection Queries", type: "text", wide: true },
        { key: "collection_crawl_enabled", label: "Crawl Enabled", type: "checkbox" },
        { key: "collection_youtube_enabled", label: "YouTube Enabled", type: "checkbox" },
        { key: "collection_document_enabled", label: "Document Enabled", type: "checkbox" },
        { key: "collection_ai_research_enabled", label: "AI Research Enabled", type: "checkbox" },
      ],
    },
    {
      title: t("settings.config.voice"),
      fields: [
        { key: "pipeline_voice_provider", label: "Voice Provider", type: "select", options: ["voicevox", "openai", "elevenlabs", "google", "gemini"] },
        { key: "voicevox_host", label: "VOICEVOX Host", type: "text" },
        { key: "voicevox_speaker_id", label: "VOICEVOX Speaker ID", type: "number" },
        { key: "gemini_tts_model", label: "Gemini TTS Model", type: "text" },
        { key: "gemini_tts_voice", label: "Gemini TTS Voice", type: "text" },
        { key: "gemini_tts_instructions", label: "Gemini TTS Instructions", type: "text" },
      ],
    },
    {
      title: t("settings.config.visual"),
      fields: [
        { key: "visual_provider", label: "Visual Provider", type: "select", options: ["static", "google"] },
      ],
    },
    {
      title: t("settings.config.googleDrive"),
      fields: [
        { key: "google_drive_enabled", label: t("settings.config.enabled"), type: "checkbox" },
        { key: "google_drive_client_id", label: "OAuth Client ID", type: "password" },
        { key: "google_drive_client_secret", label: "OAuth Client Secret", type: "password" },
        { key: "google_drive_folder_id", label: "Google Drive Folder ID", type: "text" },
      ],
      guide: t("settings.config.googleDriveGuide", { returnObjects: true }) as unknown as string[],
    },
  ];

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getSettings();
      setSettings(res.data.settings);
      setMaskedKeys(new Set(res.data.masked_keys || []));
      originalRef.current = { ...res.data.settings };
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleChange = (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleCheckboxChange = (key: string, checked: boolean) => {
    setSettings((prev) => ({ ...prev, [key]: checked ? "true" : "false" }));
  };

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      // Only send changed values; skip fields still showing masked values
      const changed: Record<string, string> = {};
      for (const [key, value] of Object.entries(settings)) {
        if (value === originalRef.current[key]) continue; // Not changed
        if (!editingSecrets.has(key) && maskedKeys.has(key)) continue; // Still masked
        changed[key] = value;
      }
      if (Object.keys(changed).length === 0) {
        setFeedback({ type: "success", message: t("settings.config.saved") });
        return;
      }
      await api.updateSettings(changed);
      setFeedback({ type: "success", message: t("settings.config.saved") });
      setEditingSecrets(new Set());
      // Refresh to get updated values
      await fetchSettings();
      refreshDriveAuthStatus();
    } catch {
      setFeedback({ type: "error", message: t("settings.config.saveFailed") });
    } finally {
      setSaving(false);
    }
  };

  const renderField = (field: FieldDef) => {
    const value = settings[field.key] ?? "";

    if (field.type === "checkbox") {
      return (
        <label key={field.key} className="flex items-center gap-2 py-1">
          <input
            type="checkbox"
            checked={value.toLowerCase() === "true" || value === "1"}
            onChange={(e) => handleCheckboxChange(field.key, e.target.checked)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-700">{field.label}</span>
        </label>
      );
    }

    if (field.type === "select") {
      return (
        <div key={field.key}>
          <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
          <select
            value={value}
            onChange={(e) => handleChange(field.key, e.target.value)}
            className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full max-w-xs bg-white"
          >
            <option value="">--</option>
            {field.options?.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      );
    }

    if (field.type === "model") {
      return (
        <div key={field.key}>
          <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
          <select
            value={value}
            onChange={(e) => handleChange(field.key, e.target.value)}
            className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full max-w-xs bg-white"
          >
            <option value="">--</option>
            {modelOptions.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
            {value && !modelOptions.includes(value) && (
              <option value={value}>{value}</option>
            )}
          </select>
        </div>
      );
    }

    if (field.type === "password") {
      const isEditing = editingSecrets.has(field.key);
      const masked = maskedKeys.has(field.key) || value === "";
      const displayValue = value || t("settings.config.notSet");

      if (!isEditing) {
        return (
          <div key={field.key} className={field.wide ? "col-span-2" : ""}>
            <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-1.5 text-sm font-mono ${masked && value ? "text-gray-600" : "text-gray-400 italic"}`}>
                {displayValue}
              </span>
              <button
                type="button"
                onClick={() => {
                  setEditingSecrets((prev) => new Set(prev).add(field.key));
                  handleChange(field.key, "");
                }}
                className="px-2 py-1 text-xs text-blue-600 hover:text-blue-800 border border-blue-300 rounded font-medium cursor-pointer"
              >
                {t("settings.config.edit")}
              </button>
            </div>
          </div>
        );
      }

      return (
        <div key={field.key} className={field.wide ? "col-span-2" : ""}>
          <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={value}
              onChange={(e) => handleChange(field.key, e.target.value)}
              className={`px-2 py-1.5 border border-blue-300 rounded text-sm font-mono ${field.wide ? "w-full" : "w-full max-w-xs"}`}
              placeholder={t("settings.config.enterValue")}
              autoFocus
            />
            <button
              type="button"
              onClick={() => {
                setEditingSecrets((prev) => {
                  const next = new Set(prev);
                  next.delete(field.key);
                  return next;
                });
                // Restore original masked value
                handleChange(field.key, originalRef.current[field.key] ?? "");
              }}
              className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700 border border-gray-300 rounded font-medium cursor-pointer whitespace-nowrap"
            >
              {t("settings.config.cancel")}
            </button>
          </div>
        </div>
      );
    }

    if (field.type === "textarea") {
      return (
        <div key={field.key} className="col-span-2">
          <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
          <textarea
            value={value}
            onChange={(e) => handleChange(field.key, e.target.value)}
            className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full font-mono resize-y h-24"
            placeholder="{...}"
          />
        </div>
      );
    }

    return (
      <div key={field.key} className={field.wide ? "col-span-2" : ""}>
        <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
        <input
          type={field.type}
          value={value}
          onChange={(e) => handleChange(field.key, e.target.value)}
          className={`px-2 py-1.5 border border-gray-300 rounded text-sm ${field.wide ? "w-full" : "w-full max-w-xs"}`}
        />
      </div>
    );
  };

  if (loading) {
    return <p className="text-gray-500 text-sm">{t("settings.loading")}</p>;
  }

  return (
    <div className="space-y-6">
      {categories.map((cat) => (
        <div key={cat.title} className="bg-white rounded-lg shadow border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">{cat.title}</h3>
          {cat.guide && cat.guide.length > 0 && (
            <details className="mb-3">
              <summary className="text-xs text-blue-600 cursor-pointer hover:text-blue-800 font-medium">
                {t("settings.config.setupGuide")}
              </summary>
              <div className="mt-2 text-xs text-gray-600">
                <p className="mb-2">{cat.guide[0]}</p>
                {cat.guide.length > 1 && (
                  <ol className="ml-4 list-decimal space-y-1">
                    {cat.guide.slice(1).map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                )}
              </div>
            </details>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {cat.fields.map((field) => renderField(field))}
          </div>
          {cat.title === t("settings.config.googleDrive") && driveAuthStatus && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  disabled={!driveAuthStatus.client_id_configured}
                  onClick={async () => {
                    try {
                      const res = await api.getGoogleDriveAuthUrl();
                      window.location.href = res.data.auth_url;
                    } catch {
                      setFeedback({ type: "error", message: t("settings.config.driveAuthFailed") });
                    }
                  }}
                  className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
                >
                  {driveAuthStatus.authenticated
                    ? t("settings.config.driveReAuth")
                    : t("settings.config.driveAuth")}
                </button>
                <span className={`text-xs font-medium ${driveAuthStatus.authenticated ? "text-green-600" : "text-gray-400"}`}>
                  {driveAuthStatus.authenticated
                    ? t("settings.config.driveConnected")
                    : t("settings.config.driveNotConnected")}
                </span>
              </div>
              {!driveAuthStatus.client_id_configured && (
                <p className="text-xs text-gray-400 mt-1">{t("settings.config.driveNeedClientId")}</p>
              )}
            </div>
          )}
        </div>
      ))}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
        >
          {saving ? t("settings.config.saving") : t("settings.config.save")}
        </button>
        {feedback && (
          <span className={`text-sm ${feedback.type === "success" ? "text-green-600" : "text-red-600"}`}>
            {feedback.message}
          </span>
        )}
      </div>
    </div>
  );
}

function PricingSection() {
  const { t } = useTranslation();
  const [pricing, setPricing] = useState<ModelPricing[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ model_prefix: "", provider: "", input_price_per_1m: 0, output_price_per_1m: 0 });

  const fetchPricing = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getPricing();
      setPricing(res.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPricing();
  }, [fetchPricing]);

  const handleAdd = async () => {
    if (!form.model_prefix || !form.provider) return;
    await api.createPricing(form);
    setForm({ model_prefix: "", provider: "", input_price_per_1m: 0, output_price_per_1m: 0 });
    setShowAdd(false);
    fetchPricing();
  };

  const handleUpdate = async (id: number) => {
    const item = pricing.find((p) => p.id === id);
    if (!item) return;
    await api.updatePricing(id, {
      model_prefix: item.model_prefix,
      provider: item.provider,
      input_price_per_1m: item.input_price_per_1m,
      output_price_per_1m: item.output_price_per_1m,
    });
    setEditingId(null);
    fetchPricing();
  };

  const handleDelete = async (id: number) => {
    await api.deletePricing(id);
    fetchPricing();
  };

  const updateRow = (id: number, field: string, value: string | number) => {
    setPricing((prev) =>
      prev.map((p) => (p.id === id ? { ...p, [field]: value } : p))
    );
  };

  const providers = [...new Set(pricing.map((p) => p.provider))].sort();

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-gray-700">{t("settings.pricing.title")}</h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 cursor-pointer"
        >
          {t("settings.pricing.add")}
        </button>
      </div>

      {showAdd && (
        <div className="bg-gray-50 rounded-lg p-4 mb-4 flex gap-2 items-end flex-wrap">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.pricing.modelPrefix")}</label>
            <input
              type="text"
              value={form.model_prefix}
              onChange={(e) => setForm({ ...form, model_prefix: e.target.value })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-40"
              placeholder="gpt-5.2"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.pricing.provider")}</label>
            <input
              type="text"
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-28"
              placeholder="openai"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.pricing.inputPrice")}</label>
            <input
              type="number"
              step="0.01"
              value={form.input_price_per_1m}
              onChange={(e) => setForm({ ...form, input_price_per_1m: parseFloat(e.target.value) || 0 })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.pricing.outputPrice")}</label>
            <input
              type="number"
              step="0.01"
              value={form.output_price_per_1m}
              onChange={(e) => setForm({ ...form, output_price_per_1m: parseFloat(e.target.value) || 0 })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-24"
            />
          </div>
          <button
            onClick={handleAdd}
            disabled={!form.model_prefix || !form.provider}
            className="px-3 py-1.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
          >
            {t("settings.pricing.save")}
          </button>
        </div>
      )}

      {loading ? (
        <p className="text-gray-500 text-sm">{t("settings.loading")}</p>
      ) : (
        providers.map((provider) => (
          <div key={provider} className="mb-4">
            <h4 className="text-sm font-medium text-gray-500 mb-2 uppercase">{provider}</h4>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-600">{t("settings.pricing.modelPrefix")}</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600">{t("settings.pricing.inputPrice")}</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600">{t("settings.pricing.outputPrice")}</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600 w-28"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {pricing
                    .filter((p) => p.provider === provider)
                    .map((p) => (
                      <tr key={p.id}>
                        <td className="px-4 py-2 font-mono text-gray-900">{p.model_prefix}</td>
                        <td className="px-4 py-2 text-right">
                          {editingId === p.id ? (
                            <input
                              type="number"
                              step="0.01"
                              value={p.input_price_per_1m}
                              onChange={(e) => updateRow(p.id, "input_price_per_1m", parseFloat(e.target.value) || 0)}
                              className="w-24 px-1 py-0.5 border rounded text-right text-sm"
                            />
                          ) : (
                            <span className="text-gray-600">${p.input_price_per_1m}</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {editingId === p.id ? (
                            <input
                              type="number"
                              step="0.01"
                              value={p.output_price_per_1m}
                              onChange={(e) => updateRow(p.id, "output_price_per_1m", parseFloat(e.target.value) || 0)}
                              className="w-24 px-1 py-0.5 border rounded text-right text-sm"
                            />
                          ) : (
                            <span className="text-gray-600">${p.output_price_per_1m}</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {editingId === p.id ? (
                            <button
                              onClick={() => handleUpdate(p.id)}
                              className="text-green-600 hover:text-green-800 text-xs font-medium cursor-pointer"
                            >
                              {t("settings.pricing.save")}
                            </button>
                          ) : (
                            <span className="flex gap-2 justify-end">
                              <button
                                onClick={() => setEditingId(p.id)}
                                className="text-blue-600 hover:text-blue-800 text-xs font-medium cursor-pointer"
                              >
                                {t("settings.pricing.edit")}
                              </button>
                              <button
                                onClick={() => handleDelete(p.id)}
                                className="text-red-500 hover:text-red-700 text-xs font-medium cursor-pointer"
                              >
                                {t("settings.pricing.delete")}
                              </button>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function PromptsSection() {
  const { t } = useTranslation();
  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<PromptHistory | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchPrompts = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getPrompts();
      setPrompts(res.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrompts();
  }, [fetchPrompts]);

  const openDetail = async (key: string) => {
    setSelectedKey(key);
    setEditing(false);
    const res = await api.getPrompt(key);
    setDetail(res.data);
    // Set edit content to active version or default
    const activeVersion = res.data.versions.find((v) => v.is_active);
    setEditContent(activeVersion ? activeVersion.content : res.data.default_content);
  };

  const handleSave = async () => {
    if (!selectedKey || !editContent.trim()) return;
    setSaving(true);
    try {
      await api.updatePrompt(selectedKey, editContent);
      await openDetail(selectedKey);
      setEditing(false);
      fetchPrompts();
    } finally {
      setSaving(false);
    }
  };

  const handleRollback = async (version: number) => {
    if (!selectedKey) return;
    await api.rollbackPrompt(selectedKey, version);
    await openDetail(selectedKey);
    fetchPrompts();
  };

  const handleReset = async () => {
    if (!selectedKey) return;
    await api.resetPrompt(selectedKey);
    setDetail(null);
    setSelectedKey(null);
    setEditing(false);
    fetchPrompts();
  };

  if (loading) {
    return <p className="text-gray-500 text-sm">{t("settings.loading")}</p>;
  }

  // Detail view
  if (selectedKey && detail) {
    const activeVersion = detail.versions.find((v) => v.is_active);
    const currentContent = activeVersion ? activeVersion.content : detail.default_content;

    return (
      <div>
        <button
          onClick={() => { setSelectedKey(null); setDetail(null); setEditing(false); }}
          className="text-blue-600 hover:text-blue-800 text-sm mb-4 cursor-pointer"
        >
          &larr; {t("settings.prompts.backToList")}
        </button>

        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">{detail.name}</h3>
            <p className="text-sm text-gray-500">
              {activeVersion
                ? `${t("settings.prompts.version")} ${activeVersion.version} (${t("settings.prompts.custom")})`
                : t("settings.prompts.usingDefault")}
            </p>
          </div>
          <div className="flex gap-2">
            {!editing && (
              <button
                onClick={() => { setEditContent(currentContent); setEditing(true); }}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 cursor-pointer"
              >
                {t("settings.prompts.edit")}
              </button>
            )}
            {activeVersion && (
              <button
                onClick={handleReset}
                className="px-3 py-1.5 text-sm bg-gray-200 text-gray-700 rounded-md font-medium hover:bg-gray-300 cursor-pointer"
              >
                {t("settings.prompts.resetDefault")}
              </button>
            )}
          </div>
        </div>

        {editing ? (
          <div>
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full h-96 px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono resize-y focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <div className="flex gap-2 mt-3">
              <button
                onClick={handleSave}
                disabled={saving || !editContent.trim()}
                className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
              >
                {saving ? t("settings.prompts.saving") : t("settings.prompts.save")}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 cursor-pointer"
              >
                {t("settings.prompts.cancel")}
              </button>
            </div>
          </div>
        ) : (
          <pre className="w-full bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm font-mono whitespace-pre-wrap overflow-auto max-h-96">
            {currentContent}
          </pre>
        )}

        {/* Version history */}
        {detail.versions.length > 0 && (
          <div className="mt-6">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">{t("settings.prompts.history")}</h4>
            <div className="space-y-2">
              {detail.versions.map((v) => (
                <div
                  key={v.id}
                  className={`flex items-center justify-between px-4 py-2 rounded-lg border ${
                    v.is_active ? "border-blue-300 bg-blue-50" : "border-gray-200 bg-white"
                  }`}
                >
                  <div className="text-sm">
                    <span className="font-medium text-gray-800">
                      v{v.version}
                    </span>
                    {v.is_active && (
                      <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                        {t("settings.prompts.active")}
                      </span>
                    )}
                    <span className="ml-3 text-gray-500 text-xs">
                      {new Date(v.created_at).toLocaleString()}
                    </span>
                  </div>
                  {!v.is_active && (
                    <button
                      onClick={() => handleRollback(v.version)}
                      className="text-blue-600 hover:text-blue-800 text-xs font-medium cursor-pointer"
                    >
                      {t("settings.prompts.restore")}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // List view
  return (
    <div>
      <div className="space-y-2">
        {prompts.map((p) => (
          <div
            key={p.key}
            onClick={() => openDetail(p.key)}
            className="flex items-center justify-between px-4 py-3 bg-white rounded-lg shadow border border-gray-200 hover:border-blue-300 cursor-pointer transition-colors"
          >
            <div>
              <div className="font-medium text-gray-800">{p.name}</div>
              <div className="text-xs text-gray-500 mt-1 font-mono truncate max-w-lg">
                {p.content_preview}
              </div>
            </div>
            <div className="text-right shrink-0 ml-4">
              {p.has_custom ? (
                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                  v{p.active_version} ({t("settings.prompts.custom")})
                </span>
              ) : (
                <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs font-medium">
                  {t("settings.prompts.default")}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DictionarySection() {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<Pronunciation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ surface: "", reading: "", priority: 0 });

  const fetchEntries = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getDictionary();
      setEntries(res.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleAdd = async () => {
    if (!form.surface || !form.reading) return;
    try {
      await api.createDictionary(form);
      setForm({ surface: "", reading: "", priority: 0 });
      setShowAdd(false);
      fetchEntries();
    } catch {
      // 409 duplicate
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteDictionary(id);
    fetchEntries();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold text-gray-700">{t("settings.dictionary.title")}</h3>
          <p className="text-xs text-gray-500 mt-1">{t("settings.dictionary.description")}</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 cursor-pointer"
        >
          {t("settings.dictionary.add")}
        </button>
      </div>

      {showAdd && (
        <div className="bg-gray-50 rounded-lg p-4 mb-4 flex gap-2 items-end flex-wrap">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.dictionary.surface")}</label>
            <input
              type="text"
              value={form.surface}
              onChange={(e) => setForm({ ...form, surface: e.target.value })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-40"
              placeholder="菊陽町"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.dictionary.reading")}</label>
            <input
              type="text"
              value={form.reading}
              onChange={(e) => setForm({ ...form, reading: e.target.value })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-40"
              placeholder="きくようまち"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("settings.dictionary.priority")}</label>
            <input
              type="number"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-20"
            />
          </div>
          <button
            onClick={handleAdd}
            disabled={!form.surface || !form.reading}
            className="px-3 py-1.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
          >
            {t("settings.dictionary.save")}
          </button>
        </div>
      )}

      {loading ? (
        <p className="text-gray-500 text-sm">{t("settings.loading")}</p>
      ) : entries.length === 0 ? (
        <p className="text-gray-500 text-sm">{t("settings.dictionary.empty")}</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600">{t("settings.dictionary.surface")}</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600">{t("settings.dictionary.reading")}</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">{t("settings.dictionary.priority")}</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600 w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-2 font-medium text-gray-900">{e.surface}</td>
                  <td className="px-4 py-2 text-gray-600">{e.reading}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{e.priority}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => handleDelete(e.id)}
                      className="text-red-500 hover:text-red-700 text-xs font-medium cursor-pointer"
                    >
                      {t("settings.dictionary.delete")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
