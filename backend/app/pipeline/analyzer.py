"""Step 3: Critical analysis pipeline step."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider
from app.services.prompt_loader import get_active_prompt, register_default

logger = logging.getLogger(__name__)

PROMPT_KEY = "analysis"
PROMPT_KEY_GROUP = "analysis_group"
PROMPT_KEY_GROUPING = "analysis_grouping"

ANALYSIS_SYSTEM_PROMPT = """\
あなたはニュースのクリティカル分析を行う専門家です。

与えられたニュース記事とファクトチェック結果に基づき、以下の観点で分析してください:

1. **背景・文脈**: このニュースの背景にある経緯や状況
2. **「なぜ今」**: このニュースが今出てきた理由、タイミングの意味
3. **複数視点**: 最低3つの異なる立場からの見方（賛成・反対・中立など）
4. **データ検証**: 記事中の数字やデータの妥当性、比較対象の適切さ
5. **生活への影響**: このニュースが一般市民の生活にどう影響するか
6. **不確実性**: わからないこと、確認できないことは明示する

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "background": "背景・文脈の説明",
  "why_now": "なぜ今このニュースが出てきたのかの分析",
  "perspectives": [
    {
      "standpoint": "立場（例: 行政側、住民側、専門家）",
      "argument": "その立場からの主張",
      "basis": "主張の根拠"
    }
  ],
  "data_validation": "データや数字の検証結果",
  "impact": "一般市民の生活への具体的な影響",
  "uncertainties": "不確実な点、確認できない点",
  "severity": "high または medium または low（ニュースの重要度）",
  "topics": ["関連トピックタグ1", "関連トピックタグ2"]
}"""

ANALYSIS_GROUPING_SYSTEM_PROMPT = """\
あなたはニュース記事の類似性を判定する専門家です。

複数のニュース記事が与えられます。同じ出来事・事件・話題を報じている記事をグループ化してください。

判定基準:
- 同一の事件・出来事を異なるメディアが報じている場合 → 同じグループ
- 関連はあるが別の出来事の場合 → 別グループ
- 1つの記事しかない話題 → グループ化しない（ungrouped）

代表記事（primary）の選定基準:
- 最も詳細で包括的な記事
- 信頼性の高いソース

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "groups": [
    {
      "group_id": 1,
      "reason": "グループ化の理由（例: 同じ事件の報道）",
      "primary_id": 5,
      "member_ids": [5, 12, 18]
    }
  ],
  "ungrouped_ids": [3, 7, 9]
}"""

ANALYSIS_GROUP_SYSTEM_PROMPT = """\
あなたはニュースのクリティカル分析を行う専門家です。

同じ出来事について複数のメディアが報じた記事が与えられます。
複数ソースからの情報を統合し、以下の観点で分析してください:

1. **背景・文脈**: このニュースの背景にある経緯や状況
2. **「なぜ今」**: このニュースが今出てきた理由、タイミングの意味
3. **複数視点**: 最低3つの異なる立場からの見方（賛成・反対・中立など）
4. **データ検証**: 記事中の数字やデータの妥当性、比較対象の適切さ。ソース間で数字が異なる場合はその違いを指摘
5. **生活への影響**: このニュースが一般市民の生活にどう影響するか
6. **不確実性**: わからないこと、確認できないことは明示する
7. **ソース間比較**: 各メディアの報道の一致点と相違点を明記

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "background": "背景・文脈の説明",
  "why_now": "なぜ今このニュースが出てきたのかの分析",
  "perspectives": [
    {
      "standpoint": "立場（例: 行政側、住民側、専門家）",
      "argument": "その立場からの主張",
      "basis": "主張の根拠"
    }
  ],
  "data_validation": "データや数字の検証結果（ソース間の違いを含む）",
  "impact": "一般市民の生活への具体的な影響",
  "uncertainties": "不確実な点、確認できない点",
  "source_comparison": "各ソース間の報道の一致点・相違点",
  "severity": "high または medium または low（ニュースの重要度）",
  "topics": ["関連トピックタグ1", "関連トピックタグ2"]
}"""

register_default(PROMPT_KEY, ANALYSIS_SYSTEM_PROMPT)
register_default(PROMPT_KEY_GROUPING, ANALYSIS_GROUPING_SYSTEM_PROMPT)
register_default(PROMPT_KEY_GROUP, ANALYSIS_GROUP_SYSTEM_PROMPT)


class AnalyzerStep(BaseStep):
    """Critically analyze news articles using AI."""

    @property
    def step_name(self) -> StepName:
        return StepName.ANALYSIS

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Analyze each NewsItem for the episode.

        Groups similar articles, then analyzes each group/item.
        Idempotent: re-running resets grouping and overwrites previous results.
        """
        provider, model = get_step_provider(self.step_name.value)
        system_prompt, prompt_version = await get_active_prompt(session, PROMPT_KEY)
        results: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        items = await self._get_news_items(episode_id, session)

        # Idempotent: reset grouping fields
        for item in items:
            item.group_id = None
            item.is_group_primary = None

        # Detect groups of similar articles
        await self.log_progress(episode_id, f"{len(items)}件の記事をグループ分析中")
        groups_info = await self._detect_groups(items, provider, model, session, episode_id)

        # Build lookup: item_id -> NewsItem
        item_by_id = {item.id: item for item in items}

        # Track which items are handled by groups
        grouped_ids: set[int] = set()

        # Analyze grouped items
        for i, group in enumerate(groups_info.get("groups", [])):
            group_items = [item_by_id[mid] for mid in group["member_ids"] if mid in item_by_id]
            if not group_items:
                continue
            grouped_ids.update(item.id for item in group_items)
            primary = group_items[0]
            await self.log_progress(episode_id, f"グループ「{primary.title[:30]}」({len(group_items)}件)を分析中")
            group_result = await self._analyze_group(
                group_items, group, provider, model, session, episode_id
            )
            results.append(group_result)
            total_input_tokens += group_result["input_tokens"]
            total_output_tokens += group_result["output_tokens"]

        # Analyze ungrouped items individually
        ungrouped = [item for item in items if item.id not in grouped_ids]
        for i, item in enumerate(ungrouped):
            await self.log_progress(episode_id, f"[{i + 1}/{len(ungrouped)}] 「{item.title[:30]}」を分析中")
            result = await self._analyze_item(item, provider, model, system_prompt, session, episode_id)
            results.append(result)
            total_input_tokens += result["input_tokens"]
            total_output_tokens += result["output_tokens"]

        await session.commit()

        severity_summary = {"high": 0, "medium": 0, "low": 0}
        for r in results:
            sev = r.get("severity", "medium")
            if sev in severity_summary:
                severity_summary[sev] += 1

        logger.info(
            "Episode %d: analyzed %d items (%d groups), severity: %s",
            episode_id,
            len(results),
            len(groups_info.get("groups", [])),
            severity_summary,
        )

        result_data: dict = {
            "items_analyzed": len(results),
            "groups": groups_info.get("groups", []),
            "results": results,
            "severity_summary": severity_summary,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }
        if prompt_version is not None:
            result_data["prompt_version"] = prompt_version
        return result_data

    async def _detect_groups(
        self,
        items: list[NewsItem],
        provider,
        model: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Detect groups of similar news articles using AI."""
        if len(items) < 2:
            return {"groups": [], "ungrouped_ids": [item.id for item in items]}

        grouping_prompt, _ = await get_active_prompt(session, PROMPT_KEY_GROUPING)

        # Build a lightweight prompt with just titles and summaries
        articles_text = ""
        for item in items:
            articles_text += (
                f"\n- ID: {item.id}\n"
                f"  タイトル: {item.title}\n"
                f"  ソース: {item.source_name}\n"
                f"  要約: {item.summary or '(なし)'}\n"
            )

        prompt = f"以下のニュース記事をグループ化してください:\n{articles_text}"

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=grouping_prompt,
        )

        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        try:
            data = parse_json_response(response.content)
        except Exception:
            logger.warning(
                "Episode %d: grouping AI returned invalid JSON, treating all items as ungrouped",
                episode_id,
            )
            return {"groups": [], "ungrouped_ids": [item.id for item in items]}

        # Validate and apply grouping to DB
        item_ids = {item.id for item in items}
        item_by_id = {item.id: item for item in items}
        claimed_ids: set[int] = set()  # Track items already assigned to a group
        valid_groups: list[dict] = []
        group_counter = 0

        for group in data.get("groups", []):
            primary_id = group.get("primary_id")
            member_ids = group.get("member_ids", [])

            # Filter to valid, unclaimed IDs (prevent overlapping groups)
            valid_members = [mid for mid in member_ids if mid in item_ids and mid not in claimed_ids]
            if len(valid_members) < 2:
                continue

            # Assign server-side group_id (episode-scoped sequential)
            group_counter += 1
            gid = group_counter

            # Ensure primary_id is in members
            if primary_id not in valid_members:
                primary_id = valid_members[0]

            claimed_ids.update(valid_members)

            for mid in valid_members:
                item_by_id[mid].group_id = gid
                item_by_id[mid].is_group_primary = (mid == primary_id)

            valid_groups.append({
                "group_id": gid,
                "reason": group.get("reason", ""),
                "primary_id": primary_id,
                "member_ids": valid_members,
            })

        logger.info(
            "Episode %d: detected %d groups from %d articles",
            episode_id,
            len(valid_groups),
            len(items),
        )

        return {"groups": valid_groups, "ungrouped_ids": [item.id for item in items if item.id not in claimed_ids]}

    async def _analyze_group(
        self,
        group_items: list[NewsItem],
        group_info: dict,
        provider,
        model: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Analyze a group of similar news articles together."""
        group_prompt, _ = await get_active_prompt(session, PROMPT_KEY_GROUP)

        primary_id = group_info["primary_id"]
        primary_item = next((item for item in group_items if item.id == primary_id), group_items[0])

        # Build combined prompt with all articles in the group
        articles_text = ""
        for item in group_items:
            fact_check_info = ""
            if item.fact_check_status:
                fact_check_info = (
                    f"\n  ファクトチェック: {item.fact_check_status} "
                    f"(スコア: {item.fact_check_score}/5)"
                )

            body_excerpt = ""
            if item.body:
                body_excerpt = f"\n本文（冒頭3000字）:\n{item.body[:3000]}"

            is_primary = " [代表記事]" if item.id == primary_id else ""
            articles_text += (
                f"\n--- 記事{is_primary} ---\n"
                f"タイトル: {item.title}\n"
                f"ソース: {item.source_name}\n"
                f"URL: {item.source_url}\n"
                f"要約: {item.summary or '(なし)'}"
                f"{body_excerpt}"
                f"{fact_check_info}\n"
            )

        prompt = (
            f"グループ化理由: {group_info.get('reason', '')}\n"
            f"以下の{len(group_items)}つの記事は同じ出来事に関する報道です:\n"
            f"{articles_text}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=group_prompt,
        )

        data = parse_json_response(response.content)

        # Store integrated analysis on the primary item
        primary_item.analysis_data = data

        # Mark non-primary items with merged_into marker
        for item in group_items:
            if item.id != primary_id:
                item.analysis_data = {"merged_into": primary_id}

        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        return {
            "news_item_id": primary_item.id,
            "title": primary_item.title,
            "group_id": group_info.get("group_id"),
            "member_ids": group_info.get("member_ids", []),
            "severity": data.get("severity", "medium"),
            "topics": data.get("topics", []),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def _analyze_item(
        self,
        item: NewsItem,
        provider,
        model: str,
        system_prompt: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Analyze a single news item."""
        # Include fact-check results in the prompt
        fact_check_info = ""
        if item.fact_check_status:
            fact_check_info = (
                f"\n\nファクトチェック結果:\n"
                f"- ステータス: {item.fact_check_status}\n"
                f"- スコア: {item.fact_check_score}/5\n"
                f"- 詳細: {item.fact_check_details or '(なし)'}"
            )

        body_excerpt = ""
        if item.body:
            body_excerpt = f"\n本文（冒頭3000字）:\n{item.body[:3000]}"

        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"URL: {item.source_url}\n"
            f"要約: {item.summary or '(なし)'}"
            f"{body_excerpt}"
            f"{fact_check_info}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=system_prompt,
        )

        data = parse_json_response(response.content)

        # Update the NewsItem in DB
        item.analysis_data = data

        # Record API usage
        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        return {
            "news_item_id": item.id,
            "title": item.title,
            "severity": data.get("severity", "medium"),
            "topics": data.get("topics", []),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
