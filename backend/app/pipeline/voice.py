"""Step 5: Voice synthesis pipeline step."""

import io
import logging
import os
import wave

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Episode, Pronunciation, StepName
from app.models.speaker_profile import SpeakerProfile
from app.pipeline.base import BaseStep
from app.services.sound_effects import load_se
from app.services.tts_provider import get_tts_provider
from app.services.tts_utils import concatenate_wav, expand_reading_hints

logger = logging.getLogger(__name__)

def _silence_seconds() -> float:
    """Get silence duration between sections from settings."""
    return settings.voice_section_silence

# Default CTA (Call To Action) text inserted after opening
DEFAULT_CTA_TEXT = (
    "この番組では、ニュースの背景や多様な視点をわかりやすくお届けしています。"
    "チャンネル登録と高評価、よろしくお願いします。"
)


class VoiceStep(BaseStep):
    """Generate audio from the episode script using a TTS provider."""

    @property
    def step_name(self) -> StepName:
        return StepName.VOICE

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Synthesize audio per article, then concatenate with silence gaps.

        Produces individual WAV/MP3 files per section (opening, each news item,
        transitions, ending) and a combined audio file.
        """
        tts_model_override = kwargs.get("tts_model")
        tts_voice_override = kwargs.get("tts_voice")
        provider = get_tts_provider(model=tts_model_override, voice=tts_voice_override)
        audio_format = provider.audio_format
        use_ssml = settings.pipeline_voice_provider == "google"  # SSML only for Cloud TTS, not Gemini

        # Load speaker profiles for multi-speaker synthesis
        speakers_result = await session.execute(select(SpeakerProfile))
        speakers_by_role: dict[str, SpeakerProfile] = {}
        for sp in speakers_result.scalars():
            speakers_by_role[sp.role] = sp

        # Create multi-speaker provider if we have anchor + expert
        multi_provider = None
        anchor = speakers_by_role.get("anchor")
        expert = speakers_by_role.get("expert")
        if anchor and expert and settings.pipeline_voice_provider == "gemini":
            from app.services.tts_gemini_multi import GeminiMultiSpeakerTTSProvider
            multi_provider = GeminiMultiSpeakerTTSProvider(
                model=tts_model_override or settings.gemini_tts_model,
                speaker_a_voice=anchor.voice_name,
                speaker_b_voice=expert.voice_name,
                speaker_a_instructions=anchor.voice_instructions or "",
                speaker_b_instructions=expert.voice_instructions or "",
            )

        # Load pronunciation dictionary
        pron_result = await session.execute(
            select(Pronunciation).order_by(Pronunciation.priority.desc(), Pronunciation.id)
        )
        pronunciations = list(pron_result.scalars().all())

        # Load news items for per-article synthesis
        items = await self._get_news_items(episode_id, session)

        # Get script parts from scriptwriter output
        opening = input_data.get("opening", "")
        transitions = input_data.get("transitions", [])
        ending = input_data.get("ending", "")

        # Build ordered list of sections to synthesize
        sections: list[dict] = []

        if opening:
            sections.append({"key": "opening", "label": "オープニング", "text": opening})

        # CTA (subscribe & like) after opening
        if settings.youtube_cta_enabled and settings.youtube_cta_text:
            sections.append({"key": "cta", "label": "CTA", "text": settings.youtube_cta_text})

        for i, item in enumerate(items):
            if item.script_text:
                section: dict = {
                    "key": f"news_{item.id}",
                    "label": item.title,
                    "text": item.script_text,
                    "news_item_id": item.id,
                }
                if item.script_data and isinstance(item.script_data, dict):
                    section["script_data"] = item.script_data
                sections.append(section)
            if i < len(transitions) and transitions[i]:
                sections.append({"key": f"transition_{i}", "label": f"つなぎ{i + 1}", "text": transitions[i]})

        if ending:
            sections.append({"key": "ending", "label": "エンディング", "text": ending})

        # Outro (closing message) after ending
        if settings.youtube_outro_enabled and settings.youtube_outro_text:
            sections.append({"key": "outro", "label": "アウトロ", "text": settings.youtube_outro_text})

        if not sections:
            raise ValueError("No script sections found for audio synthesis")

        # Setup output directory
        episode_dir = os.path.join(settings.media_dir, str(episode_id))
        os.makedirs(episode_dir, exist_ok=True)

        # Synthesize each section
        section_results: list[dict] = []
        all_audio_chunks: list[bytes] = []
        silence_chunk: bytes | None = None  # Generated after first section (to match sample rate)
        total_chars = 0
        sample_rate = 24000  # Default; updated after first TTS output
        elapsed = 0.0  # Cumulative time tracking for accurate SRT timestamps

        for i, section in enumerate(sections):
            tts_text = self._prepare_tts_text(section["text"], pronunciations)
            total_chars += len(section["text"])

            # Convert to SSML for natural prosody (Google TTS only)
            await self.log_progress(episode_id, f"[{i + 1}/{len(sections)}] 「{section['label'][:30]}」を音声合成中")

            if use_ssml:
                from app.services.ssml_converter import convert_to_ssml

                tts_input = await convert_to_ssml(
                    tts_text, session=session, episode_id=episode_id,
                )
                logger.info(
                    "Episode %d: synthesizing section '%s' with SSML (%d chars)",
                    episode_id, section["key"], len(tts_text),
                )
            else:
                tts_input = tts_text
                logger.info(
                    "Episode %d: synthesizing section '%s' (%d chars)",
                    episode_id, section["key"], len(tts_text),
                )

            # Use multi-speaker for dialogue sections, single-speaker otherwise
            script_data = section.get("script_data")
            if (
                script_data
                and isinstance(script_data, dict)
                and script_data.get("mode") == "explainer"
                and multi_provider
            ):
                dialogue = script_data.get("dialogue", [])
                # Apply pronunciation to each dialogue turn
                processed_dialogue = []
                for turn in dialogue:
                    processed_text = self._prepare_tts_text(turn.get("text", ""), pronunciations)
                    processed_dialogue.append({"speaker": turn.get("speaker", "speaker_a"), "text": processed_text})
                audio_bytes = await multi_provider.synthesize_dialogue(processed_dialogue)
                logger.info(
                    "Episode %d: multi-speaker synthesis for section '%s' (%d turns)",
                    episode_id, section["key"], len(dialogue),
                )
            else:
                audio_bytes = await provider.synthesize(tts_input)

            # Generate silence chunk matching the sample rate of the first WAV
            if silence_chunk is None and audio_format == "wav":
                sample_rate = self._get_wav_sample_rate(audio_bytes)
                silence_chunk = self._generate_silence(_silence_seconds(), audio_format, sample_rate)

            # Insert intro SE before the very first section
            if i == 0 and audio_format == "wav":
                se_intro = load_se(settings.se_intro, sample_rate)
                if se_intro:
                    all_audio_chunks.append(se_intro)
                    elapsed += self._get_audio_duration(se_intro, audio_format)
                    logger.info("Episode %d: inserted intro SE '%s'", episode_id, settings.se_intro)

            # Save individual section audio
            section_filename = f"{section['key']}.{audio_format}"
            section_path = os.path.join(episode_dir, section_filename)
            with open(section_path, "wb") as f:
                f.write(audio_bytes)

            duration = self._get_audio_duration(audio_bytes, audio_format)

            # Record precise start/end timestamps for this section
            section_start = elapsed
            elapsed += duration

            section_results.append({
                "key": section["key"],
                "label": section["label"],
                "file": f"{episode_id}/{section_filename}",
                "duration_seconds": round(duration, 2),
                "start_at": round(section_start, 3),
                "end_at": round(elapsed, 3),
                **({"news_item_id": section["news_item_id"]} if "news_item_id" in section else {}),
            })

            all_audio_chunks.append(audio_bytes)

            # Add silence or SE transition between sections (not after the last one)
            if i < len(sections) - 1:
                inserted_se = False
                next_key = sections[i + 1]["key"]
                cur_key = section["key"]
                is_news_boundary = (
                    cur_key.startswith(("news_", "transition_"))
                    or next_key.startswith(("news_", "transition_"))
                )
                if is_news_boundary and audio_format == "wav":
                    se_trans = load_se(settings.se_transition, sample_rate)
                    if se_trans:
                        all_audio_chunks.append(se_trans)
                        elapsed += self._get_audio_duration(se_trans, audio_format)
                        inserted_se = True
                if not inserted_se and silence_chunk:
                    all_audio_chunks.append(silence_chunk)
                    elapsed += _silence_seconds()

        # Insert outro SE after the last section
        if audio_format == "wav":
            se_outro = load_se(settings.se_outro, sample_rate)
            if se_outro:
                all_audio_chunks.append(se_outro)
                elapsed += self._get_audio_duration(se_outro, audio_format)
                logger.info("Episode %d: inserted outro SE '%s'", episode_id, settings.se_outro)

        # Concatenate all sections into combined audio
        combined_audio = concatenate_wav(all_audio_chunks) if audio_format == "wav" else b"".join(all_audio_chunks)

        combined_filename = f"audio.{audio_format}"
        combined_path = os.path.join(episode_dir, combined_filename)
        with open(combined_path, "wb") as f:
            f.write(combined_audio)

        total_duration = self._get_audio_duration(combined_audio, audio_format)
        relative_path = f"{episode_id}/{combined_filename}"

        # Update episode record
        ep_result = await session.execute(select(Episode).where(Episode.id == episode_id))
        episode = ep_result.scalar_one()
        episode.audio_path = relative_path
        await session.commit()

        # Record usage for TTS
        provider_name = settings.pipeline_voice_provider
        if provider_name != "voicevox":
            model_map = {
                "openai": settings.openai_tts_model,
                "elevenlabs": f"elevenlabs-{settings.elevenlabs_model_id.split('_')[-1]}",
                "google": (
                    f"google-tts-{settings.google_tts_voice.split('-')[2].lower()}"
                    if len(settings.google_tts_voice.split("-")) > 2
                    else "google-tts-standard"
                ),
                "gemini": settings.gemini_tts_model,
            }
            provider_label_map = {
                "google": "google-tts",
                "gemini": "gemini-tts",
            }
            model_name = model_map.get(provider_name, provider_name)

            # Use actual token counts from Gemini TTS if available
            input_tokens = total_chars
            output_tokens = 0
            if provider_name == "gemini" and hasattr(provider, "total_input_tokens"):
                input_tokens = provider.total_input_tokens
                output_tokens = provider.total_output_tokens
                # Include multi-speaker provider tokens
                if multi_provider:
                    input_tokens += multi_provider.total_input_tokens
                    output_tokens += multi_provider.total_output_tokens

            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider=provider_label_map.get(provider_name, provider_name),
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # Build timestamps for YouTube description
        timestamps = self._build_timestamps(section_results)

        logger.info(
            "Episode %d: audio saved to %s (%.1fs, %d sections)",
            episode_id, relative_path, total_duration, len(section_results),
        )

        return {
            "audio_path": relative_path,
            "duration_seconds": total_duration,
            "provider": settings.pipeline_voice_provider,
            "model": getattr(provider, "_model", None) or "",
            "voice": getattr(provider, "_voice", None) or "",
            "audio_format": audio_format,
            "sections": section_results,
            "timestamps": timestamps,
        }

    def _prepare_tts_text(self, text: str, pronunciations: list[Pronunciation]) -> str:
        """Expand reading hints and apply pronunciation dictionary."""
        tts_text = expand_reading_hints(text)
        for entry in pronunciations:
            tts_text = tts_text.replace(entry.surface, entry.reading)
        return tts_text

    def _get_wav_sample_rate(self, wav_bytes: bytes) -> int:
        """Extract sample rate from WAV bytes."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            return wav.getframerate()

    def _generate_silence(self, duration_seconds: float, audio_format: str, sample_rate: int = 24000) -> bytes:
        """Generate silence audio in WAV format."""
        if audio_format != "wav":
            return b""  # TODO: MP3 silence generation not yet supported

        num_frames = int(sample_rate * duration_seconds)
        silence_frames = b"\x00\x00" * num_frames  # 16-bit silence

        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(silence_frames)
        return output.getvalue()

    def _build_timestamps(self, section_results: list[dict]) -> str:
        """Build YouTube-style timestamps from section durations.

        Uses precise start_at timestamps when available, falls back to
        cumulative calculation with silence gaps.
        """
        lines: list[str] = []
        elapsed = 0.0

        for i, section in enumerate(section_results):
            # Use precise start_at if available, otherwise fall back to elapsed
            pos = section.get("start_at", elapsed)

            # Skip transitions in timestamps (not useful for YouTube index)
            if not section["key"].startswith("transition_"):
                minutes = int(pos // 60)
                seconds = int(pos % 60)
                timestamp = f"{minutes}:{seconds:02d}"
                lines.append(f"{timestamp} {section['label']}")

            # Update fallback elapsed (for data without start_at)
            elapsed += section["duration_seconds"]
            if i < len(section_results) - 1:
                elapsed += _silence_seconds()

        return "\n".join(lines)

    def _get_audio_duration(self, audio_bytes: bytes, audio_format: str) -> float:
        """Get audio duration in seconds."""
        if audio_format == "wav":
            return self._get_wav_duration(audio_bytes)
        return len(audio_bytes) / (128 * 1024 / 8)

    def _get_wav_duration(self, wav_bytes: bytes) -> float:
        """Get WAV audio duration from bytes."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / rate if rate > 0 else 0.0
