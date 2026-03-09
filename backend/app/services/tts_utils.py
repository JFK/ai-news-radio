"""Common TTS utility functions shared across providers."""

import io
import wave


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on Japanese punctuation and newlines."""
    if not text:
        return []

    sentences: list[str] = []
    current = ""
    for char in text:
        if char in "。！？\n":
            current += char
            stripped = current.strip()
            if stripped:
                sentences.append(stripped)
            current = ""
        else:
            current += char

    stripped = current.strip()
    if stripped:
        sentences.append(stripped)

    return sentences


def concatenate_wav(chunks: list[bytes]) -> bytes:
    """Concatenate multiple WAV byte chunks into a single WAV file."""
    if len(chunks) == 1:
        return chunks[0]

    output = io.BytesIO()
    params_set = False

    with wave.open(output, "wb") as out_wav:
        for chunk in chunks:
            with wave.open(io.BytesIO(chunk), "rb") as in_wav:
                if not params_set:
                    out_wav.setparams(in_wav.getparams())
                    params_set = True
                out_wav.writeframes(in_wav.readframes(in_wav.getnframes()))

    return output.getvalue()


def split_text_chunks(text: str, max_chars: int = 4096) -> list[str]:
    """Split text into chunks that fit within the character limit.

    Tries to split on sentence boundaries (。！？\\n) for natural breaks.
    """
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for char in text:
        current += char
        if char in "。！？\n" and len(current) >= max_chars * 0.5:
            stripped = current.strip()
            if stripped:
                chunks.append(stripped)
            current = ""

    # Handle remaining text
    stripped = current.strip()
    if stripped:
        if chunks and len(chunks[-1]) + len(stripped) <= max_chars:
            chunks[-1] += stripped
        else:
            chunks.append(stripped)

    return chunks


def concatenate_mp3(chunks: list[bytes]) -> bytes:
    """Concatenate multiple MP3 byte chunks into a single MP3 file.

    MP3 frames are self-contained, so simple concatenation works.
    """
    output = io.BytesIO()
    for chunk in chunks:
        output.write(chunk)
    return output.getvalue()
