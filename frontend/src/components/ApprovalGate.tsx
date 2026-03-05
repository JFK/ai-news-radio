import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { PipelineStep, NewsItem } from "../types";
import StepDataRenderer from "./step-renderers/StepDataRenderer";

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

  if (step.status !== "needs_approval") return null;

  const handleApprove = async () => {
    try {
      setSubmitting(true);
      setError(null);
      await api.approveStep(step.id);
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

      {!rejecting ? (
        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={submitting}
            className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
          >
            {submitting ? t("approval.processing") : t("approval.approve")}
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
