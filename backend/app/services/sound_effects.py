"""Sound effects (SE) preset loader.

Loads SE WAV files from ``backend/static/se/`` and resamples to match
the TTS output sample rate when necessary.
"""

from __future__ import annotations

import io
import struct
import wave
from pathlib import Path

SE_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "se"

# Available presets per position
SE_PRESETS: dict[str, list[str]] = {
    "intro": ["intro_chime", "none"],
    "transition": ["transition_chime", "transition_swoosh", "none"],
    "outro": ["outro_chime", "none"],
}


def list_se_presets() -> dict[str, list[str]]:
    """Return available SE presets grouped by position."""
    return SE_PRESETS


def load_se(preset_name: str, target_sample_rate: int) -> bytes | None:
    """Load an SE preset WAV file, resampling to *target_sample_rate* if needed.

    Returns ``None`` when *preset_name* is ``"none"`` or empty.
    """
    if not preset_name or preset_name == "none":
        return None

    path = SE_DIR / f"{preset_name}.wav"
    if not path.exists():
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
