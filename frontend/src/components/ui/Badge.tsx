import { useTranslation } from "react-i18next";

export function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const color =
    score >= 4
      ? "bg-green-100 text-green-800"
      : score >= 3
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score}/5
    </span>
  );
}

export function StatusBadge({ status }: { status: string | null }) {
  const { t } = useTranslation();
  if (!status) return null;
  const color =
    status === "verified"
      ? "bg-green-100 text-green-800"
      : status === "unverified"
        ? "bg-red-100 text-red-800"
        : "bg-gray-100 text-gray-800";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {t(`stepData.factcheck.status_${status}`, status)}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const color =
    severity === "high"
      ? "bg-red-100 text-red-800"
      : severity === "medium"
        ? "bg-yellow-100 text-yellow-800"
        : "bg-green-100 text-green-800";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {severity}
    </span>
  );
}
