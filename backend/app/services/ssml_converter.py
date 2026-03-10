"""Convert plain text to SSML using LLM for natural prosody."""

import logging

from app.services.ai_provider import get_step_provider

logger = logging.getLogger(__name__)

SSML_SYSTEM_PROMPT = """\
あなたはGoogle Cloud Text-to-Speech用のSSMLマークアップの専門家です。

与えられた日本語のラジオ台本テキストに、自然な抑揚・間・強調をつけるためのSSMLタグを付与してください。

## 使用可能なSSMLタグ

### <break> — 間（ま）
- `<break time="300ms"/>` 短い間（文の区切り）
- `<break time="500ms"/>` 中くらいの間（話題の転換前）
- `<break time="800ms"/>` 長い間（重要なポイントの前、段落の区切り）

### <prosody> — 速度・ピッチ
- `<prosody rate="slow">` ゆっくり（考えさせる箇所、問いかけ）
- `<prosody rate="95%">` やや遅め（重要な説明）
- `<prosody rate="105%">` やや速め（テンポよく進める箇所）
- `<prosody pitch="+2st">` やや高め（明るい話題、驚き）
- `<prosody pitch="-1st">` やや低め（落ち着いた解説）

### <emphasis> — 強調
- `<emphasis level="moderate">` 適度な強調（金額、キーワード）
- `<emphasis level="strong">` 強い強調（最重要ポイント）

## ルール
1. テキストの内容は一切変更しないこと。タグの挿入のみ行う
2. タグを入れすぎない。全体の20-30%程度の箇所に留める
3. 以下の場面で効果的に使う:
   - 重要な数字（金額、割合）→ emphasis
   - 話題の転換（「さて」「ところが」「一方で」）→ break
   - 問いかけ・考えさせる文 → prosody rate="slow"
   - 驚きや意外性のある文 → prosody pitch="+2st"
   - 落ち着いた解説・まとめ → prosody pitch="-1st"
   - 段落の区切り → break time="800ms"
4. `<speak>` タグで全体を囲むこと
5. テキスト中の特殊文字（&, <, >, ", '）はXMLエスケープすること
6. SSML以外のテキスト（説明やコメント）は含めないこと。SSMLのみ出力すること"""


async def convert_to_ssml(text: str, session=None, episode_id: int | None = None) -> str:
    """Convert plain text to SSML using LLM.

    Args:
        text: Plain text to convert.
        session: DB session for recording API usage (optional).
        episode_id: Episode ID for cost tracking (optional).

    Returns:
        SSML string wrapped in <speak> tags.
    """
    if not text.strip():
        return "<speak></speak>"

    # Reuse script step's AI provider for SSML conversion
    provider, model = get_step_provider("script")

    response = await provider.generate(
        prompt=text,
        model=model,
        system=SSML_SYSTEM_PROMPT,
    )

    ssml = response.content.strip()

    # Ensure it's wrapped in <speak> tags
    if not ssml.startswith("<speak>"):
        ssml = f"<speak>{ssml}</speak>"
    if not ssml.endswith("</speak>"):
        ssml = ssml + "</speak>"

    logger.debug(
        "SSML conversion: %d chars -> %d chars (%d input_tokens, %d output_tokens)",
        len(text), len(ssml), response.input_tokens, response.output_tokens,
    )

    # Record API usage if session provided
    if session and episode_id:
        from app.models import ApiUsage, StepName
        from app.services.cost_estimator import estimate_cost

        cost = await estimate_cost(session, model, response.input_tokens, response.output_tokens)
        usage = ApiUsage(
            episode_id=episode_id,
            step_name=StepName.VOICE.value,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost,
        )
        session.add(usage)

    return ssml
