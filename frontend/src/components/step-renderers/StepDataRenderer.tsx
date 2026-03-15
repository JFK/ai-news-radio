import type { StepName, NewsItem } from "../../types";
import CollectionRenderer from "./CollectionRenderer";
import FactcheckRenderer from "./FactcheckRenderer";
import AnalysisRenderer from "./AnalysisRenderer";
import ScriptRenderer from "./ScriptRenderer";
import VoiceRenderer from "./VoiceRenderer";
import VideoRenderer from "./VideoRenderer";

interface Props {
  stepName: StepName;
  outputData: Record<string, unknown>;
  newsItems: NewsItem[];
  episodeId?: number;
  editable?: boolean;
  onUpdated?: () => void;
}

export default function StepDataRenderer({
  stepName,
  outputData,
  newsItems,
  episodeId,
  editable,
  onUpdated,
}: Props) {
  switch (stepName) {
    case "collection":
      return (
        <CollectionRenderer outputData={outputData} newsItems={newsItems} />
      );
    case "factcheck":
      return <FactcheckRenderer newsItems={newsItems} />;
    case "analysis":
      return <AnalysisRenderer newsItems={newsItems} />;
    case "script":
      return (
        <ScriptRenderer
          outputData={outputData}
          newsItems={newsItems}
          episodeId={episodeId ?? 0}
          editable={editable}
          onUpdated={onUpdated}
        />
      );
    case "voice":
      return <VoiceRenderer outputData={outputData} />;
    case "video":
      return <VideoRenderer outputData={outputData} />;
    default:
      return (
        <pre className="p-3 bg-gray-50 rounded border text-xs overflow-auto max-h-64">
          {JSON.stringify(outputData, null, 2)}
        </pre>
      );
  }
}
