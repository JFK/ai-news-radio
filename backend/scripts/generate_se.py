#!/usr/bin/env python3
"""Generate sound effect preset WAV files using pure Python synthesis.

Usage:
    python backend/scripts/generate_se.py

Generates WAV files in backend/static/se/:
    - intro_chime.wav      Ascending C5-E5-G5 chime (~1.2s)
    - transition_chime.wav Single E5 ding (~0.5s)
    - transition_swoosh.wav Frequency sweep (~0.4s)
    - outro_chime.wav      Descending G5-E5-C5 chime (~1.2s)
"""

import io
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 24000
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "se"

# Note frequencies (Hz)
C5 = 523.25
E5 = 659.25
G5 = 783.99


def generate_tone(
    freq: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    volume: float = 0.5,
) -> list[float]:
    """Generate sine wave samples as floats in [-1, 1]."""
    n_samples = int(sample_rate * duration)
    return [volume * math.sin(2 * math.pi * freq * i / sample_rate) for i in range(n_samples)]


def apply_envelope(
    samples: list[float],
    attack: float = 0.01,
    decay: float = 0.3,
    sample_rate: int = SAMPLE_RATE,
) -> list[float]:
    """Apply attack/decay envelope to samples."""
    attack_samples = int(sample_rate * attack)
    decay_samples = int(sample_rate * decay)
    n = len(samples)
    result = []
    for i, s in enumerate(samples):
        if i < attack_samples:
            env = i / max(attack_samples, 1)
        elif i > n - decay_samples:
            env = (n - i) / max(decay_samples, 1)
        else:
            env = 1.0
        result.append(s * env)
    return result


def apply_exp_decay(
    samples: list[float],
    attack: float = 0.005,
    decay_rate: float = 4.0,
    sample_rate: int = SAMPLE_RATE,
) -> list[float]:
    """Apply exponential decay envelope."""
    attack_samples = int(sample_rate * attack)
    result = []
    for i, s in enumerate(samples):
        t = i / sample_rate
        if i < attack_samples:
            env = i / max(attack_samples, 1)
        else:
            env = math.exp(-decay_rate * t)
        result.append(s * env)
    return result


def mix(a: list[float], b: list[float]) -> list[float]:
    """Mix two sample lists by addition, extending to the longer."""
    length = max(len(a), len(b))
    result = [0.0] * length
    for i in range(len(a)):
        result[i] += a[i]
    for i in range(len(b)):
        result[i] += b[i]
    return result


def silence(duration: float, sample_rate: int = SAMPLE_RATE) -> list[float]:
    """Generate silence samples."""
    return [0.0] * int(sample_rate * duration)


def samples_to_wav(samples: list[float], sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convert float samples to WAV bytes (16-bit mono)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            wf.writeframes(struct.pack("<h", int(clamped * 32767)))
    return buf.getvalue()


def generate_intro_chime() -> bytes:
    """Ascending C5 → E5 → G5 chime."""
    note_dur = 0.3
    gap = 0.05
    notes = [C5, E5, G5]
    all_samples: list[float] = []
    for note in notes:
        tone = generate_tone(note, note_dur, volume=0.4)
        tone = apply_envelope(tone, attack=0.01, decay=0.15)
        all_samples.extend(tone)
        all_samples.extend(silence(gap))
    # Add reverb tail
    all_samples.extend(silence(0.3))
    return samples_to_wav(all_samples)


def generate_transition_chime() -> bytes:
    """Single E5 ding with exponential decay."""
    tone = generate_tone(E5, 0.5, volume=0.35)
    tone = apply_exp_decay(tone, attack=0.005, decay_rate=5.0)
    return samples_to_wav(tone)


def generate_transition_swoosh() -> bytes:
    """Frequency sweep from low to high."""
    duration = 0.4
    n_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        progress = i / n_samples
        # Sweep from 300Hz to 1500Hz
        freq = 300 + (1500 - 300) * progress
        # Bell-shaped amplitude envelope
        env = math.sin(math.pi * progress) * 0.3
        samples.append(env * math.sin(2 * math.pi * freq * t))
    return samples_to_wav(samples)


def generate_outro_chime() -> bytes:
    """Descending G5 → E5 → C5 chime."""
    note_dur = 0.35
    gap = 0.05
    notes = [G5, E5, C5]
    all_samples: list[float] = []
    for note in notes:
        tone = generate_tone(note, note_dur, volume=0.4)
        tone = apply_envelope(tone, attack=0.01, decay=0.2)
        all_samples.extend(tone)
        all_samples.extend(silence(gap))
    # Longer tail for outro
    all_samples.extend(silence(0.4))
    return samples_to_wav(all_samples)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generators = {
        "intro_chime.wav": generate_intro_chime,
        "transition_chime.wav": generate_transition_chime,
        "transition_swoosh.wav": generate_transition_swoosh,
        "outro_chime.wav": generate_outro_chime,
    }

    for filename, gen_func in generators.items():
        path = OUTPUT_DIR / filename
        wav_data = gen_func()
        path.write_bytes(wav_data)
        size_kb = len(wav_data) / 1024
        print(f"  Generated {path} ({size_kb:.1f} KB)")

    print(f"\nAll SE presets generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
