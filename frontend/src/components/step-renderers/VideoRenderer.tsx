import { useState } from "react";
import { useTranslation } from "react-i18next";

interface YouTubeMetadata {
  title?: string;
  description?: string;
  tags?: string[];
}

interface Props {
  outputData: Record<string, unknown>;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer"
    >
      {copied ? "✓" : label}
    </button>
  );
}

export default function VideoRenderer({ outputData }: Props) {
  const { t } = useTranslation();
  const metadata = outputData.youtube_metadata as YouTubeMetadata | undefined;

  if (!metadata) return null;

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-medium text-gray-600">
        {t("stepData.video.youtubeMetadata")}
      </h4>

      {metadata.title && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-medium text-gray-500">
              {t("stepData.video.title")}
            </p>
            <CopyButton text={metadata.title} label={t("stepData.video.copy")} />
          </div>
          <p className="text-sm text-gray-800 bg-gray-50 rounded p-2 border">
            {metadata.title}
          </p>
        </div>
      )}

      {metadata.description && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-medium text-gray-500">
              {t("stepData.video.description")}
            </p>
            <CopyButton text={metadata.description} label={t("stepData.video.copy")} />
          </div>
          <pre className="text-sm text-gray-800 bg-gray-50 rounded p-3 border whitespace-pre-wrap max-h-64 overflow-y-auto">
            {metadata.description}
          </pre>
        </div>
      )}

      {metadata.tags && metadata.tags.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-medium text-gray-500">
              {t("stepData.video.tags")}
            </p>
            <CopyButton text={metadata.tags.join(", ")} label={t("stepData.video.copy")} />
          </div>
          <div className="flex flex-wrap gap-1">
            {metadata.tags.map((tag, i) => (
              <span
                key={i}
                className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
