import { useTranslation } from "react-i18next";
import type { PipelineStep, StepName, StepStatus } from "../types";

const STEP_ORDER: StepName[] = [
  "collection",
  "factcheck",
  "analysis",
  "script",
  "voice",
  "video",
];

const STATUS_STYLES: Record<StepStatus, string> = {
  pending: "bg-gray-100 border-gray-300 text-gray-500",
  running: "bg-blue-50 border-blue-400 text-blue-700",
  needs_approval: "bg-yellow-50 border-yellow-400 text-yellow-700",
  approved: "bg-green-50 border-green-400 text-green-700",
  rejected: "bg-red-50 border-red-400 text-red-700",
};

interface Props {
  steps: PipelineStep[];
  selectedStep: StepName | null;
  onSelectStep: (stepName: StepName) => void;
}

export default function PipelineView({ steps, selectedStep, onSelectStep }: Props) {
  const { t } = useTranslation();
  const stepMap = new Map(steps.map((s) => [s.step_name, s]));

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-2">
      {STEP_ORDER.map((name, i) => {
        const step = stepMap.get(name);
        const status: StepStatus = step?.status ?? "pending";
        const isSelected = selectedStep === name;

        return (
          <div key={name} className="flex items-center">
            <button
              onClick={() => onSelectStep(name)}
              className={`
                relative flex flex-col items-center px-3 py-2 rounded-lg border-2 min-w-[90px] transition-all cursor-pointer
                ${STATUS_STYLES[status]}
                ${isSelected ? "ring-2 ring-offset-1 ring-blue-500" : ""}
                ${status === "running" ? "animate-pulse" : ""}
              `}
            >
              <span className="text-xs font-medium whitespace-nowrap">{t(`steps.${name}`)}</span>
              <span className="text-[10px] mt-0.5 opacity-75">{t(`stepStatus.${status}`)}</span>
            </button>
            {i < STEP_ORDER.length - 1 && (
              <div className="mx-0.5 text-gray-300 text-lg select-none">&rarr;</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
