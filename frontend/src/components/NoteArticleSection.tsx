import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

const MEDIA_BASE_URL = "/media";

interface NoteArticleSectionProps {
  episodeId: number;
  articleType: "analysis" | "video";
  existingMarkdown: string | null;
  onGenerated: () => void;
}

export default function NoteArticleSection({
  episodeId,
  articleType,
  existingMarkdown,
  onGenerated,
}: NoteArticleSectionProps) {
  const { t } = useTranslation();
  const [generating, setGenerating] = useState(false);
  const [markdown, setMarkdown] = useState<string | null>(existingMarkdown);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [success, setSuccess] = useState(false);
  const [generatingCover, setGeneratingCover] = useState(false);
  const [coverPath, setCoverPath] = useState<string | null>(null);
  const [coverError, setCoverError] = useState<string | null>(null);

  // Sync with parent props when existingMarkdown changes (e.g. after refetch)
  useEffect(() => {
    if (existingMarkdown) {
      setMarkdown(existingMarkdown);
    }
  }, [existingMarkdown]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setSuccess(false);
    try {
      const res = articleType === "analysis"
        ? await api.generateNoteAnalysis(episodeId)
        : await api.generateNoteVideo(episodeId);
      setMarkdown(res.data.markdown);
      setSuccess(true);
      onGenerated();
    } catch (err) {
      console.error("Note article generation failed:", err);
      setError(t("note.generateFailed"));
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!markdown) return;
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `note_${articleType}_ep${episodeId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleGenerateCover = async () => {
    setGeneratingCover(true);
    setCoverError(null);
    try {
      const res = await api.generateNoteCover(episodeId, articleType);
      setCoverPath(res.data.image_path);
    } catch (err) {
      console.error("Note cover image generation failed:", err);
      setCoverError(t("note.coverFailed"));
    } finally {
      setGeneratingCover(false);
    }
  };

  return (
    <div className="px-4 pb-4">
      <div className="flex items-center gap-3 flex-wrap mb-3">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
        >
          {generating
            ? t("note.generating")
            : markdown
              ? t("note.regenerate")
              : t("note.generate")}
        </button>
        {markdown && (
          <>
            <button
              onClick={handleCopy}
              className="px-3 py-1.5 bg-gray-600 text-white rounded-md text-sm font-medium hover:bg-gray-700 cursor-pointer"
            >
              {copied ? t("note.copied") : t("note.copy")}
            </button>
            <button
              onClick={handleDownload}
              className="px-3 py-1.5 bg-gray-600 text-white rounded-md text-sm font-medium hover:bg-gray-700 cursor-pointer"
            >
              {t("note.download")}
            </button>
          </>
        )}
        <button
          onClick={handleGenerateCover}
          disabled={generatingCover}
          className="px-3 py-1.5 bg-purple-600 text-white rounded-md text-sm font-medium hover:bg-purple-700 disabled:opacity-50 cursor-pointer"
        >
          {generatingCover
            ? t("note.coverGenerating")
            : coverPath
              ? t("note.coverRegenerate")
              : t("note.coverGenerate")}
        </button>
        {success && <span className="text-sm text-green-600">{t("note.generateSuccess")}</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
        {coverError && <span className="text-sm text-red-600">{coverError}</span>}
      </div>
      {coverPath && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1">{t("note.coverImage")}</p>
          <img
            src={`${MEDIA_BASE_URL}/${coverPath}?t=${Date.now()}`}
            alt="Cover"
            className="max-w-md rounded border"
          />
          <a
            href={`${MEDIA_BASE_URL}/${coverPath}`}
            download
            className="text-xs text-blue-600 hover:underline mt-1 inline-block"
          >
            {t("episode.download")}
          </a>
        </div>
      )}
      {markdown && (
        <pre className="p-3 bg-gray-50 rounded border text-sm overflow-auto max-h-96 whitespace-pre-wrap font-mono">
          {markdown}
        </pre>
      )}
    </div>
  );
}
