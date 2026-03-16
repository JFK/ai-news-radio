import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { SpeakerProfile } from "../../types";

interface Props {
  outputData: Record<string, unknown>;
}

export default function VoiceRenderer({ outputData }: Props) {
  const { t } = useTranslation();
  const provider = outputData.provider as string | undefined;
  const model = outputData.model as string | undefined;
  const duration = outputData.duration_seconds as number | undefined;
  const sections = outputData.sections as { key: string; label: string; duration_seconds: number }[] | undefined;

  const [speakers, setSpeakers] = useState<SpeakerProfile[]>([]);
  useEffect(() => {
    api.getSpeakers().then((res) => setSpeakers(res.data)).catch(() => {});
  }, []);

  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {provider && (
          <div>
            <dt className="text-gray-500">{t("episode.voiceProvider")}</dt>
            <dd className="font-medium">{provider}</dd>
          </div>
        )}
        {model && (
          <div>
            <dt className="text-gray-500">{t("episode.voiceModel")}</dt>
            <dd className="font-medium">{model}</dd>
          </div>
        )}
        {speakers.length > 0 && (
          <div className="col-span-2">
            <dt className="text-gray-500">{t("episode.voiceVoice")}</dt>
            <dd className="font-medium">
              {speakers.map((s) => `${s.name} (${s.voice_name})`).join(" / ")}
            </dd>
          </div>
        )}
        {duration != null && (
          <div>
            <dt className="text-gray-500">{t("episode.voiceDuration")}</dt>
            <dd className="font-medium">{Math.floor(duration / 60)}m {Math.round(duration % 60)}s</dd>
          </div>
        )}
      </dl>
      {sections && sections.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
            {t("episode.voiceSections")} ({sections.length})
          </summary>
          <table className="mt-1 w-full text-xs">
            <tbody>
              {sections.map((s) => (
                <tr key={s.key} className="border-t">
                  <td className="py-1 text-gray-600">{s.label}</td>
                  <td className="py-1 text-right text-gray-500">{s.duration_seconds.toFixed(1)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}
