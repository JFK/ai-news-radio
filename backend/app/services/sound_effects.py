"""Sound effects (SE) preset loader.

Loads SE WAV files from ``backend/static/se/`` (built-in presets) and
``media/se/`` (user uploads), resampling to match the TTS output sample
rate when necessary.
"""

from __future__ import annotations

import io
import logging
import struct
import wave
from pathlib import Path

from app.config import settings as app_settings

logger = logging.getLogger(__name__)

SE_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "se"

# Built-in presets per position
SE_PRESETS: dict[str, list[dict[str, str]]] = {
    "intro": [
        {"value": "intro_chime", "label": "Chime (ascending)"},
        {"value": "intro_news", "label": "News Jingle (broadcast)"},
        {"value": "intro_bright", "label": "Bright Arpeggio"},
        {"value": "intro_pop", "label": "Pop (bouncy)"},
    ],
    "transition": [
        {"value": "transition_chime", "label": "Chime (ding)"},
        {"value": "transition_swoosh", "label": "Swoosh (sweep)"},
        {"value": "transition_soft", "label": "Soft (double-tap)"},
        {"value": "transition_tick", "label": "Tick (percussive)"},
        {"value": "transition_bell", "label": "Bell (warm)"},
        {"value": "transition_pop", "label": "Pop (bubble)"},
    ],
    "outro": [
        {"value": "outro_chime", "label": "Chime (descending)"},
        {"value": "outro_warm", "label": "Warm (chord resolve)"},
        {"value": "outro_fade", "label": "Fade (vibrato)"},
        {"value": "outro_pop", "label": "Pop (playful)"},
    ],
}


def _custom_se_dir() -> Path:
    """Return directory for user-uploaded SE files."""
    return Path(app_settings.media_dir) / "se"


def list_se_presets() -> dict[str, list[dict[str, str]]]:
    """Return available SE presets grouped by position, including custom uploads."""
    result: dict[str, list[dict[str, str]]] = {}
    custom_dir = _custom_se_dir()

    for position, presets in SE_PRESETS.items():
        items = list(presets)
        # Add user-uploaded custom files for this position
        if custom_dir.exists():
            prefix = f"custom_{position}_"
            for f in sorted(custom_dir.glob(f"{prefix}*.wav")):
                name = f.stem  # e.g., custom_intro_myfile
                label = f"Custom: {f.stem[len(prefix):]}"
                if not any(p["value"] == name for p in items):
                    items.append({"value": name, "label": label})
        items.append({"value": "none", "label": "OFF (効果音なし)"})
        result[position] = items

    return result


def save_custom_se(position: str, filename: str, wav_data: bytes) -> str:
    """Save an uploaded SE WAV file. Returns the preset name."""
    custom_dir = _custom_se_dir()
    custom_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c for c in Path(filename).stem if c.isalnum() or c in "_-").strip("_-")
    if not safe_name:
        safe_name = "upload"
    preset_name = f"custom_{position}_{safe_name}"
    path = custom_dir / f"{preset_name}.wav"
    path.write_bytes(wav_data)
    logger.info("Saved custom SE: %s (%d bytes)", path, len(wav_data))
    return preset_name


def delete_custom_se(preset_name: str) -> bool:
    """Delete a custom SE file. Returns True if deleted."""
    if not preset_name.startswith("custom_"):
        return False
    path = _custom_se_dir() / f"{preset_name}.wav"
    if path.exists():
        path.unlink()
        return True
    return False


def load_se(preset_name: str, target_sample_rate: int) -> bytes | None:
    """Load an SE preset WAV file, resampling to *target_sample_rate* if needed.

    Searches built-in presets first, then custom uploads.
    Returns ``None`` when *preset_name* is ``"none"`` or empty.
    """
    if not preset_name or preset_name == "none":
        return None

    # Check built-in presets first, then custom uploads
    path = SE_DIR / f"{preset_name}.wav"
    if not path.exists():
        path = _custom_se_dir() / f"{preset_name}.wav"
    if not path.exists():
        logger.warning("SE preset not found: %s", preset_name)
        return None

    wav_bytes = path.read_bytes()

    # Check sample rate and resample if needed
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        src_rate = wf.getframerate()
        if src_rate == target_sample_rate:
            return wav_bytes
        # Resample via linear interpolation
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    # Decode source samples (16-bit signed)
    fmt = f"<{n_frames * n_channels}h"
    src_samples = list(struct.unpack(fmt, raw))

    # Resample
    ratio = target_sample_rate / src_rate
    new_n_frames = int(n_frames * ratio)
    resampled: list[int] = []
    for i in range(new_n_frames * n_channels):
        src_idx = i / ratio
        idx0 = int(src_idx)
        idx1 = min(idx0 + 1, len(src_samples) - 1)
        frac = src_idx - idx0
        val = src_samples[idx0] * (1 - frac) + src_samples[idx1] * frac
        resampled.append(int(max(-32768, min(32767, val))))

    # Write resampled WAV
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf_out:
        wf_out.setnchannels(n_channels)
        wf_out.setsampwidth(sampwidth)
        wf_out.setframerate(target_sample_rate)
        wf_out.writeframes(struct.pack(f"<{len(resampled)}h", *resampled))
    return buf.getvalue()
