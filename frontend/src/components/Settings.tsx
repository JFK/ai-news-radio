import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { ModelPricing, PromptSummary, PromptHistory } from "../types";

export default function Settings() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"pricing" | "prompts">("pricing");

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">{t("settings.title")}</h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("pricing")}
          className={`px-4 py-2 text-sm font-medium border-b-2 cursor-pointer ${
            activeTab === "pricing"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("settings.pricing.title")}
        </button>
        <button
          onClick={() => setActiveTab("prompts")}
          className={`px-4 py-2 text-sm font-medium border-b-2 cursor-pointer ${
            activeTab === "prompts"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("settings.prompts.title")}
        </button>
      </div>

      {activeTab === "pricing" && <PricingSection />}
      {activeTab === "prompts" && <PromptsSection />}
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
              placeholder="gpt-5"
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
