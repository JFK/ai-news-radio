import { useParams } from "react-router-dom";

export default function EpisodeDetail() {
  const { id } = useParams<{ id: string }>();

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-4">
        エピソード #{id}
      </h2>
      <p className="text-gray-600">
        パイプライン状態とニュース詳細がここに表示されます。
      </p>
    </div>
  );
}
