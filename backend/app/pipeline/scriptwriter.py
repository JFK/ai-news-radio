"""Step 4: Script generation pipeline step."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Episode, NewsItem, StepName
from app.models.speaker_profile import SpeakerProfile
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider
from app.services.prompt_loader import get_active_prompt, register_default

logger = logging.getLogger(__name__)

PROMPT_KEY_ITEM = "script_item"
PROMPT_KEY_ITEM_EXPLAINER = "script_item_explainer"
PROMPT_KEY_EPISODE = "script_episode"
PROMPT_KEY_SHORT_SOLO = "script_short_solo"
PROMPT_KEY_SHORT_EXPLAINER = "script_short_explainer"

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
- **AIなりの提案・問いかけ（15秒程度）**: まずAIの視点から1つ具体的なアイデアや解決策の方向性を提示し（「たとえばこんなアプローチもあるかもしれません」）、その上でリスナーが自分で考えたくなる問いを残す。断定はせず、あくまで「一緒に考える材料」として提案する

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

### 1. オープニング（30〜40秒程度）
- 時間帯に依存する挨拶（「こんにちは」「こんばんは」等）は使わない。リスナーはいつ聴くかわからない
- 「一緒に考えるラジオ、今日のニュースです」のように、番組名から自然に入る
- 今日取り上げるニュースのラインナップを簡潔に紹介する（「今日は〇〇、△△、そして□□についてお届けします」）
- 全体像を伝えたうえで、最もインパクトのある話題を1つフックにして期待感を作る（「中でも気になるのが…」）
- 単なる羅列ではなく、リスナーが「最後まで聴きたい」と思う導入にする

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
- thumbnail_prompt: YouTube サムネイル向け。番組の主要テーマを象徴するシンプルで目を引く構図。必ず人物（キャスター、関係者、市民など）を含めること
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

SCRIPT_ITEM_EXPLAINER_SYSTEM_PROMPT = """\
あなたはラジオニュース番組「一緒に考えるラジオ」の台本を書くベテラン放送作家です。
MC（進行役）と解説者（専門家）の2人が掛け合いでニュースを伝える対話形式の台本を書いてください。

## キャラクター
- **speaker_a（MC）**: 番組の進行役。リスナーの代わりに質問し、話題を展開する。親しみやすく、好奇心旺盛
- **speaker_b（解説者）**: 専門的な分析を提供。背景知識が豊富で、複雑な話題をわかりやすく解説する

## 対話の構成（自然な会話として組み立てること）
1. **つかみ**: MCがニュースを切り出す。リスナーの注意を引く入り方で
2. **背景・ストーリー**: 解説者が背景を説明。MCが「それってどういうことですか？」等と掘り下げる
3. **多角的な視点**: 解説者が複数の見方を提示。MCがリスナー目線で「つまり私たちにとっては…」と翻訳する
4. **生活への接点**: MCがリスナーの生活との関係を具体的に示す
5. **問いかけ**: 2人でリスナーに考える材料を提供して締める

## 対話のテクニック
- **リアクション必須**: MCは解説者の発言に必ず短いリアクションを入れてからの次の展開に移る（「なるほど」「それは意外ですね」「あ、そういうことか」「ちょっと待ってください、つまり…」）。解説者もMCの質問に「いい質問ですね」「まさにそこなんですが」等で受ける
- **相づち・うなずき**: 長めの説明の途中でも、MCが「ええ」「はい」「うんうん」と合いの手を入れる場面を作る（別ターンとして）
- 解説者は専門用語を使ったらすぐ噛み砕く。MCに聞かれる前に言い換えるのが理想
- 1ターンは2〜3文程度。長すぎるモノローグは避ける
- 掛け合いのテンポを大切に。間に呼吸を感じさせる

## 重要：出力形式
以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "mode": "explainer",
  "dialogue": [
    {"speaker": "speaker_a", "text": "MCの発言テキスト"},
    {"speaker": "speaker_b", "text": "解説者の発言テキスト"}
  ]
}

## 禁止事項
- セクション名・見出し・秒数指示の出力
- 情報源不明の断定
- 煽り・恐怖訴求
- 一方的な立場の押し付け
- 専門用語の説明なし使用

## 読みがなルール
- 難読固有名詞は初出時に丸カッコ内にひらがなで読みを補記する
- 一般的な漢字は補記不要。2回目以降も補記しない"""

SCRIPT_SHORT_SOLO_SYSTEM_PROMPT = """\
あなたはYouTubeショート動画用の台本を書く専門家です。
本編のニュース台本をもとに、15〜30秒で読み切れるショート台本を作成してください。

## 構成（厳守）
1. **フック（最初の3秒）**: 視聴者の指を止める一言。煽らず、好奇心を刺激する
   - 例: 「知ってましたか？」「○○が変わります」「意外な事実です」
2. **核心（10〜20秒）**: 本編の最もインパクトのある分析ポイントを1つだけ凝縮
   - 専門用語はその場で言い換え。数字は身近なスケールに
3. **問いかけ（最後の5秒）**: エンゲージメント促進。視聴者に考えさせる or コメントを促す

## ルール（厳守）
- **合計150文字以内**（厳守。日本語で150文字 ≒ 約25秒）
- 200文字を超えてはならない
- セクション見出し・秒数指示は含めない
- 本編の内容を前提知識なしで理解できるように
- 煽り・恐怖訴求は禁止

以下のJSON形式で回答してください:
{
  "text": "ショート台本の全文（150文字以内）",
  "caption": "SNS投稿用の短いキャプション（50文字以内）"
}"""

SCRIPT_SHORT_EXPLAINER_SYSTEM_PROMPT = """\
あなたはYouTubeショート動画用の台本を書く専門家です。
本編のニュース台本をもとに、MC＋解説者の2人掛け合いで15〜30秒のショート台本を作成してください。

## 構成（厳守）
1. **フック（最初の3秒）**: MCが視聴者の指を止める一言で切り出す
2. **核心（10〜20秒）**: MCと解説者のテンポよい掛け合いで、本編の最も重要なポイントを凝縮
3. **問いかけ（最後の5秒）**: MCがリスナーに問いかけて締める

## ルール（厳守）
- **全ターンの合計150文字以内**（厳守。日本語で150文字 ≒ 約25秒）
- 200文字を超えてはならない
- ターンは4〜6回、各ターン1文のみ、テンポ重視
- セクション見出し・秒数指示は含めない
- 煽り・恐怖訴求は禁止

以下のJSON形式で回答してください:
{
  "mode": "explainer",
  "dialogue": [
    {"speaker": "speaker_a", "text": "MCの発言（短く）"},
    {"speaker": "speaker_b", "text": "解説者の発言（短く）"}
  ],
  "caption": "SNS投稿用の短いキャプション（50文字以内）"
}"""

register_default(PROMPT_KEY_ITEM, SCRIPT_ITEM_SYSTEM_PROMPT)
register_default(PROMPT_KEY_ITEM_EXPLAINER, SCRIPT_ITEM_EXPLAINER_SYSTEM_PROMPT)
register_default(PROMPT_KEY_EPISODE, SCRIPT_EPISODE_SYSTEM_PROMPT)
register_default(PROMPT_KEY_SHORT_SOLO, SCRIPT_SHORT_SOLO_SYSTEM_PROMPT)
register_default(PROMPT_KEY_SHORT_EXPLAINER, SCRIPT_SHORT_EXPLAINER_SYSTEM_PROMPT)


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
        explainer_prompt, _ = await get_active_prompt(session, PROMPT_KEY_ITEM_EXPLAINER)
        episode_prompt, episode_prompt_version = await get_active_prompt(session, PROMPT_KEY_EPISODE)

        # Load speaker profiles for TTS hint injection and explainer mode
        speakers_result = await session.execute(select(SpeakerProfile))
        speakers_by_role: dict[str, SpeakerProfile] = {}
        for sp in speakers_result.scalars():
            speakers_by_role[sp.role] = sp

        # Inject TTS voice style instructions from narrator profile
        narrator_profile = speakers_by_role.get("narrator")
        if narrator_profile and narrator_profile.voice_instructions:
            tts_hint = (
                f"\n\n## 音声スタイルへの最適化\n"
                f"この台本は以下の指示で音声合成されます。この話し方に合った文体・リズム・語尾で書いてください:\n"
                f"「{narrator_profile.voice_instructions}」"
            )
            item_prompt += tts_hint
            episode_prompt += tts_hint

        # Inject speaker names and voice hints into explainer prompt
        anchor = speakers_by_role.get("anchor")
        expert = speakers_by_role.get("expert")
        speaker_hint = ""
        if anchor or expert:
            speaker_hint = "\n\n## スピーカー情報\n"
            if anchor:
                speaker_hint += f"- speaker_a（MC）: {anchor.name}。{anchor.description or ''}\n"
                if anchor.voice_instructions:
                    speaker_hint += f"  話し方: {anchor.voice_instructions}\n"
            if expert:
                speaker_hint += f"- speaker_b（解説者）: {expert.name}。{expert.description or ''}\n"
                if expert.voice_instructions:
                    speaker_hint += f"  話し方: {expert.voice_instructions}\n"
            explainer_prompt += speaker_hint

        item_scripts: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        all_items = await self._get_news_items(episode_id, session)

        # Filter out:
        # - excluded items (user-excluded at approval)
        # - low fact-check reliability (unverified or disputed)
        # - non-primary group members (merged into primary)
        items = [
            item for item in all_items
            if not item.excluded
            and item.fact_check_status not in ("unverified", "disputed")
            and (item.is_group_primary is True or item.group_id is None)
        ]
        # Clear script data from skipped items (idempotent: re-run cleans old data)
        skipped_items = [item for item in all_items if item not in items]
        for item in skipped_items:
            item.script_text = None
            item.script_mode = None
            item.script_data = None
        if skipped_items:
            logger.info(
                "Episode %d: skipped %d items (low reliability or non-primary group members)",
                episode_id, len(skipped_items),
            )

        if not items:
            raise ValueError("No reliable news items to generate scripts for")

        # Phase 1: per-article scripts (with mode selection)
        for i, item in enumerate(items):
            mode = self._determine_script_mode(item, settings.script_default_mode)
            if mode == "explainer":
                await self.log_progress(episode_id, f"[{i + 1}/{len(items)}] 「{item.title[:30]}」の対話台本を生成中")
                result = await self._script_item_explainer(
                    item, provider, model, explainer_prompt, session, episode_id,
                    all_items, speakers_by_role,
                )
            else:
                await self.log_progress(episode_id, f"[{i + 1}/{len(items)}] 「{item.title[:30]}」の台本を生成中")
                result = await self._script_item(item, provider, model, item_prompt, session, episode_id, all_items)
            item_scripts.append(result)
            total_input_tokens += result["input_tokens"]
            total_output_tokens += result["output_tokens"]

        # Phase 2: episode composition
        await self.log_progress(episode_id, "エピソード全体の構成を生成中（オープニング・つなぎ・エンディング）")
        episode_script = await self._compose_episode(
            item_scripts, provider, model, episode_prompt, session, episode_id
        )
        total_input_tokens += episode_script["input_tokens"]
        total_output_tokens += episode_script["output_tokens"]

        # Phase 3: Generate shorts if enabled on the episode
        shorts_data: list[dict] = []
        ep_result = await session.execute(
            select(Episode).where(Episode.id == episode_id)
        )
        episode_obj = ep_result.scalar_one()
        if episode_obj.shorts_enabled:
            short_solo_prompt, _ = await get_active_prompt(session, PROMPT_KEY_SHORT_SOLO)
            short_explainer_prompt, _ = await get_active_prompt(session, PROMPT_KEY_SHORT_EXPLAINER)
            # Inject speaker info into short explainer prompt
            if speaker_hint:
                short_explainer_prompt += speaker_hint

            for i, item in enumerate(items):
                mode = item.script_mode or "solo"
                await self.log_progress(
                    episode_id,
                    f"[{i + 1}/{len(items)}] ショート台本を生成中「{item.title[:25]}」"
                )
                short = await self._generate_short(
                    item, provider, model,
                    short_explainer_prompt if mode == "explainer" else short_solo_prompt,
                    mode, session, episode_id, speakers_by_role,
                )
                shorts_data.append(short)
                total_input_tokens += short["input_tokens"]
                total_output_tokens += short["output_tokens"]

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
        if shorts_data:
            result["shorts"] = shorts_data
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
        item.script_mode = "solo"
        item.script_data = None

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
            "mode": "solo",
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    def _determine_script_mode(self, item: NewsItem, default_mode: str) -> str:
        """Determine script mode for a news item.

        Priority:
        1. news_item.script_mode (user override)
        2. settings.script_default_mode (if not "auto")
        3. analysis_data["recommended_format"] (AI recommendation)
        4. Fallback: "solo"
        """
        if item.script_mode and item.script_mode in ("explainer", "solo"):
            return item.script_mode

        if default_mode and default_mode != "auto":
            return default_mode

        if item.analysis_data and isinstance(item.analysis_data, dict):
            recommended = item.analysis_data.get("recommended_format")
            if recommended in ("explainer", "solo"):
                return recommended

        return "solo"

    async def _script_item_explainer(
        self,
        item: NewsItem,
        provider,
        model: str,
        system_prompt: str,
        session: AsyncSession,
        episode_id: int,
        all_items: list[NewsItem] | None = None,
        speakers_by_role: dict[str, SpeakerProfile] | None = None,
    ) -> dict:
        """Generate a dialogue-style script for a news item (explainer mode)."""
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

        # Build speaker names from profiles
        anchor = speakers_by_role.get("anchor") if speakers_by_role else None
        expert = speakers_by_role.get("expert") if speakers_by_role else None
        speaker_a_name = anchor.name if anchor else "MC"
        speaker_b_name = expert.name if expert else "解説者"

        # Save structured dialogue data
        dialogue = data.get("dialogue", [])
        script_data = {
            "mode": "explainer",
            "speakers": {"speaker_a": speaker_a_name, "speaker_b": speaker_b_name},
            "dialogue": dialogue,
        }
        item.script_data = script_data
        item.script_mode = "explainer"

        # Also save flat text for backwards compatibility
        flat_lines = []
        for turn in dialogue:
            speaker = turn.get("speaker", "speaker_a")
            name = speaker_a_name if speaker == "speaker_a" else speaker_b_name
            flat_lines.append(f"{name}: {turn.get('text', '')}")
        item.script_text = "\n".join(flat_lines)

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
            "mode": "explainer",
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def _generate_short(
        self,
        item: NewsItem,
        provider,
        model: str,
        system_prompt: str,
        mode: str,
        session: AsyncSession,
        episode_id: int,
        speakers_by_role: dict[str, SpeakerProfile] | None = None,
    ) -> dict:
        """Generate a short video script for a news item."""
        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"本編台本:\n{item.script_text or '(なし)'}"
        )

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

        short: dict = {
            "news_item_id": item.id,
            "title": item.title,
            "mode": mode,
            "caption": data.get("caption", ""),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

        if mode == "explainer":
            dialogue = data.get("dialogue", [])
            anchor = speakers_by_role.get("anchor") if speakers_by_role else None
            expert = speakers_by_role.get("expert") if speakers_by_role else None
            speaker_a_name = anchor.name if anchor else "MC"
            speaker_b_name = expert.name if expert else "解説者"
            short["dialogue"] = dialogue
            short["speakers"] = {"speaker_a": speaker_a_name, "speaker_b": speaker_b_name}
            # Flat text for TTS fallback
            flat = "\n".join(
                f"{speaker_a_name if t.get('speaker') == 'speaker_a' else speaker_b_name}: {t.get('text', '')}"
                for t in dialogue
            )
            short["text"] = flat
        else:
            short["text"] = data.get("text", "")

        return short

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
