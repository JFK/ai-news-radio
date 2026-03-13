import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { PipelineStep, NewsItem } from "../types";
import StepDataRenderer from "./step-renderers/StepDataRenderer";

const ITEM_APPROVAL_STEPS = ["collection", "factcheck", "analysis"];

interface Props {
  step: PipelineStep;
  newsItems: NewsItem[];
  onUpdated: () => void;
}

export default function ApprovalGate({ step, newsItems, onUpdated }: Props) {
  const { t } = useTranslation();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeItems = newsItems.filter((item) => !item.excluded);
  const [excludedIds, setExcludedIds] = useState<Set<number>>(new Set());

  if (step.status !== "needs_approval") return null;

  const showItemSelection = ITEM_APPROVAL_STEPS.includes(step.step_name) && activeItems.length > 0;

  const toggleItem = (id: number) => {
    setExcludedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (excludedIds.size === 0) {
      setExcludedIds(new Set(activeItems.map((item) => item.id)));
    } else {
      setExcludedIds(new Set());
    }
  };

  const approvedCount = activeItems.length - excludedIds.size;

  const handleApprove = async () => {
    if (showItemSelection && approvedCount === 0) return;
    try {
      setSubmitting(true);
      setError(null);
      const ids = excludedIds.size > 0 ? Array.from(excludedIds) : undefined;
      await api.approveStep(step.id, ids);
      onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("approval.approveFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!reason.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      await api.rejectStep(step.id, reason);
      setRejecting(false);
      setReason("");
      onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("approval.rejectFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const getScoreBadge = (item: NewsItem) => {
    if (item.fact_check_score == null) return null;
    const score = item.fact_check_score;
    const color =
      score >= 4
        ? "bg-green-100 text-green-800"
        : score >= 3
          ? "bg-yellow-100 text-yellow-800"
          : "bg-red-100 text-red-800";
    return (
      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${color}`}>
        {score}/5
      </span>
    );
  };

  return (
    <div className="border-2 border-yellow-300 bg-yellow-50 rounded-lg p-4 mt-4">
      <h3 className="text-sm font-semibold text-yellow-800 mb-3">{t("approval.title")}</h3>

      {error && (
        <p className="text-sm text-red-600 mb-3">{error}</p>
      )}

      {step.output_data && (
        <div className="mb-3">
          <StepDataRenderer
            stepName={step.step_name}
            outputData={step.output_data}
            newsItems={newsItems}
          />
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
              {t("pipeline.rawJson")}
            </summary>
            <pre className="mt-2 p-3 bg-white rounded border text-xs overflow-auto max-h-64">
              {JSON.stringify(step.output_data, null, 2)}
            </pre>
          </details>
        </div>
      )}

      {showItemSelection && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">
              {t("approval.selectArticles")}
            </span>
            <button
              onClick={toggleAll}
              className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer"
            >
              {excludedIds.size === 0 ? t("approval.deselectAll") : t("approval.selectAll")}
            </button>
          </div>
          <div className="space-y-1">
            {activeItems.map((item) => {
              const isExcluded = excludedIds.has(item.id);
              return (
                <label
                  key={item.id}
                  className={`flex items-center gap-2 p-2 rounded border cursor-pointer transition-colors ${
                    isExcluded
                      ? "bg-gray-100 border-gray-200 opacity-60"
                      : "bg-white border-gray-300 hover:border-blue-400"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={!isExcluded}
                    onChange={() => toggleItem(item.id)}
                    className="rounded border-gray-300 text-blue-600 cursor-pointer"
                  />
                  <span className={`text-sm flex-1 ${isExcluded ? "line-through text-gray-400" : "text-gray-800"}`}>
                    {item.title}
                  </span>
                  {getScoreBadge(item)}
                  <span className="text-xs text-gray-400">{item.source_name}</span>
                </label>
              );
            })}
          </div>
          {excludedIds.size > 0 && (
            <p className="text-xs text-orange-600 mt-2">
              {t("approval.excludeCount", { count: excludedIds.size })}
            </p>
          )}
        </div>
      )}

      {!rejecting ? (
        <div className="flex gap-2 items-center">
          <button
            onClick={handleApprove}
            disabled={submitting || (showItemSelection && approvedCount === 0)}
            className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
          >
            {submitting
              ? t("approval.processing")
              : showItemSelection
                ? t("approval.approveSelected", { count: approvedCount })
                : t("approval.approve")}
          </button>
          <button
            onClick={() => setRejecting(true)}
            disabled={submitting}
            className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50 cursor-pointer"
          >
            {t("approval.reject")}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("approval.rejectPlaceholder")}
            className="w-full p-2 border border-gray-300 rounded-md text-sm resize-none"
            rows={3}
          />
          <div className="flex gap-2">
            <button
              onClick={handleReject}
              disabled={submitting || !reason.trim()}
              className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50 cursor-pointer"
            >
              {submitting ? t("approval.processing") : t("approval.confirmReject")}
            </button>
            <button
              onClick={() => {
                setRejecting(false);
                setReason("");
              }}
              disabled={submitting}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 disabled:opacity-50 cursor-pointer"
            >
              {t("dashboard.cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
