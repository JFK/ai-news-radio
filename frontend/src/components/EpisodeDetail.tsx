import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useEpisode } from "../hooks/useEpisode";
import { useNewsItems } from "../hooks/useNewsItems";
import type { StepName, PipelineStep } from "../types";
import PipelineView from "./PipelineView";
import ApprovalGate from "./ApprovalGate";
import StepDataRenderer from "./step-renderers/StepDataRenderer";

const MEDIA_BASE_URL = "/media";

function ElapsedTime({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState("");

  useEffect(() => {
    const update = () => {
      const start = new Date(startedAt).getTime();
      const diff = Math.floor((Date.now() - start) / 1000);
      const min = Math.floor(diff / 60);
      const sec = diff % 60;
      setElapsed(min > 0 ? `${min}m ${sec}s` : `${sec}s`);
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [startedAt]);

  return <span className="font-mono">{elapsed}</span>;
}

function StepLogs({ episodeId, stepName, isRunning }: { episodeId: number; stepName: string; isRunning: boolean }) {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<{ message: string; timestamp: string }[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await api.getStepLogs(episodeId, stepName);
      setLogs(res.data.logs);
    } catch {
      // ignore
    }
  }, [episodeId, stepName]);

  useEffect(() => {
    if (!isRunning) {
      setLogs([]);
      return;
    }
    fetchLogs();
    const timer = setInterval(fetchLogs, 3000);
    return () => clearInterval(timer);
  }, [isRunning, fetchLogs]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (!isRunning || logs.length === 0) return null;

  return (
    <div className="mt-2 mb-3 bg-gray-900 rounded-md p-3 max-h-40 overflow-y-auto">
      <p className="text-xs text-gray-400 mb-1">{t("episode.progressLogs")}</p>
      {logs.map((log, i) => (
        <div key={i} className="text-xs text-green-400 font-mono leading-5">
          <span className="text-gray-500">{new Date(log.timestamp).toLocaleTimeString("ja-JP")}</span>{" "}
          {log.message}
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  );
}

export default function EpisodeDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const episodeId = Number(id);
  const { episode, loading, error, refetch } = useEpisode(episodeId);
  const { newsItems } = useNewsItems(episodeId);
  const [selectedStep, setSelectedStep] = useState<StepName | null>(null);
  const [runningStep, setRunningStep] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState(false);
  const [driveEnabled, setDriveEnabled] = useState(false);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    api.getSettings().then((res) => {
      const val = res.data.settings.google_drive_enabled ?? "";
      setDriveEnabled(val.toLowerCase() === "true");
    }).catch(() => {});
  }, []);

  if (loading) return <p className="text-gray-500">{t("episode.loading")}</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!episode) return <p className="text-gray-500">{t("episode.notFound")}</p>;

  const steps = episode.pipeline_steps;
  const activeStep: PipelineStep | undefined = selectedStep
    ? steps.find((s) => s.step_name === selectedStep)
    : undefined;

  const canRunStep = (step: PipelineStep | undefined): boolean => {
    if (!step) return false;
    return step.status === "pending" || step.status === "rejected";
  };

  const handleRunStep = async () => {
    if (!selectedStep) return;
    setRunningStep(true);
    try {
      await api.runStep(episodeId, selectedStep);
      await refetch();
    } catch {
      await refetch();
    } finally {
      setRunningStep(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(t("episode.deleteConfirm"))) return;
    try {
      setDeleting(true);
      await api.deleteEpisode(episodeId);
      navigate("/");
    } catch {
      refetch();
    } finally {
      setDeleting(false);
    }
  };

  const handleToggleComplete = async () => {
    try {
      setToggling(true);
      await api.toggleComplete(episodeId);
      await refetch();
    } catch {
      await refetch();
    } finally {
      setToggling(false);
    }
  };

  const analysisStep = steps.find((s) => s.step_name === "analysis");
  const showDriveExport = driveEnabled && analysisStep && analysisStep.status === "approved";

  const handleExportToDrive = async () => {
    setExporting(true);
    setExportError(null);
    setExportSuccess(false);
    try {
      await api.exportToDrive(episodeId);
      setExportSuccess(true);
      await refetch();
    } catch {
      setExportError(t("episode.exportFailed"));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <Link to="/" className="text-blue-600 hover:text-blue-800 text-sm mb-4 inline-block">
        &larr; {t("episode.backToDashboard")}
      </Link>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">{episode.title}</h2>
          <p className="text-sm text-gray-500 mt-1">
            {t("episode.id")}: #{episode.id} / {t("episode.status")}: {t(`episodeStatus.${episode.status}`)} / {t("episode.createdAt")}:{" "}
            {new Date(episode.created_at).toLocaleDateString("ja-JP")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleToggleComplete}
            disabled={toggling}
            className={`px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50 cursor-pointer ${
              episode.status === "completed"
                ? "bg-yellow-500 text-white hover:bg-yellow-600"
                : "bg-green-600 text-white hover:bg-green-700"
            }`}
          >
            {toggling
              ? t("episode.toggling")
              : episode.status === "completed"
                ? t("episode.markIncomplete")
                : t("episode.markComplete")}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="px-3 py-1.5 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50 cursor-pointer"
          >
            {deleting ? t("episode.deleting") : t("episode.delete")}
          </button>
        </div>
      </div>

      {(episode.audio_path || episode.video_path) && (() => {
        const videoStep = steps.find((s) => s.step_name === "video");
        const thumbnailPath = (videoStep?.output_data as Record<string, unknown> | null)?.thumbnail_path as string | undefined;
        return (
        <div className="mb-6 bg-white rounded-lg shadow p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-600">{t("episode.media")}</h3>
          {episode.audio_path && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.audio")}</p>
              <audio controls className="w-full" src={`${MEDIA_BASE_URL}/${episode.audio_path}`} />
              <a
                href={`${MEDIA_BASE_URL}/${episode.audio_path}`}
                download
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                {t("episode.download")}
              </a>
            </div>
          )}
          {episode.video_path && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.video")}</p>
              <video controls className="w-full rounded" src={`${MEDIA_BASE_URL}/${episode.video_path}`} />
              <a
                href={`${MEDIA_BASE_URL}/${episode.video_path}`}
                download
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                {t("episode.download")}
              </a>
            </div>
          )}
          {thumbnailPath && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.thumbnail")}</p>
              <img src={`${MEDIA_BASE_URL}/${thumbnailPath}`} alt="Thumbnail" className="w-64 rounded border" />
              <a
                href={`${MEDIA_BASE_URL}/${thumbnailPath}`}
                download
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                {t("episode.download")}
              </a>
            </div>
          )}
        </div>
        );
      })()}

      {showDriveExport && (
        <div className="mb-6 bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-medium text-gray-600 mb-2">Google Drive</h3>
          <div className="flex items-center gap-3 flex-wrap">
            {episode.drive_file_url && (
              <a
                href={episode.drive_file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline"
              >
                {t("episode.driveLink")}
              </a>
            )}
            <button
              onClick={handleExportToDrive}
              disabled={exporting}
              className="px-3 py-1.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 cursor-pointer"
            >
              {exporting
                ? t("episode.exporting")
                : episode.drive_file_url
                  ? t("episode.reExportToDrive")
                  : t("episode.exportToDrive")}
            </button>
            {exportSuccess && (
              <span className="text-sm text-green-600">{t("episode.exportSuccess")}</span>
            )}
            {exportError && (
              <span className="text-sm text-red-600">{exportError}</span>
            )}
          </div>
        </div>
      )}

      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-600 mb-2">{t("episode.pipeline")}</h3>
        <PipelineView
          steps={steps}
          selectedStep={selectedStep}
          onSelectStep={setSelectedStep}
        />
      </div>

      {activeStep && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-gray-800">
              {t(`steps.${activeStep.step_name}`)}
            </h3>
            <div className="flex items-center gap-3">
              {activeStep.status === "running" && activeStep.started_at && (
                <span className="text-sm text-blue-600 flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                  {t("episode.elapsed")}: <ElapsedTime startedAt={activeStep.started_at} />
                </span>
              )}
              {canRunStep(activeStep) && (
                <button
                  onClick={handleRunStep}
                  disabled={runningStep}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
                >
                  {runningStep ? t("episode.running") : t("episode.runStep")}
                </button>
              )}
            </div>
          </div>

          <StepLogs episodeId={episodeId} stepName={activeStep.step_name} isRunning={activeStep.status === "running"} />

          <dl className="grid grid-cols-2 gap-2 text-sm mb-3">
            <div>
              <dt className="text-gray-500">{t("episode.status")}</dt>
              <dd className="font-medium">{t(`stepStatus.${activeStep.status}`)}</dd>
            </div>
            <div>
              <dt className="text-gray-500">{t("episode.started")}</dt>
              <dd>{activeStep.started_at ? new Date(activeStep.started_at).toLocaleString("ja-JP") : "-"}</dd>
            </div>
            <div>
              <dt className="text-gray-500">{t("episode.completed")}</dt>
              <dd>{activeStep.completed_at ? new Date(activeStep.completed_at).toLocaleString("ja-JP") : "-"}</dd>
            </div>
            {activeStep.rejection_reason && (
              <div className="col-span-2">
                <dt className="text-gray-500">{t("episode.rejectionReason")}</dt>
                <dd className="text-red-600">{activeStep.rejection_reason}</dd>
              </div>
            )}
          </dl>

          {activeStep.output_data && (activeStep.status !== "needs_approval" || activeStep.step_name === "script") && (
            <div className="mb-3">
              <StepDataRenderer
                stepName={activeStep.step_name}
                outputData={activeStep.output_data}
                newsItems={newsItems}
                episodeId={episodeId}
                editable={activeStep.step_name === "script" && (activeStep.status === "needs_approval" || activeStep.status === "approved")}
                onUpdated={refetch}
              />
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
                  {t("pipeline.rawJson")}
                </summary>
                <pre className="mt-1 p-3 bg-gray-50 rounded border text-xs overflow-auto max-h-48">
                  {JSON.stringify(activeStep.output_data, null, 2)}
                </pre>
              </details>
            </div>
          )}

          {activeStep.input_data && (
            <details className="mb-2">
              <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
                {t("pipeline.inputData")}
              </summary>
              <pre className="mt-1 p-3 bg-gray-50 rounded border text-xs overflow-auto max-h-48">
                {JSON.stringify(activeStep.input_data, null, 2)}
              </pre>
            </details>
          )}

          <ApprovalGate step={activeStep} newsItems={newsItems} onUpdated={refetch} />
        </div>
      )}

      {!activeStep && selectedStep === null && (
        <p className="text-gray-500 text-sm">{t("episode.selectStep")}</p>
      )}
    </div>
  );
}
