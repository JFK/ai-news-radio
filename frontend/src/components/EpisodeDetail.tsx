import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useEpisode } from "../hooks/useEpisode";
import { useNewsItems } from "../hooks/useNewsItems";
import type { StepName, PipelineStep, ShortsVideo } from "../types";
import { GEMINI_TTS_MODELS, GEMINI_TTS_VOICES } from "../constants/tts";
import PipelineView from "./PipelineView";
import ApprovalGate from "./ApprovalGate";
import StepDataRenderer from "./step-renderers/StepDataRenderer";

const MEDIA_BASE_URL = "/media";

/** Persistent <details> that remembers open/closed state in localStorage. */
function PersistentDetails({
  storageKey,
  defaultOpen = false,
  className,
  summary,
  children,
}: {
  storageKey: string;
  defaultOpen?: boolean;
  className?: string;
  summary: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(() => {
    const stored = localStorage.getItem(storageKey);
    return stored !== null ? stored === "1" : defaultOpen;
  });
  const handleToggle = (e: React.SyntheticEvent<HTMLDetailsElement>) => {
    const isOpen = (e.target as HTMLDetailsElement).open;
    setOpen(isOpen);
    localStorage.setItem(storageKey, isOpen ? "1" : "0");
  };
  return (
    <details className={className} open={open} onToggle={handleToggle}>
      <summary className="cursor-pointer p-4 text-sm font-medium text-gray-600 select-none">
        {summary}
      </summary>
      {children}
    </details>
  );
}

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
    // Always fetch once to show logs (even for completed steps)
    fetchLogs();
    if (!isRunning) return;
    const timer = setInterval(fetchLogs, 3000);
    return () => clearInterval(timer);
  }, [isRunning, fetchLogs]);

  useEffect(() => {
    if (isRunning) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, isRunning]);

  if (logs.length === 0) return null;

  const logContent = (
    <div className="bg-gray-900 rounded-md p-3 max-h-40 overflow-y-auto">
      {logs.map((log, i) => (
        <div key={i} className="text-xs text-green-400 font-mono leading-5">
          <span className="text-gray-500">{new Date(log.timestamp).toLocaleTimeString("ja-JP")}</span>{" "}
          {log.message}
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  );

  if (isRunning) {
    return (
      <div className="mt-2 mb-3">
        <p className="text-xs text-gray-400 mb-1">{t("episode.progressLogs")}</p>
        {logContent}
      </div>
    );
  }

  return (
    <details className="mt-2 mb-3">
      <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
        {t("episode.progressLogs")}
      </summary>
      <div className="mt-1">{logContent}</div>
    </details>
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
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [ttsModel, setTtsModel] = useState("");
  const [ttsVoice, setTtsVoice] = useState("");
  const [videoTargets, setVideoTargets] = useState<Set<string>>(new Set(["all"]));
  const [totalCost, setTotalCost] = useState<number | null>(null);

  useEffect(() => {
    api.getSettings().then((res) => {
      const val = res.data.settings.google_drive_enabled ?? "";
      setDriveEnabled(val.toLowerCase() === "true");
    }).catch(() => {});
  }, []);

  useEffect(() => {
    api.getEpisodeCosts(episodeId).then((res) => {
      setTotalCost(res.data.total_cost_usd);
    }).catch(() => {});
  }, [episodeId]);

  if (loading) return <p className="text-gray-500">{t("episode.loading")}</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!episode) return <p className="text-gray-500">{t("episode.notFound")}</p>;

  const steps = episode.pipeline_steps;
  const activeStep: PipelineStep | undefined = selectedStep
    ? steps.find((s) => s.step_name === selectedStep)
    : undefined;

  const canRunStep = (step: PipelineStep | undefined): boolean => {
    if (!step) return false;
    return step.status === "pending" || step.status === "rejected" || step.status === "approved" || step.status === "needs_approval";
  };

  const handleRunStep = async () => {
    if (!selectedStep) return;
    setRunningStep(true);
    try {
      const body: { tts_model?: string; tts_voice?: string; video_targets?: string[] } = {};
      if (selectedStep === "voice") {
        if (ttsModel) body.tts_model = ttsModel;
        if (ttsVoice) body.tts_voice = ttsVoice;
      }
      if (selectedStep === "video" && !videoTargets.has("all") && videoTargets.size > 0) {
        body.video_targets = Array.from(videoTargets);
      }
      await api.runStep(episodeId, selectedStep, Object.keys(body).length > 0 ? body : undefined);
      // Backend launches background task and returns immediately.
      // Poll until the step status changes from pending to running (or beyond).
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const ep = await refetch();
        const updated = ep?.pipeline_steps.find((s) => s.step_name === selectedStep);
        if (updated && updated.status !== "pending" && updated.status !== "rejected") break;
      }
    } catch {
      await refetch();
    } finally {
      setRunningStep(false);
    }
  };

  const saveTitle = async () => {
    if (!episode || !titleDraft.trim() || titleDraft === episode.title) {
      setEditingTitle(false);
      return;
    }
    try {
      await api.updateEpisode(episode.id, { title: titleDraft.trim() });
      await refetch();
      setEditingTitle(false);
    } catch (err) {
      console.error("Failed to update title:", err);
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
          {editingTitle ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onKeyDown={async (e) => {
                  if (e.key === "Enter") {
                    await saveTitle();
                  } else if (e.key === "Escape") {
                    setEditingTitle(false);
                  }
                }}
                className="text-xl font-semibold text-gray-800 border-b-2 border-blue-500 outline-none bg-transparent px-0 py-0.5 min-w-[300px]"
                autoFocus
              />
              <button onClick={saveTitle} className="text-xs text-blue-600 hover:underline cursor-pointer">{t("stepData.script.save")}</button>
              <button onClick={() => setEditingTitle(false)} className="text-xs text-gray-500 hover:underline cursor-pointer">{t("stepData.script.cancel")}</button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group">
              <h2 className="text-xl font-semibold text-gray-800">{episode.title}</h2>
              <button
                onClick={() => { setTitleDraft(episode.title); setEditingTitle(true); }}
                className="text-gray-400 hover:text-blue-600 cursor-pointer"
                title={t("episode.editTitle")}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                </svg>
              </button>
            </div>
          )}
          <p className="text-sm text-gray-500 mt-1">
            {t("episode.id")}: #{episode.id} / {t("episode.status")}: {t(`episodeStatus.${episode.status}`)} / {t("episode.createdAt")}:{" "}
            {new Date(episode.created_at).toLocaleDateString("ja-JP")}
            {totalCost !== null && totalCost > 0 && (
              <>
                {" / "}
                <Link to="/costs" className="text-blue-600 hover:text-blue-800 hover:underline" title={t("episode.viewCostDetails")}>
                  {t("episode.totalCost")}: ${totalCost.toFixed(4)}
                </Link>
              </>
            )}
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

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h3 className="text-sm font-medium text-gray-600">{t("episode.pipeline")}</h3>
          {!activeStep && selectedStep === null && (
            <span className="text-xs text-gray-400">{t("episode.selectStep")}</span>
          )}
        </div>
        <PipelineView
          steps={steps}
          selectedStep={selectedStep}
          onSelectStep={setSelectedStep}
        />
      </div>

      {(episode.audio_path || episode.video_path) && (() => {
        const videoStep = steps.find((s) => s.step_name === "video");
        const videoOutputData = videoStep?.output_data as Record<string, unknown> | null;
        const thumbnailPath = videoOutputData?.thumbnail_path as string | undefined;
        const srtPath = videoOutputData?.srt_path as string | undefined;
        // Cache bust: use step completed_at so re-runs show fresh media
        const mediaCacheBust = videoStep?.completed_at || steps.find((s) => s.step_name === "voice")?.completed_at || "";
        const cb = mediaCacheBust ? `?t=${new Date(mediaCacheBust).getTime()}` : "";
        return (
        <PersistentDetails storageKey="episode-media-open" defaultOpen className="mb-6 bg-white rounded-lg shadow" summary={t("episode.media")}>
          <div className="px-4 pb-4 space-y-3">
          {episode.audio_path && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.audio")}</p>
              <audio controls className="w-full" src={`${MEDIA_BASE_URL}/${episode.audio_path}${cb}`} />
              <a
                href={`${MEDIA_BASE_URL}/${episode.audio_path}`}
                download
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                {t("episode.download")}
              </a>
            </div>
          )}
          {/* Shorts audio (right after main audio) */}
          {(() => {
            const voiceStep2 = steps.find((s) => s.step_name === "voice");
            const voiceOutput = voiceStep2?.output_data as Record<string, unknown> | null;
            const shorts = voiceOutput?.shorts as Array<{news_item_id: number; file: string; duration_seconds: number; mode: string; caption?: string}> | undefined;
            if (!shorts?.length) return null;
            return (
              <div>
                <p className="text-xs text-gray-500 mb-1">{t("episode.voiceShorts")}</p>
                <div className="space-y-2">
                  {shorts.map((s, i) => (
                    <div key={i} className="border border-orange-200 rounded-lg p-2 bg-orange-50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-orange-700">Short #{i + 1}</span>
                        <span className="text-xs text-gray-500">{s.duration_seconds}s</span>
                      </div>
                      <audio controls className="w-full h-8" src={`${MEDIA_BASE_URL}/${s.file}`} />
                      {s.caption && <p className="text-xs text-gray-500 mt-1 italic">{s.caption}</p>}
                      <a href={`${MEDIA_BASE_URL}/${s.file}`} download className="text-xs text-blue-600 hover:underline mt-1 inline-block">{t("episode.download")}</a>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
          {episode.video_path && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.video")}</p>
              <video controls className="max-w-lg rounded" src={`${MEDIA_BASE_URL}/${episode.video_path}${cb}`} />
              <a
                href={`${MEDIA_BASE_URL}/${episode.video_path}`}
                download
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                {t("episode.download")}
              </a>
            </div>
          )}
          {/* Shorts videos */}
          {(() => {
            const shortsVideos = videoOutputData?.shorts as ShortsVideo[] | undefined;
            if (!shortsVideos?.length) return null;
            return (
              <div>
                <p className="text-xs text-gray-500 mb-1">{t("episode.shortsVideos")}</p>
                <div className="space-y-3">
                  {shortsVideos.map((sv, i) => (
                    <div key={i} className="border border-purple-200 rounded-lg p-3 bg-purple-50">
                      <div className="flex items-start gap-3">
                        <video
                          controls
                          className="rounded border"
                          style={{ aspectRatio: "9/16", maxHeight: "400px" }}
                          src={`${MEDIA_BASE_URL}/${sv.video_path}${cb}`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-purple-700">Short #{i + 1}</span>
                            <span className="text-xs text-gray-500">{sv.duration_seconds.toFixed(1)}s / {sv.provider}</span>
                          </div>
                          {sv.metadata && (
                            <div className="space-y-1">
                              {sv.metadata.title && (
                                <div className="flex items-center gap-1">
                                  <p className="text-sm font-medium text-gray-800 truncate">{sv.metadata.title}</p>
                                  <button
                                    onClick={() => navigator.clipboard.writeText(sv.metadata?.title ?? "")}
                                    className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer shrink-0"
                                  >{t("stepData.video.copy")}</button>
                                </div>
                              )}
                              {sv.metadata.description && (
                                <div className="flex items-center gap-1">
                                  <p className="text-xs text-gray-600 line-clamp-2">{sv.metadata.description}</p>
                                  <button
                                    onClick={() => navigator.clipboard.writeText(sv.metadata?.description ?? "")}
                                    className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer shrink-0"
                                  >{t("stepData.video.copy")}</button>
                                </div>
                              )}
                              {sv.metadata.hashtags && sv.metadata.hashtags.length > 0 && (
                                <div className="flex items-center gap-1 flex-wrap">
                                  {sv.metadata.hashtags.map((tag, j) => (
                                    <span key={j} className="px-1.5 py-0.5 rounded-full text-xs bg-purple-100 text-purple-700">{tag}</span>
                                  ))}
                                  <button
                                    onClick={() => navigator.clipboard.writeText(sv.metadata?.hashtags?.join(" ") ?? "")}
                                    className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer"
                                  >{t("stepData.video.copy")}</button>
                                </div>
                              )}
                            </div>
                          )}
                          <a href={`${MEDIA_BASE_URL}/${sv.video_path}`} download className="text-xs text-blue-600 hover:underline mt-1 inline-block">{t("episode.download")}</a>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
          {thumbnailPath && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.thumbnail")}</p>
              <img src={`${MEDIA_BASE_URL}/${thumbnailPath}${cb}`} alt="Thumbnail" className="w-64 rounded border" />
              <a
                href={`${MEDIA_BASE_URL}/${thumbnailPath}`}
                download
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                {t("episode.download")}
              </a>
            </div>
          )}
          {srtPath && (
            <div>
              <p className="text-xs text-gray-500 mb-1">{t("episode.subtitle")}</p>
              <a
                href={`${MEDIA_BASE_URL}/${srtPath}`}
                download
                className="text-xs text-blue-600 hover:underline inline-block"
              >
                {t("episode.download")} (SRT)
              </a>
            </div>
          )}
          {(() => {
            const illustrationPaths = videoOutputData?.illustration_paths as string[] | undefined;
            if (!illustrationPaths?.length) return null;
            return (
              <div>
                <p className="text-xs text-gray-500 mb-1">{t("episode.illustrations")}</p>
                <div className="flex gap-2 flex-wrap">
                  {illustrationPaths.map((p, i) => (
                    <img key={i} src={`${MEDIA_BASE_URL}/${p}${cb}`} alt={`illustration ${i + 1}`} className="w-32 rounded border" />
                  ))}
                </div>
              </div>
            );
          })()}
          </div>
        </PersistentDetails>
        );
      })()}

      {showDriveExport && (
        <PersistentDetails storageKey="episode-drive-open" className="mb-6 bg-white rounded-lg shadow" summary="Google Drive">
          <div className="px-4 pb-4 flex items-center gap-3 flex-wrap">
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
        </PersistentDetails>
      )}

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
                  {runningStep
                    ? t("episode.running")
                    : activeStep.status === "approved" || activeStep.status === "needs_approval"
                      ? t("episode.reRunStep")
                      : t("episode.runStep")}
                </button>
              )}
            </div>
          </div>

          {activeStep.step_name === "script" && canRunStep(activeStep) && (
            <div className="mb-3 flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={episode.shorts_enabled}
                  onChange={async (e) => {
                    await api.updateEpisode(episode.id, { shorts_enabled: e.target.checked });
                    refetch();
                  }}
                  className="rounded border-gray-300 text-orange-500 focus:ring-orange-500"
                />
                {t("episode.shortsEnabled")}
              </label>
            </div>
          )}

          {activeStep.step_name === "voice" && canRunStep(activeStep) && (
            <div className="mb-3 flex items-center gap-3 flex-wrap">
              <label className="text-xs text-gray-500">
                {t("episode.voiceModel")}
                <select
                  value={ttsModel}
                  onChange={(e) => setTtsModel(e.target.value)}
                  className="ml-1 text-sm border rounded px-2 py-1"
                >
                  <option value="">{t("episode.voiceDefault")}</option>
                  {GEMINI_TTS_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-gray-500">
                {t("episode.voiceVoice")}
                <select
                  value={ttsVoice}
                  onChange={(e) => setTtsVoice(e.target.value)}
                  className="ml-1 text-sm border rounded px-2 py-1"
                >
                  <option value="">{t("episode.voiceDefault")}</option>
                  {GEMINI_TTS_VOICES.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {activeStep.step_name === "video" && canRunStep(activeStep) && activeStep.output_data && (
            <div className="mb-3">
              <p className="text-xs text-gray-500 mb-1.5">{t("episode.videoTargets")}</p>
              <div className="flex items-center gap-3 flex-wrap">
                {(["all", "images", "video", "metadata", "shorts"] as const).map((target) => (
                  <label key={target} className="flex items-center gap-1 text-sm text-gray-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={videoTargets.has(target)}
                      disabled={target !== "all" && videoTargets.has("all")}
                      onChange={(e) => {
                        setVideoTargets((prev) => {
                          const next = new Set(prev);
                          if (target === "all") {
                            if (e.target.checked) {
                              return new Set(["all"]);
                            } else {
                              next.delete("all");
                              return next;
                            }
                          }
                          if (e.target.checked) {
                            next.add(target);
                            next.delete("all");
                          } else {
                            next.delete(target);
                            if (next.size === 0) next.add("all");
                          }
                          return next;
                        });
                      }}
                      className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                    />
                    {t(`episode.videoTarget_${target}`)}
                  </label>
                ))}
              </div>
            </div>
          )}

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

    </div>
  );
}
