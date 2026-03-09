"""Common test helpers shared across test files."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsItem
from app.pipeline.engine import PipelineEngine


async def create_episode_with_items(
    session: AsyncSession,
    n_items: int = 2,
    with_factcheck: bool = False,
    with_analysis: bool = False,
) -> tuple[int, list[int]]:
    """Create an episode with N news items.

    Args:
        session: Database session.
        n_items: Number of news items to create.
        with_factcheck: Populate fact_check fields on items.
        with_analysis: Populate analysis_data (implies with_factcheck).

    Returns:
        Tuple of (episode_id, list of item_ids).
    """
    if with_analysis:
        with_factcheck = True

    engine = PipelineEngine()
    episode = await engine.create_episode("Test Episode", session)

    item_ids = []
    for i in range(n_items):
        item = NewsItem(
            episode_id=episode.id,
            title=f"テストニュース {i}",
            summary=f"テスト要約 {i}",
            source_url=f"https://example.com/news/{i}",
            source_name="TestSource",
        )
        if with_factcheck:
            item.fact_check_status = "verified"
            item.fact_check_score = 4
            item.fact_check_details = "ファクトチェック済み"
        if with_analysis:
            item.analysis_data = {
                "background": "テスト背景",
                "why_now": "テストの理由",
                "perspectives": [
                    {"standpoint": "行政側", "argument": "主張A", "basis": "根拠A"},
                    {"standpoint": "住民側", "argument": "主張B", "basis": "根拠B"},
                    {"standpoint": "専門家", "argument": "主張C", "basis": "根拠C"},
                ],
                "data_validation": "妥当",
                "impact": "影響あり",
                "uncertainties": "未確認事項あり",
            }
        session.add(item)
        await session.flush()
        item_ids.append(item.id)

    await session.commit()
    return episode.id, item_ids
