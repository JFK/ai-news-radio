import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { ModelPricing } from "../types";

export default function Settings() {
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

  // Group by provider
  const providers = [...new Set(pricing.map((p) => p.provider))].sort();

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">{t("settings.title")}</h2>

      {/* Model Pricing Table */}
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
    </div>
  );
}
