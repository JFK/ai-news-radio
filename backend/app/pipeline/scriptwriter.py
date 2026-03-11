"""Step 4: Script generation pipeline step."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider
from app.services.prompt_loader import get_active_prompt, register_default

logger = logging.getLogger(__name__)

PROMPT_KEY_ITEM = "script_item"
PROMPT_KEY_EPISODE = "script_episode"

SCRIPT_ITEM_SYSTEM_PROMPT = """\
あなたはラジオニュース番組「一緒に考えるラジオ」の台本を書くベテラン放送作家です。
リスナーが家事や通勤の「ながら聴き」でも思わず手を止めるような、引き込む台本を書いてください。

## 台本の必須要素（順序はニュースに最適な形で自由に組み替えてよい）
- **つかみ（冒頭10秒）**: リスナーの注意を一瞬でつかむ。以下のいずれかのパターンで入ること:
  - 意外な事実・数字から入る（「実は〇〇、知っていましたか？」）
  - 身近なシーンから入る（「今朝コンビニで〇〇を買った方、実は…」）
  - 核心を突く問いから入る（「〇〇は本当に必要なのでしょうか」）
  - 対比・ギャップで入る（「〇〇と言われていますが、現場では…」）
  ※ 毎回同じパターンにならないよう、ニュースの性質に合わせて変えること
- **背景・ストーリー（30秒程度）**: 「なぜこうなったか→今どうなっているか→今後どうなりそうか」の流れで。具体的なエピソード（人・場所・場面）を1つ入れると臨場感が出る。専門用語はその場で噛み砕く
- **多角的な視点（30秒程度）**: 異なる立場からの見方を最低2つ。「〇〇の立場からすると…、一方で△△の側から見ると…」のように対比で示す。数字は身近なスケールに置き換える（「〇〇億円、つまり県民一人あたり〇〇円」など）。情報源の信頼性にも触れる
- **あなたの生活との接点（15秒程度）**: 「これ、実は皆さんの〇〇に関係してくるんです」のように、リスナー自身の生活に引きつける
- **問いかけ・余韻（10秒程度）**: 断定せず、リスナーが自分で考えたくなる問いや視点を残す

## ストーリーテリングの技法（積極的に使うこと）
- **Before / After**: 「以前は〇〇だったのが、今は△△に」で変化を際立たせる
- **具体→抽象**: まず具体的なエピソードで興味を引き、そこから全体像へ広げる
- **意外な接続**: 一見無関係に見える2つの事実をつなげて「実はこういう関係がある」と示す
- **スケール変換**: 大きな数字を実感できるサイズに（「東京ドーム〇個分」「1日あたり〇〇円」）

## テンポと緩急
- 重要なポイントの前に一拍おく（「…ここからが重要なんですが」「さて」）
- 情報が続く箇所では短い文でテンポよく。考えさせる箇所ではゆったりした文で
- 「〜ですよね。でも実は…」のような転換で聴き手の予想を裏切る瞬間を作る

## 重要：出力形式
- 台本は音声としてそのまま読み上げられます
- 【導入】【背景解説】【クリティカル分析】などのセクション見出し・ヘッダーは絶対に含めないこと
- （10秒）（30秒）などの秒数指示も含めないこと
- 各パートは見出しなしで自然な語りとしてつなげること

## 禁止事項
- セクション名・見出し・秒数指示の出力（例: 【導入（10秒）】）
- 情報源不明の断定
- 煽り・恐怖訴求（「大変なことになります」「危険です」のような不安を煽る表現）
- 一方的な立場の押し付け
- 専門用語の説明なし使用
- 毎回同じ導入パターンの繰り返し

## 話し方
- 親しみやすいが知的なトーン。友人に話すように、でも裏付けはしっかり
- 「〜ですね」「〜なんです」など、ラジオらしい語りかけ口調
- 時に「ちょっと驚きませんか？」「ここ、面白いんですが」など、リスナーに話しかける
- 難しい数字は身近なスケールに置き換える

## 読みがなルール
- 難読固有名詞（地名・人名・組織名・専門用語）は初出時に丸カッコ内にひらがなで読みを補記する
  - 例: 「健軍（けんぐん）駐屯地」「菊陽町（きくようまち）」「合志市（こうしし）」
- 一般的な漢字（熊本、東京、政府、大臣など）は補記不要
- 2回目以降の出現では補記しない
- 数字の読みは補記不要（音声合成が対応済み）

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "script_text": "台本の全文テキスト"
}"""

SCRIPT_EPISODE_SYSTEM_PROMPT = """\
あなたはラジオニュース番組「一緒に考えるラジオ」の構成作家です。

個別のニュース台本が用意されています。これらを1つの番組として、リスナーが最後まで聴きたくなる構成にしてください。

## 番組コンセプト
「ニュースを読むだけじゃない。一緒に考えるラジオ。」

## 構成要素

### 1. オープニング（30秒程度）
- 挨拶のあと、今日のラインナップの中から最もインパクトのある話題を1つだけチラ見せして期待感を作る
- 「今日は〇〇のニュースから始めましょう」のような平坦な紹介ではなく、「今日、ちょっと気になるニュースがあるんです」のように好奇心を刺激する
- 全トピックの羅列は避け、1つのフックで「続きを聴きたい」と思わせる

### 2. つなぎ（各ニュース間）
- 単なる「次のニュースです」は禁止
- 前のニュースと次のニュースの間に、以下のいずれかで橋を架ける:
  - テーマの共通点（「さっきの〇〇と実はつながる話なんですが」）
  - 対比（「〇〇の話をしましたが、今度はまったく違う角度から」）
  - リスナーの気持ちの転換（「少し重い話が続きましたね。次は少し明るい話題です」）
- つなぎ自体が短い「ミニコンテンツ」として面白いこと

### 3. エンディング（20秒程度）
- 番組全体を通して浮かび上がるテーマや問いを提示する
- 個別ニュースの要約の繰り返しは避ける
- リスナーが番組後も考え続けたくなる余韻を残す
- 「また次回」の定型句だけで終わらず、最後まで知的な刺激を

## 番組全体のテンポ設計
- 重い話題と軽い話題を交互に配置する意識を持つ（つなぎで調整）
- 番組の中盤にクライマックス（最も考えさせるニュース）を置くイメージ

## 読みがなルール
- 難読固有名詞は初出時に丸カッコ内にひらがなで読みを補記する
  - 例: 「健軍（けんぐん）」「菊陽町（きくようまち）」
- 一般的な漢字は補記不要。2回目以降も補記しない

## 重要：出力形式
- 台本は音声としてそのまま読み上げられます
- セクション見出し・ヘッダー・秒数指示は絶対に含めないこと

## 画像プロンプト生成
番組の内容に合ったビジュアルを生成するため、以下の2つの英語プロンプトも生成してください:
- thumbnail_prompt: YouTube サムネイル向け。番組の主要テーマを象徴するシンプルで目を引く構図
- background_prompt: 動画の背景画像向け。暗めでテキストオーバーレイに適した落ち着いたトーン

どちらも「写真的・イラスト的なビジュアルのみ」で、テキスト・文字・ロゴは絶対に含めないでください。

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "opening": "オープニングの台本テキスト",
  "transitions": ["ニュース1→2のつなぎ", "ニュース2→3のつなぎ"],
  "ending": "エンディングの台本テキスト",
  "thumbnail_prompt": "English prompt for thumbnail image, no text/letters/words",
  "background_prompt": "English prompt for dark background image, no text/letters/words"
}"""

register_default(PROMPT_KEY_ITEM, SCRIPT_ITEM_SYSTEM_PROMPT)
register_default(PROMPT_KEY_EPISODE, SCRIPT_EPISODE_SYSTEM_PROMPT)


class ScriptwriterStep(BaseStep):
    """Generate radio scripts from analyzed news articles."""

    @property
    def step_name(self) -> StepName:
        return StepName.SCRIPT

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Generate scripts in two phases.

        Phase 1: Per-article script generation (N AI calls)
        Phase 2: Episode composition (1 AI call)
        """
        provider, model = get_step_provider(self.step_name.value)
        item_prompt, item_prompt_version = await get_active_prompt(session, PROMPT_KEY_ITEM)
        episode_prompt, episode_prompt_version = await get_active_prompt(session, PROMPT_KEY_EPISODE)
        item_scripts: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        all_items = await self._get_news_items(episode_id, session)

        # Filter out items with low fact-check reliability (unverified or disputed).
        # Items with fact_check_status=None (not yet checked) are kept.
        # Filter out non-primary group members (they are merged into the primary).
        items = [
            item for item in all_items
            if item.fact_check_status not in ("unverified", "disputed")
            and (item.is_group_primary is True or item.group_id is None)
        ]
        skipped = len(all_items) - len(items)
        if skipped:
            logger.info(
                "Episode %d: skipped %d items (low reliability or non-primary group members)",
                episode_id, skipped,
            )

        if not items:
            raise ValueError("No reliable news items to generate scripts for")

        # Phase 1: per-article scripts
        for item in items:
            result = await self._script_item(item, provider, model, item_prompt, session, episode_id, all_items)
            item_scripts.append(result)
            total_input_tokens += result["input_tokens"]
            total_output_tokens += result["output_tokens"]

        # Phase 2: episode composition
        episode_script = await self._compose_episode(
            item_scripts, provider, model, episode_prompt, session, episode_id
        )
        total_input_tokens += episode_script["input_tokens"]
        total_output_tokens += episode_script["output_tokens"]

        await session.commit()

        logger.info("Episode %d: scripted %d items + episode composition", episode_id, len(items))

        result = {
            "items_scripted": len(item_scripts),
            "item_scripts": [{"news_item_id": s["news_item_id"], "title": s["title"]} for s in item_scripts],
            "episode_script": episode_script["full_script"],
            "opening": episode_script["opening"],
            "transitions": episode_script["transitions"],
            "ending": episode_script["ending"],
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }
        if episode_script.get("thumbnail_prompt"):
            result["thumbnail_prompt"] = episode_script["thumbnail_prompt"]
        if episode_script.get("background_prompt"):
            result["background_prompt"] = episode_script["background_prompt"]
        if item_prompt_version is not None:
            result["prompt_versions"] = result.get("prompt_versions", {})
            result["prompt_versions"]["script_item"] = item_prompt_version
        if episode_prompt_version is not None:
            result["prompt_versions"] = result.get("prompt_versions", {})
            result["prompt_versions"]["script_episode"] = episode_prompt_version
        return result

    async def _script_item(
        self,
        item: NewsItem,
        provider,
        model: str,
        system_prompt: str,
        session: AsyncSession,
        episode_id: int,
        all_items: list[NewsItem] | None = None,
    ) -> dict:
        """Generate a script for a single news item."""
        analysis_info = ""
        if item.analysis_data:
            ad = item.analysis_data
            perspectives_text = ""
            for p in ad.get("perspectives", []):
                perspectives_text += f"  - {p.get('standpoint', '')}: {p.get('argument', '')}\n"

            analysis_info = (
                f"\n\n分析結果:\n"
                f"- 背景: {ad.get('background', '(なし)')}\n"
                f"- なぜ今: {ad.get('why_now', '(なし)')}\n"
                f"- 複数視点:\n{perspectives_text}"
                f"- データ検証: {ad.get('data_validation', '(なし)')}\n"
                f"- 生活への影響: {ad.get('impact', '(なし)')}\n"
                f"- 不確実性: {ad.get('uncertainties', '(なし)')}"
            )
            if ad.get("source_comparison"):
                analysis_info += f"\n- ソース間比較: {ad['source_comparison']}"

        # Add group member sources for primary articles
        group_sources_info = ""
        if item.is_group_primary and item.group_id is not None and all_items:
            group_members = [
                it for it in all_items
                if it.group_id == item.group_id and it.id != item.id
            ]
            if group_members:
                sources = [f"- {it.source_name}: {it.title} ({it.source_url})" for it in group_members]
                group_sources_info = (
                    f"\n\n同じニュースの他のソース（{len(group_members) + 1}社が報道）:\n"
                    + "\n".join(sources)
                )

        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"要約: {item.summary or '(なし)'}"
            f"{analysis_info}"
            f"{group_sources_info}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=system_prompt,
        )

        data = parse_json_response(response.content)
        item.script_text = data.get("script_text", "")

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
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def _compose_episode(
        self,
        item_scripts: list[dict],
        provider,
        model: str,
        system_prompt: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Compose the full episode script with opening, transitions, and ending."""
        # Build summary of all news items for the composition prompt
        items_summary = ""
        for i, script in enumerate(item_scripts, 1):
            items_summary += f"\nニュース{i}: {script['title']}"

        # Reload items to get their script_text
        result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode_id).order_by(NewsItem.id))
        items = list(result.scalars().all())

        # Only include items that have scripts (excludes non-primary group members)
        scripted_items = [item for item in items if item.script_text]
        scripts_text = ""
        for i, item in enumerate(scripted_items, 1):
            scripts_text += f"\n\n--- ニュース{i}: {item.title} ---\n{item.script_text}"

        prompt = f"今日のニュース一覧:{items_summary}\n\n各ニュースの台本:{scripts_text}"

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=system_prompt,
        )

        data = parse_json_response(response.content)

        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        # Build full episode script
        opening = data.get("opening", "")
        transitions = data.get("transitions", [])
        ending = data.get("ending", "")

        full_script_parts = [opening]
        for i, item in enumerate(scripted_items):
            full_script_parts.append(item.script_text)
            if i < len(transitions):
                full_script_parts.append(transitions[i])
        full_script_parts.append(ending)

        full_script = "\n\n".join(full_script_parts)

        return {
            "opening": opening,
            "transitions": transitions,
            "ending": ending,
            "full_script": full_script,
            "thumbnail_prompt": data.get("thumbnail_prompt", ""),
            "background_prompt": data.get("background_prompt", ""),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
