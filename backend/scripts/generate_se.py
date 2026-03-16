#!/usr/bin/env python3
"""Generate sound effect preset WAV files using pure Python synthesis.

Usage:
    python backend/scripts/generate_se.py

Generates WAV files in backend/static/se/
"""

import io
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 24000
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "se"

# Note frequencies (Hz)
C4 = 261.63
D4 = 293.66
E4 = 329.63
F4 = 349.23
G4 = 392.00
A4 = 440.00
B4 = 493.88
C5 = 523.25
D5 = 587.33
E5 = 659.25
F5 = 698.46
G5 = 783.99
A5 = 880.00
B5 = 987.77
C6 = 1046.50


def generate_tone(
    freq: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    volume: float = 0.5,
) -> list[float]:
    """Generate sine wave samples as floats in [-1, 1]."""
    n_samples = int(sample_rate * duration)
    return [volume * math.sin(2 * math.pi * freq * i / sample_rate) for i in range(n_samples)]


def generate_harmonics(
    freq: float,
    duration: float,
    harmonics: list[tuple[float, float]] | None = None,
    sample_rate: int = SAMPLE_RATE,
    volume: float = 0.5,
) -> list[float]:
    """Generate tone with harmonics. harmonics = [(multiplier, amplitude), ...]"""
    if harmonics is None:
        harmonics = [(1.0, 1.0), (2.0, 0.3), (3.0, 0.1)]
    n_samples = int(sample_rate * duration)
    samples = [0.0] * n_samples
    for mult, amp in harmonics:
        for i in range(n_samples):
            samples[i] += volume * amp * math.sin(2 * math.pi * freq * mult * i / sample_rate)
    # Normalize
    peak = max(abs(s) for s in samples) or 1.0
    return [s / peak * volume for s in samples]


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


def mix(*tracks: list[float]) -> list[float]:
    """Mix multiple sample lists by addition."""
    length = max(len(t) for t in tracks)
    result = [0.0] * length
    for track in tracks:
        for i, s in enumerate(track):
            result[i] += s
    return result


def offset_samples(samples: list[float], offset_secs: float, sample_rate: int = SAMPLE_RATE) -> list[float]:
    """Prepend silence to offset samples in time."""
    pad = [0.0] * int(sample_rate * offset_secs)
    return pad + samples


def silence(duration: float, sample_rate: int = SAMPLE_RATE) -> list[float]:
    """Generate silence samples."""
    return [0.0] * int(sample_rate * duration)


def clamp_and_normalize(samples: list[float], target_volume: float = 0.8) -> list[float]:
    """Normalize samples to target volume."""
    peak = max(abs(s) for s in samples) or 1.0
    scale = target_volume / peak
    return [s * scale for s in samples]


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


# ──────────────────────────────────────────────
# Intro presets
# ──────────────────────────────────────────────

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
    all_samples.extend(silence(0.3))
    return samples_to_wav(all_samples)


def generate_intro_news() -> bytes:
    """News broadcast-style layered intro jingle (~2s)."""
    # Bold chord: C4+E4+G4+C5 with harmonics
    chord_notes = [C4, E4, G4, C5]
    tracks = []
    for j, note in enumerate(chord_notes):
        t = generate_harmonics(note, 1.5, volume=0.25)
        t = apply_envelope(t, attack=0.02, decay=0.6)
        t = offset_samples(t, j * 0.08)
        tracks.append(t)
    chord = mix(*tracks)

    # Rising accent notes
    accent_notes = [G4, C5, E5, G5]
    accent = []
    for j, note in enumerate(accent_notes):
        t = generate_tone(note, 0.12, volume=0.3)
        t = apply_exp_decay(t, decay_rate=8.0)
        t = offset_samples(t, 1.0 + j * 0.1)
        if accent:
            accent = mix(accent, t)
        else:
            accent = t

    result = mix(chord, accent)
    result.extend(silence(0.3))
    result = clamp_and_normalize(result, 0.6)
    return samples_to_wav(result)


def generate_intro_bright() -> bytes:
    """Bright ascending arpeggio C5→E5→G5→C6."""
    notes = [C5, E5, G5, C6]
    all_samples: list[float] = []
    for note in notes:
        tone = generate_harmonics(note, 0.2, harmonics=[(1.0, 1.0), (2.0, 0.5), (4.0, 0.15)], volume=0.35)
        tone = apply_exp_decay(tone, decay_rate=6.0)
        all_samples.extend(tone)
        all_samples.extend(silence(0.02))
    all_samples.extend(silence(0.4))
    return samples_to_wav(all_samples)


# ──────────────────────────────────────────────
# Transition presets
# ──────────────────────────────────────────────

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
        freq = 300 + (1500 - 300) * progress
        env = math.sin(math.pi * progress) * 0.3
        samples.append(env * math.sin(2 * math.pi * freq * t))
    return samples_to_wav(samples)


def generate_transition_soft() -> bytes:
    """Soft double-tap notification (two gentle tones)."""
    t1 = generate_harmonics(A5, 0.15, harmonics=[(1.0, 1.0), (2.0, 0.2)], volume=0.25)
    t1 = apply_exp_decay(t1, decay_rate=10.0)
    t2 = generate_harmonics(E5, 0.2, harmonics=[(1.0, 1.0), (2.0, 0.2)], volume=0.2)
    t2 = apply_exp_decay(t2, decay_rate=8.0)
    t2 = offset_samples(t2, 0.18)
    result = mix(t1, t2)
    result.extend(silence(0.2))
    return samples_to_wav(result)


def generate_transition_tick() -> bytes:
    """Short percussive tick/click sound."""
    # White noise burst + short tone
    duration = 0.08
    n_samples = int(SAMPLE_RATE * duration)
    import random
    random.seed(42)  # Reproducible
    noise = [random.uniform(-0.3, 0.3) for _ in range(n_samples)]
    tone = generate_tone(800, duration, volume=0.4)
    result = mix(noise, tone)
    result = apply_exp_decay(result, attack=0.001, decay_rate=30.0)
    result.extend(silence(0.15))
    return samples_to_wav(result)


def generate_transition_bell() -> bytes:
    """Warm bell tone with harmonics."""
    tone = generate_harmonics(
        C5, 0.6,
        harmonics=[(1.0, 1.0), (2.0, 0.6), (3.0, 0.3), (4.0, 0.15), (5.0, 0.08)],
        volume=0.3,
    )
    tone = apply_exp_decay(tone, attack=0.002, decay_rate=4.0)
    tone.extend(silence(0.1))
    return samples_to_wav(tone)


# ──────────────────────────────────────────────
# Outro presets
# ──────────────────────────────────────────────

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
    all_samples.extend(silence(0.4))
    return samples_to_wav(all_samples)


def generate_outro_warm() -> bytes:
    """Warm descending chord resolution (~2s)."""
    # G major → C major resolution
    g_chord = [G4, B4, D5]
    c_chord = [C4, E4, G4]

    tracks_g = []
    for note in g_chord:
        t = generate_harmonics(note, 1.0, volume=0.2)
        t = apply_envelope(t, attack=0.02, decay=0.4)
        tracks_g.append(t)
    part1 = mix(*tracks_g)

    tracks_c = []
    for note in c_chord:
        t = generate_harmonics(note, 1.2, volume=0.25)
        t = apply_envelope(t, attack=0.05, decay=0.6)
        t = offset_samples(t, 0.9)
        tracks_c.append(t)
    part2 = mix(*tracks_c)

    result = mix(part1, part2)
    result.extend(silence(0.3))
    result = clamp_and_normalize(result, 0.5)
    return samples_to_wav(result)


def generate_outro_fade() -> bytes:
    """Soft fading tone with slight vibrato."""
    duration = 1.5
    n_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        progress = i / n_samples
        # Vibrato
        vibrato = math.sin(2 * math.pi * 5 * t) * 3
        freq = C5 + vibrato
        # Fade out
        env = (1 - progress) ** 2 * 0.35
        samples.append(env * math.sin(2 * math.pi * freq * t))
    samples.extend(silence(0.2))
    return samples_to_wav(samples)


# ──────────────────────────────────────────────
# Pop presets (each position)
# ──────────────────────────────────────────────

def generate_intro_pop() -> bytes:
    """Upbeat pop intro - bouncy rising notes with rhythm."""
    notes = [C5, E5, G5, C6, G5, C6]
    durations = [0.1, 0.1, 0.1, 0.15, 0.08, 0.2]
    all_samples: list[float] = []
    for note, dur in zip(notes, durations):
        tone = generate_harmonics(note, dur, harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.15)], volume=0.35)
        tone = apply_exp_decay(tone, attack=0.003, decay_rate=8.0)
        all_samples.extend(tone)
        all_samples.extend(silence(0.03))
    all_samples.extend(silence(0.3))
    return samples_to_wav(all_samples)


def generate_transition_pop() -> bytes:
    """Pop bubble/pluck transition sound."""
    # Rapid pitch drop (bubble pop effect)
    duration = 0.15
    n_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        progress = i / n_samples
        # Start high, drop quickly
        freq = 1200 * math.exp(-8 * progress) + 200
        env = math.exp(-6 * progress) * 0.4
        samples.append(env * math.sin(2 * math.pi * freq * t))
    # Add a softer second pop
    pop2_dur = 0.1
    n2 = int(SAMPLE_RATE * pop2_dur)
    pop2 = []
    for i in range(n2):
        t = i / SAMPLE_RATE
        progress = i / n2
        freq = 900 * math.exp(-10 * progress) + 300
        env = math.exp(-8 * progress) * 0.25
        pop2.append(env * math.sin(2 * math.pi * freq * t))
    pop2 = offset_samples(pop2, 0.18)
    result = mix(samples, pop2)
    result.extend(silence(0.15))
    return samples_to_wav(result)


def generate_outro_pop() -> bytes:
    """Pop outro - playful descending bouncy notes."""
    notes = [C6, G5, E5, C5, G4, C5]
    durations = [0.08, 0.08, 0.1, 0.1, 0.12, 0.25]
    all_samples: list[float] = []
    for note, dur in zip(notes, durations):
        tone = generate_harmonics(note, dur, harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.1)], volume=0.3)
        tone = apply_exp_decay(tone, attack=0.003, decay_rate=6.0)
        all_samples.extend(tone)
        all_samples.extend(silence(0.04))
    all_samples.extend(silence(0.4))
    return samples_to_wav(all_samples)


# ──────────────────────────────────────────────

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generators = {
        # Intro
        "intro_chime.wav": generate_intro_chime,
        "intro_news.wav": generate_intro_news,
        "intro_bright.wav": generate_intro_bright,
        "intro_pop.wav": generate_intro_pop,
        # Transition
        "transition_chime.wav": generate_transition_chime,
        "transition_swoosh.wav": generate_transition_swoosh,
        "transition_soft.wav": generate_transition_soft,
        "transition_tick.wav": generate_transition_tick,
        "transition_bell.wav": generate_transition_bell,
        "transition_pop.wav": generate_transition_pop,
        # Outro
        "outro_chime.wav": generate_outro_chime,
        "outro_warm.wav": generate_outro_warm,
        "outro_fade.wav": generate_outro_fade,
        "outro_pop.wav": generate_outro_pop,
    }

    for filename, gen_func in generators.items():
        path = OUTPUT_DIR / filename
        wav_data = gen_func()
        path.write_bytes(wav_data)
        size_kb = len(wav_data) / 1024
        print(f"  Generated {path} ({size_kb:.1f} KB)")

    print(f"\nAll {len(generators)} SE presets generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
